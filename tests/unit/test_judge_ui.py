"""All backends here are synthetic. These tests make no AWS calls."""
import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from treehouse.judge.models import JudgeConfig, Receipt
from treehouse.judge.service import JudgeError, JudgeService


def config():
    return JudgeConfig.model_validate({
        "schema_version": "treehouse.judge-config/1", "region": "us-east-1",
        "runtime_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test",
        "gateway_url": "https://example.com/mcp", "gateway_id": "test-gateway",
        "knowledge_base_id": "test-kb", "model_id": "test-model"})


def receipt(**updates):
    cfg = config()
    return {"schema_version": "treehouse.judge-invocation/1", "answer": "Synthetic test answer",
            "citations": [{"uri": "s3://test/project.md", "title": "Synthetic document", "quote": "Synthetic source excerpt"}],
            "tool_calls": [{"name": "search_project_docs", "arguments": {"query": "test"},
                            "result": {"answer": "synthetic"}, "is_error": False}],
            "gateway_tools": ["search_project_docs", "list_task_cards", "explain_rule"],
            "knowledge_base_id": cfg.knowledge_base_id, "gateway_id": cfg.gateway_id,
            "session_id": "test-session", "model_id": cfg.model_id,
            "runtime_arn": cfg.runtime_arn, "request_id": "test-request",
            "captured_at": datetime.now(UTC).isoformat(), "source": "live", **updates}


def test_derived_proofs_and_missing_evidence():
    assert {p["state"] for p in Receipt.model_validate(receipt()).proofs()} == {"observed"}
    assert Receipt.model_validate(receipt(citations=[{"uri": "s3://test/doc"}])).proofs()[0]["state"] == "missing"
    bad = receipt(citations=[], gateway_tools=["only-one"], answer="")
    assert [p["state"] for p in Receipt.model_validate(bad).proofs()] == ["missing"] * 3
    bad = receipt(tool_calls=[{"name": "search_project_docs", "arguments": {}, "result": "denied", "is_error": True}])
    assert Receipt.model_validate(bad).proofs()[1]["state"] == "missing"
    bad = receipt(tool_calls=[{"name": "other", "arguments": {}, "result": "ok", "is_error": False}])
    assert Receipt.model_validate(bad).proofs()[1]["state"] == "missing"


@pytest.mark.parametrize("updates", [{"verified": True}, {"request_id": ""},
    {"citations": [{"uri": "javascript:alert(1)"}]}, {"captured_at": "2026-01-01"}])
def test_reject_malformed_or_unsafe_receipts(updates):
    with pytest.raises(ValidationError):
        Receipt.model_validate(receipt(**updates))


def test_import_provenance_matches_and_age():
    old = receipt(captured_at=(datetime.now(UTC) - timedelta(days=2)).isoformat())
    service = JudgeService(config(), recorded=old)
    assert service.snapshot()["stale"]
    assert service.snapshot()["receipt"]["source"] == "recorded"
    assert {p["state"] for p in service.snapshot()["proofs"]} == {"recorded"}
    sample = JudgeService(recorded=receipt(source="sample"))
    assert {p["state"] for p in sample.snapshot()["proofs"]} == {"unverified"}
    with pytest.raises(ValueError, match="does not match"):
        JudgeService(config(), recorded=receipt(gateway_id="wrong"))


def test_lazy_reads_single_explicit_invoke_and_redacted_denial():
    calls = []
    def backend(cfg, prompt):
        calls.append(prompt)
        return receipt()
    async def scenario():
        service = JudgeService(config(), backend=backend)
        service.snapshot()
        assert not calls
        assert (await service.invoke("Test"))["receipt"]["source"] == "live"
        assert calls == ["Test"]
        with pytest.raises(JudgeError) as err:
            await service.invoke("Again")
        assert err.value.status == 429
        def denied(*_):
            raise RuntimeError("SECRET-AWS-KEY")
        with pytest.raises(JudgeError) as err:
            await JudgeService(config(), backend=denied).invoke("test")
        assert err.value.status == 502 and "SECRET" not in str(err.value)
    asyncio.run(scenario())


def test_timeout_keeps_slot_until_backend_finishes():
    released = threading.Event()
    def slow(*_):
        released.wait(2)
        return receipt()
    async def scenario():
        service = JudgeService(config(), backend=slow, timeout=.01, cooldown=0)
        try:
            with pytest.raises(JudgeError) as err:
                await service.invoke("test")
            assert err.value.status == 504 and service.snapshot()["busy"]
            with pytest.raises(JudgeError) as err:
                await service.invoke("again")
            assert err.value.status == 409
        finally:
            released.set()
        await asyncio.sleep(.05)
        assert not service.snapshot()["busy"] and service.receipt is not None
        assert service.snapshot()["receipt"]["answer"] == "Synthetic test answer"
        assert (await service.invoke("second question"))["receipt"]["answer"] == "Synthetic test answer"
    asyncio.run(scenario())


