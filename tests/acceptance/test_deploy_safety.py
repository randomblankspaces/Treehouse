"""Offline independent deploy safety acceptance; baseline fake validates botocore inputs."""

import base64
import hashlib
import importlib.util
import json
import os
import zipfile
from pathlib import Path

import botocore.session
import pytest
from botocore import xform_name as xform
from botocore.exceptions import ClientError
from botocore.validate import validate_parameters

from treehouse.paths import repo_root

ROOT = Path(os.environ.get("TREEHOUSE_DEPLOY_ROOT", repo_root()))
spec = importlib.util.spec_from_file_location("judge_deploy_acceptance", ROOT / "scripts/judge_deploy.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Fake:
    def __init__(self):
        self.models = botocore.session.get_session()
        self.calls = []
        self.roles = {}
        self.bucket = None
        self.vectors = None
        self.index = None
        self.kb = None
        self.source = None
        self.function = None
        self.gateway = None
        self.target = None
        self.runtime = None

    def call(self, svc, op, **p):
        model = self.models.get_service_model(svc)
        names = {xform(name): name for name in model.operation_names}
        validate_parameters(p, model.operation_model(names[op]).input_shape)
        self.calls.append((svc, op, p))

        def need(value):
            if value is None:
                raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, op)
            return value

        if op == "get_caller_identity":
            return {"Account": "123456789012"}
        if op == "head_bucket":
            return need(self.bucket)
        if op == "create_bucket":
            self.bucket = {"ResponseMetadata": {}}
            return {}
        if op == "get_bucket_tagging":
            return {"TagSet": [{"Key": k, "Value": v} for k, v in mod.TAGS.items()]}
        if op == "list_tags_for_resource":
            return {"tags": mod.TAGS}
        if op == "get_vector_bucket":
            return need(self.vectors)
        if op == "create_vector_bucket":
            self.vectors = {}
            return {}
        if op == "get_index":
            return {"index": need(self.index)}
        if op == "create_index":
            self.index = p
            return {}
        if op == "get_role":
            return {"Role": need(self.roles.get(p["RoleName"]))}
        if op == "create_role":
            self.roles[p["RoleName"]] = {
                "Tags": p["Tags"],
                "AssumeRolePolicyDocument": json.loads(p["AssumeRolePolicyDocument"]),
            }
            return {}
        if op == "list_knowledge_bases":
            return {"knowledgeBaseSummaries": [self.kb] if self.kb else []}
        if op == "create_knowledge_base":
            self.kb = {"knowledgeBaseId": "KB12345678", **p, "status": "ACTIVE"}
            return {"knowledgeBase": self.kb}
        if op == "get_knowledge_base":
            return {"knowledgeBase": need(self.kb)}
        if op == "list_data_sources":
            return {"dataSourceSummaries": [self.source] if self.source else []}
        if op == "create_data_source":
            self.source = {"dataSourceId": "DS12345678", **p}
            return {"dataSource": self.source}
        if op == "start_ingestion_job":
            return {"ingestionJob": {"ingestionJobId": "JOB1234567"}}
        if op == "get_ingestion_job":
            return {"ingestionJob": {"status": "COMPLETE", "statistics": {"numberOfDocumentsFailed": 0}}}
        if op == "get_function":
            return {"Configuration": need(self.function)}
        if op == "create_function":
            self.function = {
                "State": "Active",
                "Role": p["Role"],
                "Environment": p["Environment"],
                "CodeSha256": base64.b64encode(hashlib.sha256(p["Code"]["ZipFile"]).digest()).decode(),
            }
            return {}
        if op == "get_function_configuration":
            return need(self.function)
        if op == "list_gateways":
            return {"items": [self.gateway] if self.gateway else []}
        if op == "create_gateway":
            self.gateway = {
                "gatewayId": "judge-gw123",
                "gatewayArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/judge-gw123",
                "gatewayUrl": "https://judge-gw123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
                "status": "READY",
                **p,
            }
            return self.gateway
        if op == "get_gateway":
            return need(self.gateway)
        if op == "list_gateway_targets":
            return {"items": [self.target] if self.target else []}
        if op == "create_gateway_target":
            self.target = {"targetId": "target1234", "status": "READY", **p}
            return self.target
        if op == "get_gateway_target":
            return need(self.target)
        if op == "list_agent_runtimes":
            return {"agentRuntimes": [self.runtime] if self.runtime else []}
        if op == "create_agent_runtime":
            self.runtime = {
                "agentRuntimeId": "judge-runtime123",
                "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/judge-runtime123",
                "status": "READY",
                **p,
            }
            return self.runtime
        if op == "get_agent_runtime":
            return need(self.runtime)
        if op in {
            "put_object",
            "put_public_access_block",
            "put_bucket_encryption",
            "put_bucket_tagging",
            "put_vector_bucket_policy",
            "put_role_policy",
        }:
            return {}
        raise AssertionError((svc, op, p))


