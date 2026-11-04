#!/usr/bin/env python3
"""Plan by default; Kiro-only, resumable bounded AWS challenge deployment."""

import argparse
import hashlib
import importlib.util
import io
import json
import re
import secrets
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"
MODEL = "amazon.nova-lite-v1:0"
TAGS = {"project": "treehouse-judge", "purpose": "three-challenge-demo"}


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str) + "\n")
    temporary.replace(path)


def policy(statements):
    return json.dumps({"Version": "2012-10-17", "Statement": statements})


def allow(actions, resources):
    return {"Effect": "Allow", "Action": actions, "Resource": resources}


DENY_BATCH = {"Effect": "Deny", "Action": ["bedrock:CreateModelInvocationJob"], "Resource": "*"}


class AWS:
    """Validate every request against the installed botocore model before dispatch."""

    def __init__(self, session):
        self.session = session
        self.clients = {}

    def call(self, service, operation, **params):
        from botocore.config import Config
        from botocore.validate import validate_parameters

        if service not in self.clients:
            self.clients[service] = self.session.client(
                service,
                region_name=REGION,
                config=Config(connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 2}),
            )
        client = self.clients[service]
        name = client.meta.method_to_api_mapping[operation]
        validate_parameters(params, client.meta.service_model.operation_model(name).input_shape)
        return getattr(client, operation)(**params)


