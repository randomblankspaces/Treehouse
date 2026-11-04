"""Offline checks: no AWS credentials or network required."""

import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runtime_receipt_is_real_transport_metadata(monkeypatch):
    import boto3
    from botocore.response import StreamingBody
    from botocore.stub import ANY, Stubber

    from treehouse.judge.aws import invoke_runtime

    config = {
        "region": "us-east-1",
        "runtime_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/judge-abc",
        "gateway_id": "gw123",
        "knowledge_base_id": "KB123",
        "model_id": "amazon.nova-lite-v1:0",
    }
    monkeypatch.setattr("treehouse.judge.aws.uuid4", lambda: "12345678-1234-1234-1234-123456789012")
    payload = {
        "schema_version": "treehouse.judge-invocation/1",
        "answer": "grounded",
        "citations": [],
        "tool_calls": [],
        "gateway_tools": [],
        "gateway_id": "gw123",
        "knowledge_base_id": "KB123",
        "model_id": config["model_id"],
        "session_id": "12345678-1234-1234-1234-123456789012",
    }
    data = json.dumps(payload).encode()
    client = boto3.client(
        "bedrock-agentcore", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    with Stubber(client) as stub:
        stub.add_response(
            "invoke_agent_runtime",
            {
                "statusCode": 200,
                "response": StreamingBody(io.BytesIO(data), len(data)),
                "contentType": "application/json",
                "ResponseMetadata": {"RequestId": "aws-request"},
            },
            {
                "agentRuntimeArn": config["runtime_arn"],
                "runtimeSessionId": ANY,
                "qualifier": "DEFAULT",
                "contentType": "application/json",
                "accept": "application/json",
                "payload": ANY,
            },
        )
        receipt = invoke_runtime(config, "question", client=client)
    assert receipt["request_id"] == "aws-request"
    assert receipt["source"] == "live"
    assert receipt["runtime_arn"] == config["runtime_arn"]


def test_gateway_lambda_uses_rag_citations(monkeypatch):
    mod = load("deploy/judge_gateway/handler.py", "gateway_handler")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "KB123")
    monkeypatch.setenv("MODEL_ID", "amazon.nova-lite-v1:0")

    class Client:
        def retrieve_and_generate(self, **kw):
            import botocore.session
            from botocore.validate import validate_parameters

            validate_parameters(
                kw,
                botocore.session.get_session()
                .get_service_model("bedrock-agent-runtime")
                .operation_model("RetrieveAndGenerate")
                .input_shape,
            )
            assert (
                kw["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]["knowledgeBaseId"]
                == "KB123"
            )
            return {
                "output": {"text": "The marker is Cedar Lantern 47."},
                "citations": [
                    {
                        "retrievedReferences": [
                            {
                                "location": {"s3Location": {"uri": "s3://owned/public/treehouse.md"}},
                                "content": {"text": "Cedar Lantern 47"},
                            }
                        ]
                    }
                ],
                "ResponseMetadata": {"RequestId": "kb-request"},
            }

    class Context:
        client_context = type(
            "CC", (), {"custom": {"bedrockAgentCoreToolName": "project___search_project_docs"}}
        )()
        aws_request_id = "lambda-request"

    result = mod.dispatch({"query": "marker?"}, Context(), client=Client())
    assert result["citations"] == [{"uri": "s3://owned/public/treehouse.md", "quote": "Cedar Lantern 47"}]
    assert result["request_id"] == "kb-request"
    assert len(mod.TOOLS) == 3


def test_runtime_strands_really_calls_gateway():
    mod = load("deploy/judge_runtime/main.py", "judge_runtime_main")
    pytest.importorskip("strands", reason="requires the strands extra")
    from strands.models import Model

    class ScriptedModel(Model):
        calls = 0

        def get_config(self):
            return {"model_id": "offline", "context_window_limit": 10000}

        def update_config(self, **kw):
            pass

        async def structured_output(self, *args, **kw):
            yield {}

        async def stream(self, *args, **kw):
            self.calls += 1
            yield {"messageStart": {"role": "assistant"}}
            if self.calls == 1:
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"toolUseId": "one", "name": "search_project_docs"}}
                    }
                }
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"query":"marker"}'}}}}
                yield {"contentBlockStop": {}}
                yield {"messageStop": {"stopReason": "tool_use"}}
            else:
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": "Cedar Lantern 47"}}}
                yield {"contentBlockStop": {}}
                yield {"messageStop": {"stopReason": "end_turn"}}

    class Gateway:
        def catalog(self):
            return ["project___" + t for t in ("search_project_docs", "list_task_cards", "explain_rule")]

        def call(self, name, arguments):
            assert name == "project___search_project_docs"
            return (
                {
                    "answer": "Cedar Lantern 47",
                    "citations": [{"uri": "s3://test/doc", "quote": "Cedar Lantern 47"}],
                },
                False,
                "gateway-request",
            )

    config = {
        "region": "us-east-1",
        "gateway_id": "gw",
        "knowledge_base_id": "kb",
        "model_id": "offline",
        "gateway_url": "https://example.invalid/mcp",
    }
    result = mod.invoke(
        {"prompt": "marker?", "session_id": "session"},
        config=config,
        gateway=Gateway(),
        model=ScriptedModel(),
    )
    assert result["tool_calls"][0]["request_id"] == "gateway-request"
    assert result["tool_calls"][0]["name"] == "project___search_project_docs"
    assert result["citations"][0]["uri"] == "s3://test/doc"
    assert result["answer"] == "Cedar Lantern 47"