class SafetyFake(Fake):
    def __init__(self):
        super().__init__()
        self.vector_policy = None
        self.bucket_tags = None
        self.ownership = {}
        self.job_status = "COMPLETE"
        self.jobs = []
        self.job_results = {}
        self.extra_sources = []
        self.interrupt_tag = False

    def call(self, svc, op, **p):
        # Retain the baseline fake's botocore input shape validation for *every* operation.
        model = self.models.get_service_model(svc)
        names = {xform(name): name for name in model.operation_names}
        validate_parameters(p, model.operation_model(names[op]).input_shape)
        if op == "create_bucket":
            super().call(svc, op, **p)
            return {"ResponseMetadata": {"RequestId": "owned-creation-request", "HTTPStatusCode": 200}}
        if op == "create_knowledge_base":
            out = super().call(svc, op, **p)
            self.kb["knowledgeBaseArn"] = "arn:aws:bedrock:us-east-1:123456789012:knowledge-base/KB12345678"
            return out
        if op == "get_bucket_tagging":
            self.calls.append((svc, op, p))
            if self.bucket_tags is None:
                raise ClientError({"Error": {"Code": "NoSuchTagSet"}}, op)
            return {"TagSet": self.bucket_tags}
        if op == "put_bucket_tagging":
            self.calls.append((svc, op, p))
            if self.interrupt_tag:
                self.interrupt_tag = False
                raise RuntimeError("simulated interruption before tag")
            self.bucket_tags = p["Tagging"]["TagSet"]
            return {}
        if op == "list_tags_for_resource":
            self.calls.append((svc, op, p))
            arn = p.get("resourceArn", p.get("resourceARN", ""))
            return {"tags": self.ownership.get(arn, mod.TAGS)}
        if op == "get_vector_bucket_policy":
            self.calls.append((svc, op, p))
            if self.vector_policy is None:
                raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, op)
            return {"policy": self.vector_policy}
        if op == "put_vector_bucket_policy":
            self.calls.append((svc, op, p))
            self.vector_policy = p["policy"]
            return {}
        if op == "create_data_source":
            out = super().call(svc, op, **p)
            self.source["status"] = "AVAILABLE"
            return out
        if op == "get_data_source":
            self.calls.append((svc, op, p))
            return {"dataSource": self.source}
        if op == "list_data_sources" and self.extra_sources:
            self.calls.append((svc, op, p))
            return {"dataSourceSummaries": ([self.source] if self.source else []) + self.extra_sources}
        if op == "start_ingestion_job":
            self.calls.append((svc, op, p))
            self.jobs.append(p.copy())
            job_id = f"JOB{len(self.jobs):07d}"
            self.job_results[job_id] = self.job_status
            return {"ingestionJob": {"ingestionJobId": job_id}}
        if op == "get_ingestion_job":
            self.calls.append((svc, op, p))
            status = self.job_results[p["ingestionJobId"]]
            return {
                "ingestionJob": {
                    "knowledgeBaseId": p["knowledgeBaseId"],
                    "dataSourceId": p["dataSourceId"],
                    "ingestionJobId": p["ingestionJobId"],
                    "status": status,
                    "failureReasons": ["fixture failure"] if status == "FAILED" else [],
                    "statistics": {"numberOfDocumentsFailed": 0},
                }
            }
        return super().call(svc, op, **p)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name in ("main.py", "strands/__init__.py", "boto3/__init__.py"):
            z.writestr(name, "# offline fixture")
    return SafetyFake(), {"state_path": tmp_path / "state.json", "runtime_zip": archive}


def test_foreign_untagged_bucket_not_adopted(setup):
    aws, args = setup
    aws.bucket = {"ResponseMetadata": {}}
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(
        op in {"put_bucket_tagging", "put_object", "put_bucket_encryption"} for _, op, _ in aws.calls
    )


def test_interrupted_tagging_after_creation_ack_requires_proof(setup):
    aws, args = setup
    aws.interrupt_tag = True
    with pytest.raises(RuntimeError):
        mod.deploy(aws, **args)
    assert json.loads(args["state_path"].read_text())  # creation proof persisted before tag
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(
        op in {"put_bucket_tagging", "put_object", "put_bucket_encryption", "put_public_access_block"}
        for _, op, _ in aws.calls
    )