async def request(app, path, *, method="GET", body=b"", origin="http://127.0.0.1:8765", host="127.0.0.1:8765"):
    """Minimal ASGI client avoids adding an HTTP client dependency for core users."""
    headers = [(b"host", host.encode()), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": method, "scheme": "http", "path": path,
             "raw_path": path.encode(), "query_string": b"", "headers": headers,
             "server": ("127.0.0.1", 8765), "client": ("127.0.0.1", 1234)}
    messages = []
    consumed = False
    async def receive():
        nonlocal consumed
        if not consumed:
            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Event().wait()
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    return start["status"], b"".join(m.get("body", b"") for m in messages), dict(start["headers"])


def test_api_guards_validation_export_and_empty():
    pytest.importorskip("fastapi")
    from treehouse.judge.web import create_app
    async def scenario():
        service = JudgeService(config(), backend=lambda *_: receipt())
        app = create_app(service)
        assert (await request(app, "/api/status"))[0] == 200
        assert service.receipt is None
        assert (await request(app, "/api/receipt"))[0] == 404
        for kwargs in ({"origin": "https://evil.example"}, {"host": "evil.example"}, {"origin": None}):
            assert (await request(app, "/api/invoke", method="POST", body=b'{"prompt":"x"}', **kwargs))[0] == 403
        for body, expected in [(b'{"prompt":""}', 422), (b'[]', 422),
                               (json.dumps({"prompt": "x" * 2001}).encode(), 422),
                               (b"x" * 10001, 413), (b'{"prompt":"x","runtime_arn":"override"}', 422)]:
            assert (await request(app, "/api/invoke", method="POST", body=body))[0] == expected
        assert service.receipt is None
        status, _, headers = await request(app, "/api/invoke", method="POST", body=b'{"prompt":"Test"}')
        assert status == 200 and b"frame-ancestors 'none'" in headers[b"content-security-policy"]
        status, body, headers = await request(app, "/api/receipt")
        assert status == 200 and json.loads(body)["request_id"] == "test-request"
        assert b"attachment" in headers[b"content-disposition"]
        assert (await request(app, "/assets/secrets"))[0] == 404
        assert (await request(create_app(), "/api/invoke", method="POST", body=b'{"prompt":"Test"}'))[0] == 409
    asyncio.run(scenario())


def test_static_html_has_no_receipt_interpolation():
    from pathlib import Path
    assets = Path(__file__).parents[2] / "src/treehouse/judge/assets"
    js = (assets / "app.js").read_text()
    assert "innerHTML" not in js and "textContent" in js
    assert 'aria-live="polite"' in (assets / "index.html").read_text()


@pytest.mark.parametrize("uri", ["s3:", "s3://bucket/", "s3:///doc.md", "https:///doc", "https://user:secret@example.com/doc", "https://example.com/doc?X-Amz-Signature=secret", "https://example.com/doc?access_token=secret"])
def test_source_requires_real_location_without_credentials(uri):
    with pytest.raises(ValidationError):
        Receipt.model_validate(receipt(citations=[{"uri": uri, "quote": "text"}]))


@pytest.mark.parametrize("names", [["a", "a ", " a"], ["a", "b", ""], ["a", "b", "c d"]])
def test_catalog_rejects_whitespace_names(names):
    with pytest.raises(ValidationError):
        Receipt.model_validate(receipt(gateway_tools=names))
    assert Receipt.model_validate(receipt(gateway_tools=["a", "a", "a"])).proofs()[1]["state"] == "missing"


def test_call_name_rejects_whitespace():
    with pytest.raises(ValidationError):
        Receipt.model_validate(receipt(tool_calls=[{"name": " search_project_docs", "arguments": {}, "result": "ok", "is_error": False}]))


def test_recursive_redaction_applies_before_status_and_export():
    raw = receipt(answer="Do not expose AKIAABCDEFGHIJKLMNOP or Bearer synthetic-token",
                  citations=[{"uri": "s3://test/doc", "quote": "aws_secret_access_key=synthetic-secret"}],
                  tool_calls=[{"name": "search_project_docs", "arguments": {"nested": [{"Authorization": "raw-auth"}, {"api_key": "raw-key"}]},
                               "result": {"rows": [{"password": "raw-password", "text": "Bearer other-secret"}], "aws_session_token": "raw-session"}, "is_error": False}])
    service = JudgeService(config(), recorded=raw)
    status = json.dumps(service.snapshot())
    exported = service.receipt.model_dump_json()
    for secret in ("AKIAABCDEFGHIJKLMNOP", "synthetic-token", "synthetic-secret", "raw-auth", "raw-key", "raw-password", "other-secret", "raw-session"):
        assert secret not in status and secret not in exported
    assert "REDACTED" in status


def test_late_answer_is_retained_with_one_backend_call():
    async def scenario():
        calls = []
        def backend(*_):
            import time
            calls.append("called")
            time.sleep(.05)
            return receipt(answer="Synthetic late answer")
        service = JudgeService(config(), backend=backend, timeout=.005)
        with pytest.raises(JudgeError) as err:
            await service.invoke("test")
        assert err.value.status == 504
        await asyncio.sleep(.08)
        assert service.snapshot()["receipt"]["answer"] == "Synthetic late answer"
        assert not service.snapshot()["busy"] and calls == ["called"]
    asyncio.run(scenario())