def test_mcp_sigv4_and_sse_parser():
    from botocore.credentials import Credentials

    mod = load("deploy/judge_runtime/main.py", "judge_runtime_signing")
    request = mod.signed_request(
        "https://test.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        {"jsonrpc": "2.0", "method": "tools/list", "id": "1"},
        Credentials("access", "secret", "token"),
    )
    assert "us-east-1/bedrock-agentcore/aws4_request" in request.headers["Authorization"]
    assert request.headers["X-Amz-Security-Token"] == "token"
    assert mod.parse_mcp(b'event: message\ndata: {"jsonrpc":"2.0","id":"1","result":{"tools":[]}}\n\n')[
        "result"
    ] == {"tools": []}
    with pytest.raises(ValueError):
        mod.signed_request("http://localhost/mcp", {}, Credentials("x", "y"))


def test_adapter_rejects_oversized_and_error_responses():
    from treehouse.judge.aws import invoke_runtime

    config = {
        "region": "us-east-1",
        "runtime_arn": "arn",
        "gateway_id": "gw",
        "knowledge_base_id": "kb",
        "model_id": "model",
    }

    class Fake:
        def __init__(self, data, status=200):
            self.data, self.status = data, status

        def invoke_agent_runtime(self, **kw):
            assert len(kw["runtimeSessionId"]) >= 33
            return {"response": io.BytesIO(self.data), "statusCode": self.status}

    with pytest.raises(ValueError, match="exceeds"):
        invoke_runtime(config, "question", client=Fake(b"x" * 1_000_001))
    with pytest.raises(RuntimeError, match="non-success"):
        invoke_runtime(config, "question", client=Fake(b"{}", 500))
    with pytest.raises(ValueError, match="schema"):
        invoke_runtime(config, "question", client=Fake(b"{}"))


def test_deploy_plan_does_not_construct_aws_client(capsys):
    mod = load("scripts/judge_deploy.py", "judge_plan")
    mod.main([])
    assert json.loads(capsys.readouterr().out)["mode"] == "PLAN_NO_AWS_CALLS"


def test_lambda_other_tools_and_rejected_input(monkeypatch):
    mod = load("deploy/judge_gateway/handler.py", "gateway_other")

    class Context:
        client_context = type(
            "CC", (), {"custom": {"bedrockAgentCoreToolName": "project___list_task_cards"}}
        )()
        aws_request_id = "lambda-request"

    assert len(mod.dispatch({}, Context())["tasks"]) == 3
    Context.client_context.custom["bedrockAgentCoreToolName"] = "project___explain_rule"
    assert mod.dispatch({"rule_id": "privacy"}, Context())["request_id"] == "lambda-request"
    with pytest.raises(ValueError, match="Unknown public rule"):
        mod.dispatch({"rule_id": "secret"}, Context())
    Context.client_context.custom["bedrockAgentCoreToolName"] = "project___search_project_docs"
    with pytest.raises(ValueError, match="Query"):
        mod.dispatch({"query": ""}, Context())