def test_different_vector_policy_is_never_overwritten(setup):
    aws, args = setup
    foreign = '{"Version":"2012-10-17","Statement":[{"Sid":"keep-existing-grant"}]}'
    aws.vector_policy = foreign
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert aws.vector_policy == foreign
    assert not any(op == "put_vector_bucket_policy" for _, op, _ in aws.calls)


def test_failed_ingestion_requires_explicit_single_retry(setup):
    aws, args = setup
    aws.job_status = "FAILED"
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert len(aws.jobs) == 1
    before = args["state_path"].read_text()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert len(aws.jobs) == 1
    assert "fail" in before.lower()
    aws.job_status = "COMPLETE"
    mod.deploy(aws, **args, retry_failed_ingestion=True)
    assert len(aws.jobs) == 2
    assert aws.jobs[0]["clientToken"] != aws.jobs[1]["clientToken"]
    mod.deploy(aws, **args, retry_failed_ingestion=True)
    assert len(aws.jobs) == 2


@pytest.mark.parametrize("resource", ["knowledge_base", "gateway", "runtime"])
def test_existing_foreign_resource_is_not_adopted(setup, resource):
    aws, args = setup
    mod.deploy(aws, **args)
    obj = {"knowledge_base": aws.kb, "gateway": aws.gateway, "runtime": aws.runtime}[resource]
    arn = obj.get("knowledgeBaseArn") or obj.get("gatewayArn") or obj.get("agentRuntimeArn")
    assert arn, f"{resource} fake must return ARN for ownership readback"
    aws.ownership[arn] = {"other": "owner"}
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(
        op in {"start_ingestion_job", "create_gateway_target", "update_agent_runtime"}
        for _, op, _ in aws.calls
    )


@pytest.mark.parametrize(
    "resource,field",
    [
        ("knowledge_base", "roleArn"),
        ("knowledge_base", "storageConfiguration"),
        ("knowledge_base", "knowledgeBaseConfiguration"),
        ("gateway", "roleArn"),
        ("gateway", "protocolType"),
        ("runtime", "roleArn"),
        ("runtime", "networkConfiguration"),
        ("runtime", "protocolConfiguration"),
    ],
)
def test_existing_owned_resource_config_collision_fails_closed(setup, resource, field):
    aws, args = setup
    mod.deploy(aws, **args)
    obj = {"knowledge_base": aws.kb, "gateway": aws.gateway, "runtime": aws.runtime}[resource]
    assert field in obj, f"fixture missing {resource}.{field}"
    obj[field] = "foreign-configuration" if isinstance(obj[field], str) else {"foreign": "configuration"}
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(
        op in {"start_ingestion_job", "create_gateway_target", "update_agent_runtime"}
        for _, op, _ in aws.calls
    )


@pytest.mark.parametrize(
    "field", ["dataSourceConfiguration", "vectorIngestionConfiguration", "dataDeletionPolicy"]
)
def test_data_source_config_collision_stops_ingestion(setup, field):
    aws, args = setup
    mod.deploy(aws, **args)
    assert field in aws.source, f"fixture missing source.{field}"
    aws.source[field] = (
        "foreign-configuration" if isinstance(aws.source[field], str) else {"foreign": "configuration"}
    )
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(op == "start_ingestion_job" for _, op, _ in aws.calls)


def test_unexpected_additional_source_stops_ingestion(setup):
    aws, args = setup
    mod.deploy(aws, **args)
    aws.extra_sources = [{"name": "unrelated", "dataSourceId": "DS87654321"}]
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(op == "start_ingestion_job" for _, op, _ in aws.calls)


def test_gateway_target_credential_mismatch_stops_adoption(setup):
    aws, args = setup
    mod.deploy(aws, **args)
    assert "credentialProviderConfigurations" in aws.target
    aws.target["credentialProviderConfigurations"] = [{"credentialProviderType": "OAUTH"}]
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(op == "create_gateway_target" for _, op, _ in aws.calls)


def test_stale_creation_ack_does_not_adopt_replaced_untagged_bucket(setup):
    aws, args = setup
    aws.interrupt_tag = True
    with pytest.raises(RuntimeError):
        mod.deploy(aws, **args)
    # The previous bucket was deleted and an unrelated bucket now occupies that name.
    aws.bucket = {"ResponseMetadata": {}}
    aws.bucket_tags = None
    aws.calls.clear()
    with pytest.raises((ValueError, RuntimeError)):
        mod.deploy(aws, **args)
    assert not any(
        op in {"put_bucket_tagging", "put_object", "put_bucket_encryption", "put_public_access_block"}
        for _, op, _ in aws.calls
    )