def missing(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in {
        "NoSuchEntity",
        "NoSuchBucket",
        "404",
        "NotFoundException",
        "ResourceNotFoundException",
    }


def optional(fn):
    try:
        return fn()
    except Exception as error:
        if missing(error):
            return None
        raise


def find(aws, service, operation, result_key, name_key, name, **params):
    for _ in range(50):
        result = aws.call(service, operation, **params)
        for item in result[result_key]:
            if item[name_key] == name:
                return item
        if not result.get("nextToken"):
            return None
        params["nextToken"] = result["nextToken"]
    raise RuntimeError("Resource list pagination exceeded bound")


def wait(get, *, field="status", ready=("READY",), timeout=600):
    deadline = time.monotonic() + timeout
    while True:
        value = get()
        status = value[field]
        if status in ready:
            return value
        if status in {
            "FAILED",
            "DELETE_UNSUCCESSFUL",
            "DELETING",
            "UPDATE_UNSUCCESSFUL",
            "CREATE_UNSUCCESSFUL",
            "STOPPED",
        }:
            raise RuntimeError(f"Resource failed: {json.dumps(value, default=str)}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Resource still {status}; rerun the same command to resume")
        time.sleep(10)


def deploy(aws, *, state_path, runtime_zip, prefix="treehouse-judge", retry_failed_ingestion=False):
    """Apply only via CLI's explicit Kiro gate; injectable for offline SDK checks."""
    module("deploy/judge_runtime/build.py", "judge_build").validate_archive(runtime_zip)
    state_path = Path(state_path)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    prior_kb_id, prior_source_id = state.get("knowledge_base_id"), state.get("data_source_id")
    account = aws.call("sts", "get_caller_identity")["Account"]
    if state and (
        state.get("account") != account or state.get("region") != REGION or state.get("prefix") != prefix
    ):
        raise ValueError("State account, region or prefix mismatch; do not overwrite another deployment")
    state.update(account=account, region=REGION, prefix=prefix, schema_version="treehouse.judge-deploy/1")
    write_json(state_path, state)
    bucket_base = f"{prefix}-{account}-{REGION}"
    # Persist one unpredictable name before any create; ordinary reruns never choose another bucket.
    prior_bucket = state.get("bucket") or state.get("bucket_create_receipt", {}).get("bucket")
    nonce = state.get("bucket_nonce")
    if prior_bucket:
        if prior_bucket == bucket_base and nonce is None:
            bucket = prior_bucket  # Legacy names may be read/reused only when current ownership tags verify.
        elif re.fullmatch(re.escape(bucket_base) + r"-[0-9a-f]{12}", prior_bucket):
            bucket = prior_bucket
            suffix = bucket.rsplit("-", 1)[1]
            if nonce is not None and nonce != suffix:
                raise ValueError("Persisted bucket name and nonce differ")
            nonce = suffix
        else:
            raise ValueError("Persisted bucket name does not match this deployment")
    else:
        nonce = nonce or secrets.token_hex(6)
        if not re.fullmatch(r"[0-9a-f]{12}", nonce):
            raise ValueError("Invalid persisted bucket nonce")
        bucket = f"{bucket_base}-{nonce}"
    if len(bucket) > 63:
        raise ValueError("Deployment bucket name exceeds the S3 limit")
    state.update(bucket=bucket, bucket_nonce=nonce)
    write_json(state_path, state)
    vectors = f"{prefix}-vectors-{account}"
    index = "public-docs"
    runtime_name = prefix.replace("-", "_")
    model_arn = f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL}"
    embed_arn = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"
    bucket_arn = f"arn:aws:s3:::{bucket}"
    vector_arn = f"arn:aws:s3vectors:{REGION}:{account}:bucket/{vectors}"
    index_arn = f"{vector_arn}/index/{index}"
    lambda_arn = f"arn:aws:lambda:{REGION}:{account}:function:{prefix}-tools"

    def save(**values):
        state.update(values)
        write_json(state_path, state)

    def role(suffix, principal, statements):
        name = f"{prefix}-{suffix}"
        arn = f"arn:aws:iam::{account}:role/{name}"
        existing = optional(lambda: aws.call("iam", "get_role", RoleName=name))
        trust = {"Effect": "Allow", "Principal": {"Service": principal}, "Action": "sts:AssumeRole"}
        if principal != "lambda.amazonaws.com":
            trust["Condition"] = {
                "StringEquals": {"aws:SourceAccount": account},
                "ArnLike": {
                    "aws:SourceArn": f"arn:aws:{'bedrock' if principal == 'bedrock.amazonaws.com' else 'bedrock-agentcore'}:{REGION}:{account}:*"
                },
            }
        trust_json = policy([trust])
        if not existing:
            aws.call(
                "iam",
                "create_role",
                RoleName=name,
                AssumeRolePolicyDocument=trust_json,
                Tags=[{"Key": k, "Value": v} for k, v in TAGS.items()],
            )
        elif not all({"Key": k, "Value": v} in existing["Role"].get("Tags", []) for k, v in TAGS.items()):
            raise ValueError(f"Refusing to modify unowned role {name}")
        if existing and existing["Role"].get("AssumeRolePolicyDocument") != json.loads(trust_json):
            raise ValueError(f"Refusing to modify role with unexpected trust: {name}")
        # Only these named project roles/policies are managed. No administrator policy.
        aws.call(
            "iam",
            "put_role_policy",
            RoleName=name,
            PolicyName="treehouse-judge",
            PolicyDocument=policy([*statements, DENY_BATCH]),
        )
        save(**{suffix + "_role_arn": arn})
        return arn

    expected_tags = [{"Key": key, "Value": value} for key, value in TAGS.items()]
    existing_bucket = optional(
        lambda: aws.call("s3", "head_bucket", Bucket=bucket, ExpectedBucketOwner=account)
    )
    if existing_bucket is None:
        if nonce is None:
            raise ValueError("Legacy deployment bucket is missing; manual recovery decision required")
        created = aws.call("s3", "create_bucket", Bucket=bucket)
        receipt = created.get("ResponseMetadata", {})
        save(
            bucket_create_receipt={
                "bucket": bucket,
                "account": account,
                "region": REGION,
                "request_id": receipt.get("RequestId"),
                "http_status": receipt.get("HTTPStatusCode"),
                "diagnostic_only": True,
                "ownership_tags_confirmed": False,
            }
        )
        # A 200 in us-east-1 is not creation proof. Random naming mitigates the create race;
        # acknowledgements never authorize a later adoption of an existing untagged bucket.
        aws.call(
            "s3",
            "put_bucket_tagging",
            Bucket=bucket,
            ExpectedBucketOwner=account,
            Tagging={"TagSet": expected_tags},
        )
    try:
        bucket_tags = aws.call("s3", "get_bucket_tagging", Bucket=bucket, ExpectedBucketOwner=account)[
            "TagSet"
        ]
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") != "NoSuchTagSet":
            raise
        bucket_tags = []
    if not all(tag in bucket_tags for tag in expected_tags):
        raise ValueError(
            "Refusing existing unowned or untagged S3 bucket; acknowledgement is diagnostic only"
        )
    if state.get("bucket_create_receipt"):
        save(
            bucket_create_receipt={
                **state["bucket_create_receipt"],
                "diagnostic_only": True,
                "ownership_tags_confirmed": True,
            }
        )
    aws.call(
        "s3",
        "put_public_access_block",
        Bucket=bucket,
        ExpectedBucketOwner=account,
        PublicAccessBlockConfiguration={
            key: True
            for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")
        },
    )
    aws.call(
        "s3",
        "put_bucket_encryption",
        Bucket=bucket,
        ExpectedBucketOwner=account,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    save(bucket=bucket, vector_bucket=vectors, index_arn=index_arn)
    aws.call(
        "s3",
        "put_object",
        Bucket=bucket,
        Key="public/treehouse-public.md",
        Body=(ROOT / "docs/judge-knowledge/treehouse-public.md").read_bytes(),
        ContentType="text/markdown",
        ExpectedBucketOwner=account,
    )
    if optional(lambda: aws.call("s3vectors", "get_vector_bucket", vectorBucketName=vectors)) is None:
        aws.call("s3vectors", "create_vector_bucket", vectorBucketName=vectors, tags=TAGS)
    elif aws.call("s3vectors", "list_tags_for_resource", resourceArn=vector_arn).get("tags") != TAGS:
        raise ValueError("Refusing to modify unowned vector bucket")
    current_index = optional(
        lambda: aws.call("s3vectors", "get_index", vectorBucketName=vectors, indexName=index)
    )
    if current_index is None:
        aws.call(
            "s3vectors",
            "create_index",
            vectorBucketName=vectors,
            indexName=index,
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
            metadataConfiguration={
                "nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
            },
            tags=TAGS,
        )
    elif any(
        current_index["index"].get(k) != v
        for k, v in {
            "dataType": "float32",
            "dimension": 1024,
            "distanceMetric": "cosine",
            "metadataConfiguration": {
                "nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
            },
        }.items()
    ):
        raise ValueError("Existing vector index configuration differs")
    kb_role = role(
        "kb",
        "bedrock.amazonaws.com",
        [
            allow(["bedrock:InvokeModel"], embed_arn),
            allow(["s3:ListBucket"], bucket_arn),
            allow(["s3:GetObject"], f"{bucket_arn}/public/*"),
            allow(
                [
                    "s3vectors:GetIndex",
                    "s3vectors:QueryVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:PutVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:ListVectors",
                ],
                index_arn,
            ),
        ],
    )
    expected_vector_policy = policy(
        [
            {
                "Effect": "Allow",
                "Principal": {"AWS": kb_role},
                "Action": [
                    "s3vectors:GetIndex",
                    "s3vectors:QueryVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:PutVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:ListVectors",
                ],
                "Resource": index_arn,
            }
        ]
    )
    existing_vector_policy = optional(
        lambda: aws.call("s3vectors", "get_vector_bucket_policy", vectorBucketName=vectors)
    )
    if existing_vector_policy and existing_vector_policy.get("policy"):
        if json.loads(existing_vector_policy["policy"]) != json.loads(expected_vector_policy):
            raise ValueError("Existing vector bucket policy differs; no grants were replaced")
    else:
        aws.call(
            "s3vectors", "put_vector_bucket_policy", vectorBucketName=vectors, policy=expected_vector_policy
        )
    expected_kb_config = {
        "type": "VECTOR",
        "vectorKnowledgeBaseConfiguration": {
            "embeddingModelArn": embed_arn,
            "embeddingModelConfiguration": {
                "bedrockEmbeddingModelConfiguration": {"dimensions": 1024, "embeddingDataType": "FLOAT32"}
            },
        },
    }
    expected_storage = {"type": "S3_VECTORS", "s3VectorsConfiguration": {"indexArn": index_arn}}
    kb = find(aws, "bedrock-agent", "list_knowledge_bases", "knowledgeBaseSummaries", "name", prefix)
    if not kb:
        time.sleep(10)  # New service roles need bounded propagation time.
        kb = aws.call(
            "bedrock-agent",
            "create_knowledge_base",
            name=prefix,
            roleArn=kb_role,
            clientToken=hashlib.sha256((prefix + account + "kb").encode()).hexdigest(),
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": embed_arn,
                    "embeddingModelConfiguration": {
                        "bedrockEmbeddingModelConfiguration": {
                            "dimensions": 1024,
                            "embeddingDataType": "FLOAT32",
                        }
                    },
                },
            },
            storageConfiguration={"type": "S3_VECTORS", "s3VectorsConfiguration": {"indexArn": index_arn}},
            tags=TAGS,
        )["knowledgeBase"]
    kb_id = kb["knowledgeBaseId"]
    save(knowledge_base_id=kb_id)
    kb_readback = wait(
        lambda: aws.call("bedrock-agent", "get_knowledge_base", knowledgeBaseId=kb_id)["knowledgeBase"],
        ready=("ACTIVE",),
    )
    kb_arn = kb_readback["knowledgeBaseArn"]
    kb_tags = aws.call("bedrock-agent", "list_tags_for_resource", resourceArn=kb_arn).get("tags", {})
    if (
        any(kb_tags.get(key) != value for key, value in TAGS.items())
        or kb_readback.get("roleArn") != kb_role
        or kb_readback.get("knowledgeBaseConfiguration") != expected_kb_config
        or kb_readback.get("storageConfiguration") != expected_storage
    ):
        raise ValueError("Existing KB ownership, role, storage or embedding configuration differs")
    expected_source_config = {
        "type": "S3",
        "s3Configuration": {"bucketArn": bucket_arn, "inclusionPrefixes": ["public/"]},
    }
    expected_ingestion_config = {
        "chunkingConfiguration": {
            "chunkingStrategy": "FIXED_SIZE",
            "fixedSizeChunkingConfiguration": {"maxTokens": 300, "overlapPercentage": 10},
        }
    }
    source_items = []
    params = {"knowledgeBaseId": kb_id}
    for _ in range(50):
        page = aws.call("bedrock-agent", "list_data_sources", **params)
        source_items.extend(page["dataSourceSummaries"])
        if not page.get("nextToken"):
            break
        params["nextToken"] = page["nextToken"]
    else:
        raise RuntimeError("Data source pagination exceeded bound")
    if len(source_items) > 1 or (source_items and source_items[0]["name"] != "public-project-note"):
        raise ValueError("KB contains unexpected data sources; refusing unrelated indexed content")
    source = source_items[0] if source_items else None
    if source is None:
        source = aws.call(
            "bedrock-agent",
            "create_data_source",
            knowledgeBaseId=kb_id,
            name="public-project-note",
            dataDeletionPolicy="DELETE",
            dataSourceConfiguration=expected_source_config,
            vectorIngestionConfiguration=expected_ingestion_config,
        )["dataSource"]
    source_id = source["dataSourceId"]
    save(data_source_id=source_id)
    source = wait(
        lambda: aws.call("bedrock-agent", "get_data_source", knowledgeBaseId=kb_id, dataSourceId=source_id)[
            "dataSource"
        ],
        ready=("AVAILABLE",),
    )
    if (
        source.get("knowledgeBaseId") != kb_id
        or source.get("dataDeletionPolicy") != "DELETE"
        or source.get("dataSourceConfiguration") != expected_source_config
        or source.get("vectorIngestionConfiguration") != expected_ingestion_config
    ):
        raise ValueError("Existing data source bucket, prefix, deletion or ingestion configuration differs")
    digest = hashlib.sha256((ROOT / "docs/judge-knowledge/treehouse-public.md").read_bytes()).hexdigest()
    if (
        state.get("ingestion_document_sha256") != digest
        or state.get("ingestion_kb_id", prior_kb_id) != kb_id
        or state.get("ingestion_source_id", prior_source_id) != source_id
    ):
        save(
            ingestion_attempt=1,
            ingestion_job_id=None,
            ingestion_client_token=None,
            ingestion_document_sha256=digest,
            ingested_document_sha256=None,
        )

    save(ingestion_kb_id=kb_id, ingestion_source_id=source_id)

    def ingest_observation():
        attempt = state.get("ingestion_attempt", 1)
        if not state.get("ingestion_job_id"):
            token = (
                state.get("ingestion_client_token")
                or hashlib.sha256(f"{kb_id}:{source_id}:{digest}:{attempt}".encode()).hexdigest()
            )
            save(ingestion_attempt=attempt, ingestion_client_token=token)
            job = aws.call(
                "bedrock-agent",
                "start_ingestion_job",
                knowledgeBaseId=kb_id,
                dataSourceId=source_id,
                clientToken=token,
            )["ingestionJob"]
            save(ingestion_job_id=job["ingestionJobId"])
        job = wait(
            lambda: aws.call(
                "bedrock-agent",
                "get_ingestion_job",
                knowledgeBaseId=kb_id,
                dataSourceId=source_id,
                ingestionJobId=state["ingestion_job_id"],
            )["ingestionJob"],
            ready=("COMPLETE", "FAILED", "STOPPED"),
        )
        if any(
            job.get(key) != value
            for key, value in {
                "knowledgeBaseId": kb_id,
                "dataSourceId": source_id,
                "ingestionJobId": state["ingestion_job_id"],
            }.items()
        ):
            raise ValueError("Ingestion readback identifiers differ from the owned source")
        save(ingestion_last_observation=job)
        return job

    def failed(job):
        return job["status"] != "COMPLETE" or bool(
            job.get("statistics", {}).get("numberOfDocumentsFailed", 0)
        )

    job = ingest_observation()
    if failed(job):
        history = state.get("ingestion_failures", [])
        if not any(item.get("ingestionJobId") == state["ingestion_job_id"] for item in history):
            history.append({**job, "ingestionJobId": state["ingestion_job_id"]})
        save(ingestion_failures=history, ingested_document_sha256=None)
        if not retry_failed_ingestion or state.get("ingestion_attempt", 1) >= 3:
            raise RuntimeError(
                "Ingestion failed; inspect persisted failure evidence; explicit bounded retry required"
            )
        save(
            ingestion_attempt=state.get("ingestion_attempt", 1) + 1,
            ingestion_job_id=None,
            ingestion_client_token=None,
        )
        job = ingest_observation()
        if failed(job):
            save(ingestion_failures=[*history, {**job, "ingestionJobId": state["ingestion_job_id"]}])
            raise RuntimeError("Explicit ingestion retry failed; no further job was started")
    save(ingested_document_sha256=digest)
    log_arn = f"arn:aws:logs:{REGION}:{account}:log-group:/aws/lambda/{prefix}-tools:*"
    lambda_role = role(
        "lambda",
        "lambda.amazonaws.com",
        [
            allow(["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], log_arn),
            allow(["bedrock:Retrieve"], f"arn:aws:bedrock:{REGION}:{account}:knowledge-base/{kb_id}"),
            allow(["bedrock:RetrieveAndGenerate"], "*"),
            allow(["bedrock:InvokeModel"], model_arn),
        ],
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            zipfile.ZipInfo("handler.py"), (ROOT / "deploy/judge_gateway/handler.py").read_bytes()
        )
    function = optional(lambda: aws.call("lambda", "get_function", FunctionName=lambda_arn))
    if not function:
        time.sleep(10)
        aws.call(
            "lambda",
            "create_function",
            FunctionName=f"{prefix}-tools",
            Runtime="python3.12",
            Role=lambda_role,
            Handler="handler.lambda_handler",
            Code={"ZipFile": stream.getvalue()},
            Timeout=75,
            MemorySize=256,
            Architectures=["arm64"],
            Environment={"Variables": {"KNOWLEDGE_BASE_ID": kb_id, "MODEL_ID": MODEL}},
            Tags=TAGS,
        )
    else:
        import base64

        expected_code = base64.b64encode(hashlib.sha256(stream.getvalue()).digest()).decode()
        live = function["Configuration"]
        if (
            live.get("CodeSha256") != expected_code
            or live.get("Role") != lambda_role
            or live.get("Environment", {}).get("Variables") != {"KNOWLEDGE_BASE_ID": kb_id, "MODEL_ID": MODEL}
        ):
            raise ValueError("Existing Lambda differs; review an explicit update rather than overwrite")
    function = wait(
        lambda: aws.call("lambda", "get_function_configuration", FunctionName=lambda_arn),
        field="State",
        ready=("Active",),
    )
    save(
        lambda_arn=lambda_arn,
        lambda_source_sha256=hashlib.sha256(
            (ROOT / "deploy/judge_gateway/handler.py").read_bytes()
        ).hexdigest(),
    )
    gateway_role = role(
        "gateway", "bedrock-agentcore.amazonaws.com", [allow(["lambda:InvokeFunction"], lambda_arn)]
    )
    gateway = find(aws, "bedrock-agentcore-control", "list_gateways", "items", "name", prefix)
    if not gateway:
        time.sleep(10)
        gateway = aws.call(
            "bedrock-agentcore-control",
            "create_gateway",
            name=prefix,
            roleArn=gateway_role,
            protocolType="MCP",
            authorizerType="AWS_IAM",
            protocolConfiguration={"mcp": {"supportedVersions": ["2025-03-26"]}},
            tags=TAGS,
        )
    gateway_id = gateway["gatewayId"]
    save(gateway_id=gateway_id)
    gateway = wait(lambda: aws.call("bedrock-agentcore-control", "get_gateway", gatewayIdentifier=gateway_id))
    gateway_tags = aws.call(
        "bedrock-agentcore-control", "list_tags_for_resource", resourceArn=gateway["gatewayArn"]
    ).get("tags", {})
    if (
        any(gateway_tags.get(key) != value for key, value in TAGS.items())
        or gateway.get("roleArn") != gateway_role
        or gateway.get("protocolType") != "MCP"
        or gateway.get("authorizerType") != "AWS_IAM"
        or gateway.get("protocolConfiguration") != {"mcp": {"supportedVersions": ["2025-03-26"]}}
        or gateway.get("authorizerConfiguration")
    ):
        raise ValueError("Existing Gateway ownership, role, MCP or IAM configuration differs")
    target = find(
        aws,
        "bedrock-agentcore-control",
        "list_gateway_targets",
        "items",
        "name",
        "project",
        gatewayIdentifier=gateway_id,
    )
    if not target:
        target = aws.call(
            "bedrock-agentcore-control",
            "create_gateway_target",
            gatewayIdentifier=gateway_id,
            name="project",
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {
                            "inlinePayload": module("deploy/judge_gateway/handler.py", "judge_lambda").TOOLS
                        },
                    }
                }
            },
            credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        )
    target_id = target["targetId"]
    target_readback = wait(
        lambda: aws.call(
            "bedrock-agentcore-control",
            "get_gateway_target",
            gatewayIdentifier=gateway_id,
            targetId=target_id,
        )
    )
    target_lambda = target_readback["targetConfiguration"]["mcp"]["lambda"]
    if target_readback.get("credentialProviderConfigurations") != [
        {"credentialProviderType": "GATEWAY_IAM_ROLE"}
    ]:
        raise ValueError("Existing Gateway target credentials differ")
    if target_lambda != {
        "lambdaArn": lambda_arn,
        "toolSchema": {
            "inlinePayload": module("deploy/judge_gateway/handler.py", "judge_lambda_check").TOOLS
        },
    }:
        raise ValueError("Existing Gateway target differs from the three owned Lambda tools")
    save(gateway_target_id=target_id, gateway_url=gateway["gatewayUrl"])
    runtime_role = role(
        "runtime",
        "bedrock-agentcore.amazonaws.com",
        [
            allow(["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], model_arn),
            allow(["bedrock-agentcore:InvokeGateway"], gateway["gatewayArn"]),
            allow(["s3:GetObject"], f"{bucket_arn}/runtime/*"),
            allow(["s3:ListBucket"], bucket_arn),
            allow(
                [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                f"arn:aws:logs:{REGION}:{account}:log-group:/aws/bedrock-agentcore/runtimes/{runtime_name}*:*",
            ),
        ],
    )
    artifact_digest = hashlib.sha256(Path(runtime_zip).read_bytes()).hexdigest()
    key = f"runtime/{artifact_digest}.zip"
    aws.call(
        "s3",
        "put_object",
        Bucket=bucket,
        Key=key,
        Body=Path(runtime_zip).read_bytes(),
        ContentType="application/zip",
        ExpectedBucketOwner=account,
    )
    runtime = find(
        aws,
        "bedrock-agentcore-control",
        "list_agent_runtimes",
        "agentRuntimes",
        "agentRuntimeName",
        runtime_name,
    )
    if not runtime:
        time.sleep(10)
        runtime = aws.call(
            "bedrock-agentcore-control",
            "create_agent_runtime",
            agentRuntimeName=runtime_name,
            roleArn=runtime_role,
            agentRuntimeArtifact={
                "codeConfiguration": {
                    "code": {"s3": {"bucket": bucket, "prefix": key}},
                    "runtime": "PYTHON_3_12",
                    "entryPoint": ["main.py"],
                }
            },
            networkConfiguration={"networkMode": "PUBLIC"},
            protocolConfiguration={"serverProtocol": "HTTP"},
            lifecycleConfiguration={"idleRuntimeSessionTimeout": 60, "maxLifetime": 300},
            environmentVariables={
                "GATEWAY_URL": gateway["gatewayUrl"],
                "GATEWAY_ID": gateway_id,
                "KNOWLEDGE_BASE_ID": kb_id,
                "MODEL_ID": MODEL,
                "AWS_DEFAULT_REGION": REGION,
            },
            tags=TAGS,
        )
    elif state.get("runtime_artifact_sha256") not in (None, artifact_digest):
        raise ValueError("Runtime artifact changed; review an explicit update rather than overwrite")
    save(runtime_id=runtime["agentRuntimeId"], runtime_artifact_sha256=artifact_digest)
    runtime = wait(
        lambda: aws.call("bedrock-agentcore-control", "get_agent_runtime", agentRuntimeId=state["runtime_id"])
    )
    if (
        runtime.get("agentRuntimeArtifact", {})
        .get("codeConfiguration", {})
        .get("code", {})
        .get("s3", {})
        .get("prefix")
        != key
    ):
        raise ValueError("Existing Runtime artifact differs; review an explicit update rather than overwrite")
    runtime_tags = aws.call(
        "bedrock-agentcore-control", "list_tags_for_resource", resourceArn=runtime["agentRuntimeArn"]
    ).get("tags", {})
    expected_artifact = {
        "codeConfiguration": {
            "code": {"s3": {"bucket": bucket, "prefix": key}},
            "runtime": "PYTHON_3_12",
            "entryPoint": ["main.py"],
        }
    }
    if (
        any(runtime_tags.get(key) != value for key, value in TAGS.items())
        or runtime.get("roleArn") != runtime_role
        or runtime.get("agentRuntimeArtifact") != expected_artifact
        or runtime.get("protocolConfiguration") != {"serverProtocol": "HTTP"}
        or runtime.get("networkConfiguration") != {"networkMode": "PUBLIC"}
        or runtime.get("lifecycleConfiguration") != {"idleRuntimeSessionTimeout": 60, "maxLifetime": 300}
        or not runtime["agentRuntimeArn"].startswith(f"arn:aws:bedrock-agentcore:{REGION}:{account}:runtime/")
    ):
        raise ValueError("Existing Runtime ownership, role, artifact, protocol, network or lifecycle differs")
    if runtime.get("authorizerConfiguration"):
        raise ValueError("Expected default IAM Runtime authorization")
    env = runtime["environmentVariables"]
    if any(
        env.get(k) != v
        for k, v in {
            "GATEWAY_URL": gateway["gatewayUrl"],
            "GATEWAY_ID": gateway_id,
            "KNOWLEDGE_BASE_ID": kb_id,
            "MODEL_ID": MODEL,
        }.items()
    ):
        raise ValueError("Runtime readback does not match requested resources")
    config = {
        "schema_version": "treehouse.judge-config/1",
        "region": REGION,
        "runtime_arn": runtime["agentRuntimeArn"],
        "gateway_url": gateway["gatewayUrl"],
        "gateway_id": gateway_id,
        "knowledge_base_id": kb_id,
        "model_id": MODEL,
    }
    write_json(state_path.parent / "judge-config.json", config)
    save(runtime_arn=runtime["agentRuntimeArn"], status="READY_FOR_LIVE_SMOKE")
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--kiro", action="store_true", help="Confirm execution in the authorized Kiro AWS terminal"
    )
    parser.add_argument("--acknowledge-spend", type=int, choices=[25])
    parser.add_argument("--prefix", default="treehouse-judge")
    parser.add_argument(
        "--retry-failed-ingestion",
        action="store_true",
        help="After diagnosis, start at most one new ingestion attempt; maximum three total",
    )
    parser.add_argument("--state", type=Path, default=ROOT / "outputs/judge/deploy-state.json")
    parser.add_argument("--runtime-zip", type=Path)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,24}", args.prefix):
        parser.error("Prefix must be 3–25 lowercase letters, numbers or hyphens")
    if not args.apply:
        print(
            json.dumps(
                {
                    "mode": "PLAN_NO_AWS_CALLS",
                    "region": REGION,
                    "resources": [
                        "private S3 source/code bucket",
                        "S3 vector bucket + 1024-d cosine index",
                        "Bedrock KB + public-note ingestion",
                        "four scoped service roles with batch Deny",
                        "ARM64 Lambda with three tools",
                        "AWS_IAM MCP Gateway + Lambda target",
                        "ARM64 Python 3.12 CodeZip Runtime",
                    ],
                    "model_id": MODEL,
                    "working_budget_usd": 15,
                    "stop_usd": 25,
                    "existing_account_warn_usd": 350,
                    "existing_account_hard_stop_usd": 450,
                    "live_proof": "pending Kiro deploy + explicit smoke; this plan proves no AWS service state",
                },
                indent=2,
            )
        )
        return
    if sys.platform == "darwin" or not args.kiro or args.acknowledge_spend != 25 or not args.runtime_zip:
        parser.error(
            "Apply requires a non-Mac Kiro terminal, --kiro --acknowledge-spend 25 and --runtime-zip"
        )
    import boto3

    config = deploy(
        AWS(boto3.Session(region_name=REGION)),
        state_path=args.state,
        runtime_zip=args.runtime_zip,
        prefix=args.prefix,
        retry_failed_ingestion=args.retry_failed_ingestion,
    )
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