def test_strands_budget_stops_repeated_tool_attempts():
    mod = load("deploy/judge_runtime/main.py", "runtime_bound")
    pytest.importorskip("strands", reason="requires the strands extra")
    from strands.models import Model

    class Repeater(Model):
        turns = 0

        def get_config(self):
            return {"model_id": "offline", "context_window_limit": 10000}

        def update_config(self, **kw):
            pass

        async def structured_output(self, *args, **kw):
            yield {}

        async def stream(self, *args, **kw):
            self.turns += 1
            yield {"messageStart": {"role": "assistant"}}
            for index in range(6):
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"toolUseId": str(index), "name": "search_project_docs"}}
                    }
                }
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"query":"marker"}'}}}}
                yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}

    class Gateway:
        attempts = 0

        def catalog(self):
            return ["project___" + t for t in ("search_project_docs", "list_task_cards", "explain_rule")]

        def call(self, *args):
            self.attempts += 1
            raise RuntimeError("offline transport failure")

    gateway = Gateway()
    model = Repeater()
    config = {
        "region": "us-east-1",
        "gateway_id": "gw",
        "knowledge_base_id": "kb",
        "model_id": "offline",
        "gateway_url": "https://example.invalid/mcp",
    }
    from strands.types.exceptions import EventLoopException

    with pytest.raises(EventLoopException, match="model budget exceeded"):
        mod.invoke({"prompt": "marker?"}, config=config, gateway=gateway, model=model)
    assert gateway.attempts == 5
    assert model.turns == 4


def test_archive_rejects_mac_native_dependencies(tmp_path):
    import zipfile

    mod = load("deploy/judge_runtime/build.py", "runtime_build_test")
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name in ["main.py", "strands/__init__.py", "boto3/__init__.py"]:
            z.writestr(name, "")
        z.writestr("native.so", b"MACHO" + b"0" * 20)
    with pytest.raises(ValueError, match="Linux ARM64"):
        mod.validate_archive(archive)


@pytest.mark.allow_loopback
def test_runtime_http_contract_matches_adapter_envelope(monkeypatch):
    """Exercise our documented /ping + raw /invocations contract over local HTTP."""
    import threading
    from urllib.request import Request, urlopen

    from treehouse.judge.aws import invoke_runtime

    mod = load("deploy/judge_runtime/main.py", "runtime_http")
    session_id = "12345678-1234-1234-1234-123456789012"
    config = {
        "region": "us-east-1",
        "runtime_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-abc",
        "gateway_id": "gw",
        "knowledge_base_id": "kb",
        "model_id": "offline",
    }
    payload = {
        "schema_version": "treehouse.judge-invocation/1",
        "answer": "offline HTTP envelope",
        "citations": [],
        "tool_calls": [],
        "gateway_tools": [],
        "gateway_id": "gw",
        "knowledge_base_id": "kb",
        "model_id": "offline",
        "session_id": session_id,
    }
    monkeypatch.setattr(mod, "invoke", lambda request: payload)
    monkeypatch.setattr("treehouse.judge.aws.uuid4", lambda: session_id)
    server = mod.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(url + "/ping", timeout=2) as response:
            assert json.load(response) == {"status": "Healthy"}
        with urlopen(
            Request(
                url + "/invocations",
                data=b'{"prompt":"offline"}',
                headers={"Content-Type": "application/json"},
            ),
            timeout=2,
        ) as response:
            data = response.read()
            assert json.loads(data) == payload

        class Transport:
            def invoke_agent_runtime(self, **kwargs):
                return {
                    "response": io.BytesIO(data),
                    "statusCode": 200,
                    "ResponseMetadata": {"RequestId": "offline-http-receipt"},
                }

        result = invoke_runtime(config, "question", client=Transport())
        assert result["answer"] == "offline HTTP envelope"
        assert result["request_id"] == "offline-http-receipt"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.allow_loopback
def test_signed_gateway_redirects_never_forward_auth():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.request import ProxyHandler, Request, build_opener

    mod = load("deploy/judge_runtime/main.py", "runtime_no_redirect")
    seen = []

    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            seen.append(self.path)
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/credential-leak")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(RuntimeError, match="redirects are forbidden"):
            build_opener(ProxyHandler({}), mod.NoRedirect()).open(
                Request(
                    f"http://127.0.0.1:{server.server_port}/mcp",
                    data=b"{}",
                    headers={"Authorization": "offline-only"},
                ),
                timeout=2,
            )
        assert seen == ["/mcp"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
