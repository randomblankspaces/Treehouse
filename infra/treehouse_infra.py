"""Treehouse AWS prototype as CDK stacks (A4/A10 of docs/design/SYSTEM-DESIGN.md).

* ``RunStoreStack``: the sealed run store (S3 versioned + Object Lock GOVERNANCE with a default retention, so
  every new version is locked), the KMS-encrypted key bucket with an explicit Deny for the worker role (bucket
  policy and key policy), and the worker and grader roles.
* ``EvalStack``: the Treehouse code-based evaluator Lambda code (``treehouse.aws.lambda_evaluator.handler``) as two
  functions with their AgentCore Evaluator registrations (TRACE rules, SESSION guard), and an online evaluation config that is
  DISABLED by default and reads a log group given as a stack parameter.

``cdk synth`` needs no credentials. Pass ``-c agentcore=false`` to leave out the AgentCore resources where the
service is unavailable, and ``-c retention_days=N`` to change the default Object Lock retention (1 day).
"""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
from pathlib import Path

import jsii
from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    CfnParameter,
    Duration,
    ILocalBundling,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

SRC = Path(__file__).resolve().parents[1] / "src"
PYDANTIC = f"pydantic=={importlib.metadata.version('pydantic')}"  # same version the tests ran with
LAMBDA_TIMEOUT = Duration.seconds(60)


@jsii.implements(ILocalBundling)
class _UvBundle:
    """Bundle without docker (the Kiro terminal may have none): manylinux pydantic wheels plus src/treehouse."""

    def try_bundle(self, output_dir: str, *_args, **_kw) -> bool:
        uv = shutil.which("uv")
        if uv is None:
            return False  # CDK falls back to the docker bundling image
        subprocess.run([uv, "pip", "install", "--quiet", "--target", output_dir, "--python-version", "3.12",
                        "--python-platform", "x86_64-manylinux2014", "--only-binary", ":all:", PYDANTIC], check=True)
        shutil.copytree(SRC / "treehouse", Path(output_dir) / "treehouse",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return True


def evaluator_code() -> lambda_.Code:
    return lambda_.Code.from_asset(str(SRC), exclude=["**/__pycache__"], bundling=BundlingOptions(
        image=lambda_.Runtime.PYTHON_3_12.bundling_image,
        command=["bash", "-c", f"pip install -q '{PYDANTIC}' -t /asset-output && cp -r treehouse /asset-output/"],
        local=_UvBundle()))


class RunStoreStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, retention_days: int = 1, **kw) -> None:
        super().__init__(scope, cid, **kw)
        common = dict(block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True, versioned=True,
                      removal_policy=RemovalPolicy.RETAIN)
        self.run_store = s3.Bucket(
            self, "RunStore", encryption=s3.BucketEncryption.S3_MANAGED, object_lock_enabled=True,
            object_lock_default_retention=s3.ObjectLockRetention.governance(Duration.days(retention_days)),
            **common)

        # Sandbox roles: anyone in the account may assume them; their policies, not the trust, do the work.
        self.worker_role = iam.Role(self, "WorkerRole", assumed_by=iam.AccountRootPrincipal(),
                                    description="Treehouse worker: Bedrock, run-store write-once; never the key bucket")
        self.grader_role = iam.Role(self, "GraderRole", assumed_by=iam.AccountRootPrincipal(),
                                    description="Treehouse grader: reads runs and keys")
        self.run_store.grant_read(self.worker_role)
        self.run_store.grant_put(self.worker_role)
        self.worker_role.add_to_policy(iam.PolicyStatement(  # sealing PUTs carry per-object lock headers
            actions=["s3:PutObjectRetention"], resources=[self.run_store.arn_for_objects("*")]))
        self.worker_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], resources=["*"]))
        self.run_store.grant_read(self.grader_role)

        self.key_kms = kms.Key(self, "KeyBucketKey", enable_key_rotation=True, removal_policy=RemovalPolicy.RETAIN,
                               description="Treehouse key bucket")
        self.key_bucket = s3.Bucket(self, "KeyBucket", encryption=s3.BucketEncryption.KMS,
                                    encryption_key=self.key_kms, bucket_key_enabled=True, **common)
        worker = iam.ArnPrincipal(self.worker_role.role_arn)
        self.key_bucket.add_to_resource_policy(iam.PolicyStatement(
            sid="DenyWorker", effect=iam.Effect.DENY, principals=[worker], actions=["s3:*"],
            resources=[self.key_bucket.bucket_arn, self.key_bucket.arn_for_objects("*")]))
        self.key_kms.add_to_resource_policy(iam.PolicyStatement(
            sid="DenyWorker", effect=iam.Effect.DENY, principals=[worker], actions=["kms:*"], resources=["*"]))
        self.key_bucket.grant_read(self.grader_role)

        for name, value in (("RunStoreBucketName", self.run_store.bucket_name),
                            ("KeyBucketName", self.key_bucket.bucket_name),
                            ("WorkerRoleArn", self.worker_role.role_arn),
                            ("GraderRoleArn", self.grader_role.role_arn)):
            CfnOutput(self, name, value=value)


class EvalStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, with_agentcore: bool = True, **kw) -> None:
        super().__init__(scope, cid, **kw)
        code = evaluator_code()  # one asset; two functions, because the L2 Evaluator adds a fixed-id invoke
        fns = {}                 # permission to its Lambda, so one function cannot back two evaluators
        for name in ("rules", "guard"):
            fns[name] = lambda_.Function(
                self, f"{name.title()}Fn", runtime=lambda_.Runtime.PYTHON_3_12,
                architecture=lambda_.Architecture.X86_64, handler="treehouse.aws.lambda_evaluator.handler",
                code=code, timeout=LAMBDA_TIMEOUT, memory_size=512,
                log_group=logs.LogGroup(self, f"{name.title()}Logs", retention=logs.RetentionDays.ONE_WEEK,
                                        removal_policy=RemovalPolicy.DESTROY),
                description=f"Treehouse {name} checks as an AgentCore code-based evaluator")
            CfnOutput(self, f"{name.title()}FunctionArn", value=fns[name].function_arn)
        self.functions = fns
        if not with_agentcore:
            return

        def config(name: str) -> agentcore.EvaluatorConfig:
            return agentcore.EvaluatorConfig.code_based(lambda_function=fns[name], timeout=LAMBDA_TIMEOUT)

        self.rules = agentcore.Evaluator(self, "RulesEvaluator", evaluator_name="treehouse_rules",
                                         level=agentcore.EvaluationLevel.TRACE, evaluator_config=config("rules"),
                                         description="R1 schema, R2 in-AOI, R4 evidence-in-trace per trial")
        self.guard = agentcore.Evaluator(self, "GuardEvaluator", evaluator_name="treehouse_guard",
                                         level=agentcore.EvaluationLevel.SESSION, evaluator_config=config("guard"),
                                         description="forbidden-source access and cost/tool-call/byte limits")
        agent_logs = CfnParameter(self, "AgentLogGroup", default="/aws/bedrock-agentcore/runtimes/treehouse-DEFAULT",
                                  description="Log group with the hosted agent's spans (online eval only)")
        agent_service = CfnParameter(self, "AgentServiceName", default="treehouse.DEFAULT",
                                     description="service.name of the hosted agent's spans")
        # Both evaluators are reference-free, so they may run online; the config ships DISABLED (KA3 enables it).
        self.online = agentcore.OnlineEvaluationConfig(
            self, "OnlineEval", online_evaluation_config_name="treehouse_online",
            data_source=agentcore.DataSourceConfig.from_cloud_watch_logs(
                log_group_names=[agent_logs.value_as_string], service_names=[agent_service.value_as_string]),
            evaluators=[agentcore.EvaluatorSelector.custom(self.rules), agentcore.EvaluatorSelector.custom(self.guard)],
            execution_status=agentcore.ExecutionStatus.DISABLED, sampling_percentage=10,
            description="Treehouse checks over a hosted agent's live sessions")
        for name, value in (("RulesEvaluatorId", self.rules.evaluator_id),
                            ("GuardEvaluatorId", self.guard.evaluator_id),
                            ("OnlineEvalConfigId", self.online.online_evaluation_config_id)):
            CfnOutput(self, name, value=value)
