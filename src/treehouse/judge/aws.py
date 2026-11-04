"""One explicit, bounded Runtime invocation. AWS dependencies are optional and lazy."""

import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

MAX_RESPONSE_BYTES = 1_000_000


def invoke_runtime(config: dict, prompt: str, *, client=None) -> dict:
    """Return Runtime JSON plus metadata from its real AWS transport response.

    Raises on transport errors, malformed responses and mismatched resource IDs;
    callers decide whether the returned evidence meets their proof criteria.
    """
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
        raise ValueError("Prompt must contain 1–4000 characters")
    if config.get("region") != "us-east-1":
        raise ValueError("Judge deployment is pinned to us-east-1")
    if client is None:
        if sys.platform == "darwin":
            raise RuntimeError("Live AWS calls are authorized only in the Kiro AWS terminal")
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "bedrock-agentcore",
            region_name="us-east-1",
            config=Config(connect_timeout=5, read_timeout=120, retries={"total_max_attempts": 1}),
        )
    session_id = str(uuid4())
    response = client.invoke_agent_runtime(
        agentRuntimeArn=config["runtime_arn"],
        runtimeSessionId=session_id,
        qualifier="DEFAULT",
        contentType="application/json",
        accept="application/json",
        payload=json.dumps({"prompt": prompt.strip(), "session_id": session_id}).encode(),
    )
    stream = response["response"]
    try:
        data = stream.read(MAX_RESPONSE_BYTES + 1)
    finally:
        stream.close()
    if response.get("statusCode", 200) != 200:
        raise RuntimeError("AgentCore Runtime returned a non-success status")
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Runtime response exceeds evidence limit")
    receipt = json.loads(data)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "treehouse.judge-invocation/1":
        raise ValueError("Unexpected Runtime response schema")
    if receipt.get("session_id") != session_id:
        raise ValueError("Runtime session does not match invocation")
    for key in ("knowledge_base_id", "gateway_id", "model_id"):
        if receipt.get(key) != config[key]:
            raise ValueError(f"Runtime {key} does not match server configuration")
    if not isinstance(receipt.get("answer"), str) or not receipt["answer"].strip():
        raise ValueError("Runtime did not return an answer")
    for key in ("citations", "tool_calls", "gateway_tools"):
        if not isinstance(receipt.get(key), list):
            raise ValueError(f"Runtime {key} must be a list")
    request_id = response.get("ResponseMetadata", {}).get("RequestId")
    if not request_id:
        raise ValueError("Runtime transport omitted the AWS request ID")
    receipt.update(
        runtime_arn=config["runtime_arn"],
        request_id=request_id,
        captured_at=datetime.now(UTC).isoformat(),
        source="live",
    )
    return receipt
