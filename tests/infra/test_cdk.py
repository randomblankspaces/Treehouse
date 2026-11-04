"""T3: CDK assertions for the AWS prototype. Synthesised offline with bundling skipped (no uv/docker/network)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

cdk = pytest.importorskip("aws_cdk", reason="needs the infra extra: uv sync --extra infra")
if shutil.which("node") is None:
    pytest.skip("aws-cdk-lib needs node", allow_module_level=True)

from aws_cdk.assertions import Match, Template  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra"))
from treehouse_infra import EvalStack, RunStoreStack  # noqa: E402


def _app():
    return cdk.App(context={"aws:cdk:bundling-stacks": []})


@pytest.fixture(scope="module")
def store():
    return Template.from_stack(RunStoreStack(_app(), "S"))


@pytest.fixture(scope="module")
def evals():
    return Template.from_stack(EvalStack(_app(), "E"))


def _logical_id(t, rtype, props):
    found = t.find_resources(rtype, {"Properties": props})
    assert len(found) == 1, found
    return next(iter(found))


def test_run_store_object_lock_defaults_to_compliance_retention(store):
    store.has_resource_properties("AWS::S3::Bucket", {
        "ObjectLockEnabled": True,
        "ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled",
                                    "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 1}}},
        "VersioningConfiguration": {"Status": "Enabled"},
        "PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "RestrictPublicBuckets": True},
    })


def test_key_bucket_is_kms_encrypted_and_denies_worker(store):
    key_bucket = _logical_id(store, "AWS::S3::Bucket", {"BucketEncryption": {"ServerSideEncryptionConfiguration": [
        Match.object_like({"ServerSideEncryptionByDefault": Match.object_like({"SSEAlgorithm": "aws:kms"})})]}})
    worker = _logical_id(store, "AWS::IAM::Role", {"Description": Match.string_like_regexp("worker")})
    deny = Match.object_like({"Sid": "DenyWorker", "Effect": "Deny", "Action": "s3:*",
                              "Principal": {"AWS": {"Fn::GetAtt": [worker, "Arn"]}}})
    store.has_resource_properties("AWS::S3::BucketPolicy", {
        "Bucket": {"Ref": key_bucket}, "PolicyDocument": {"Statement": Match.array_with([deny])}})
    store.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True, "KeyPolicy": {"Statement": Match.array_with([
        Match.object_like({"Effect": "Deny", "Action": "kms:*",
                           "Principal": {"AWS": {"Fn::GetAtt": [worker, "Arn"]}}})])}})


def test_worker_cannot_delete_or_bypass_governance(store):
    for pid, pol in store.find_resources("AWS::IAM::Policy").items():
        text = str(pol)
        if "WorkerRole" in text:
            assert "s3:DeleteObject" not in text and "BypassGovernanceRetention" not in text, pid


def test_evaluators_registered_against_the_lambda(evals):
    fns = evals.find_resources("AWS::Lambda::Function", {"Properties": {
        "Handler": "treehouse.aws.lambda_evaluator.handler", "Runtime": "python3.12"}})
    assert len(fns) == 2
    for name, level in (("treehouse_rules", "TRACE"), ("treehouse_guard", "SESSION")):
        fn = next(f for f in fns if f.startswith(name.split("_")[1].title()))
        evals.has_resource_properties("AWS::BedrockAgentCore::Evaluator", {
            "EvaluatorName": name, "Level": level,
            "EvaluatorConfig": {"CodeBased": {"LambdaConfig": Match.object_like(
                {"LambdaArn": {"Fn::GetAtt": [fn, "Arn"]}})}}})
    evals.has_resource_properties("AWS::Lambda::Permission", {"Principal": "bedrock-agentcore.amazonaws.com"})


def test_online_eval_off_by_default(evals):
    # The online config references a hosted-agent log group that must already exist; the control plane
    # validates it at create time even though the config is DISABLED. We have no runtime yet (KA3), so the
    # config is opt-in via with_online / -c online=true and absent from the default stack.
    evals.resource_count_is("AWS::BedrockAgentCore::OnlineEvaluationConfig", 0)


def test_online_eval_disabled_and_parameterised_when_opted_in():
    t = Template.from_stack(EvalStack(_app(), "EOnline", with_online=True))
    t.has_resource_properties("AWS::BedrockAgentCore::OnlineEvaluationConfig", Match.object_like({
        "OnlineEvaluationConfigName": "treehouse_online", "ExecutionStatus": "DISABLED",
        "DataSourceConfig": {"CloudWatchLogs": {"LogGroupNames": [{"Ref": "AgentLogGroup"}],
                                                "ServiceNames": [{"Ref": "AgentServiceName"}]}},
    }))


def test_log_groups_have_short_retention(evals):
    evals.has_resource_properties("AWS::Logs::LogGroup", {"RetentionInDays": 7})


def test_agentcore_can_be_left_out():
    t = Template.from_stack(EvalStack(_app(), "E2", with_agentcore=False))
    t.resource_count_is("AWS::BedrockAgentCore::Evaluator", 0)
    t.resource_count_is("AWS::Lambda::Function", 2)


def test_dev_stack_can_opt_into_governance_mode():
    t = Template.from_stack(RunStoreStack(_app(), "G", lock_mode="governance", retention_days=1))
    t.has_resource_properties("AWS::S3::Bucket", {
        "ObjectLockConfiguration": {"Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 1}}}})
