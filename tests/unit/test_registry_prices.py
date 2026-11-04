"""Model registry, price tables, the same-family and vision rules, and the P6 CLI commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from treehouse.cli import app
from treehouse.paths import repo_root
from treehouse.providers.prices import load_default, load_fixture, load_probe_ceiling
from treehouse.providers.registry import ModelRegistry, RoleRuleViolation, UnknownModel, check_roles
from treehouse.providers.spend import SpendLedger
from treehouse.schemas.config import InferenceParams, RoleConfig, RunConfig
from treehouse.schemas.model_io import Usage

P = InferenceParams(max_tokens=100)

def new_ledger(*a, **kw):
    """A test ledger: synthetic tables allowed, genesis written (B1: reserve refuses an un-initialised file)."""
    kw.setdefault("allow_synthetic", True)
    led = SpendLedger(*a, **kw)
    if not led.initialized:
        led.init(note="test")
    return led



def role(key, family, provider="bedrock", tools=()):
    return RoleConfig(provider=provider, model_key=key, family=family, params=P, tools=list(tools))


def cfg(worker, verifier=None, **kw):
    return RunConfig(task_ref="t@sha256:00", mode="live", worker=worker, verifier=verifier, seed=1, **kw)


def test_registry_defaults_u1_u2():
    reg = ModelRegistry.load()
    w, v = reg.get(reg.defaults["worker"]), reg.get(reg.defaults["verifier"])
    assert (w.key, w.model_id, w.image_delivery, w.verified) == (
        "claude-sonnet-5-5", "anthropic.claude-sonnet-5-5", "user_turn", False)
    assert w.invoke_id.startswith(("us.", "global.")) and w.vision and w.tool_use
    assert (v.key, v.model_id, v.invoke_id) == ("nova-pro", "amazon.nova-pro-v1:0", "us.amazon.nova-pro-v1:0")
    assert w.family != v.family
    assert reg.get("us.amazon.nova-pro-v1:0").key == "nova-pro"
    with pytest.raises(UnknownModel):
        reg.get("nope")


def test_every_registry_model_has_a_price_row():
    reg = ModelRegistry.load()
    for t in (load_default(), load_fixture()):
        # M6: one row per (model, inference profile) the registry calls
        assert {f"{m.price_ref}@{m.invoke_id.split('.')[0]}" for m in reg.models} <= set(t.models)
    assert load_probe_ceiling().estimated and load_probe_ceiling().default.priced
    assert load_fixture().synthetic and not load_default().synthetic


def test_same_family_rule_uses_registry_family():
    reg = ModelRegistry.load()
    check_roles(cfg(role("claude-sonnet-5-5", "anthropic-claude"), role("nova-pro", "amazon-nova")), reg,
                needs_vision=True)
    # the config claims different families, but the registry knows better
    with pytest.raises(RoleRuleViolation, match="registry says"):
        check_roles(cfg(role("claude-sonnet-5-5", "anthropic-claude"), role("claude-sonnet-5-5", "other")), reg,
                    needs_vision=False)
    same = cfg(role("nova-pro", "amazon-nova"), role("nova-pro", "amazon-nova"), allow_same_family=True)
    check_roles(same, reg, needs_vision=False)


def test_vision_rule():
    reg = ModelRegistry.load()
    blind = reg.get("nova-pro").model_copy(update={"key": "text-only", "vision": False, "family": "x"})
    reg = ModelRegistry(defaults=reg.defaults, models=[*reg.models, blind])
    c = cfg(role("text-only", "x"), role("nova-pro", "amazon-nova"))
    check_roles(c, reg, needs_vision=False)
    with pytest.raises(RoleRuleViolation, match="vision"):
        check_roles(c, reg, needs_vision=True)


def test_fake_roles_are_not_registry_checked():
    check_roles(cfg(role("scripted", "fake-a", provider="fake"), role("scripted-v", "fake-b", provider="fake")),
                ModelRegistry.load(), needs_vision=True)


# -- CLI -------------------------------------------------------------------------------------------
def test_prices_check_fails_on_null_table_and_passes_on_filled(tmp_path):
    r = CliRunner().invoke(app, ["prices", "check"])
    assert r.exit_code == 1 and "UNPRICED" in r.output and "claude-sonnet-5-5 [worker]" in r.output
    text = (repo_root() / "config/prices/bedrock-us-east-1.2026-11-04.yaml").read_text()
    filled = (text.replace("input: null, output: null", "input: 0.003, output: 0.015")
              .replace("source: null", "source: test").replace("retrieved: null", "retrieved: 2026-11-04"))
    (tmp_path / "t.yaml").write_text(filled)
    r = CliRunner().invoke(app, ["prices", "check", "--table", str(tmp_path / "t.yaml")])
    assert r.exit_code == 0, r.output
    r = CliRunner().invoke(app, ["prices", "check", "--table", str(repo_root() / "config/prices/fixture.yaml")])
    assert r.exit_code == 1 and "synthetic" in r.output


def test_budget_status_and_plan(monkeypatch, tmp_path):
    r = CliRunner().invoke(app, ["budget", "status"])
    assert r.exit_code == 4 and "NO LEDGER" in r.output  # B1: a missing ledger is loud, never "$0 ok"
    assert CliRunner().invoke(app, ["budget", "init"]).exit_code == 0
    assert CliRunner().invoke(app, ["budget", "init"]).exit_code == 1  # never re-init
    r = CliRunner().invoke(app, ["budget", "status"])
    assert r.exit_code == 0 and "spent $0.0000" in r.output and ": ok" in r.output and "EMPTY LEDGER" in r.output
    assert "NOT the AWS bill" in r.output
    led = new_ledger(prices=load_fixture())
    led.commit(led.reserve("nova-pro", 1000, 1000), Usage(input_tokens=1000, output_tokens=1000))
    r = CliRunner().invoke(app, ["budget", "status"])
    assert "over 1 call(s)" in r.output
    r = CliRunner().invoke(app, ["budget", "plan", "--trials", "3"])
    assert r.exit_code == 1 and "UNPRICED" in r.output
    task = str(repo_root() / "tasks/synth-crossings-v1.yaml")
    r = CliRunner().invoke(app, ["budget", "plan", "--task", task, "--trials", "3"])
    assert r.exit_code == 1 and "UNPRICED" in r.output  # M11c: a null table never plans "ok"
    fx = str(repo_root() / "config/prices/fixture.yaml")
    r = CliRunner().invoke(app, ["budget", "plan", "--task", task, "--trials", "3", "--calls", "100", "--prices", fx])
    assert r.exit_code == 0, r.output
    # M11a: the $5 per-run cap plus one call's worst case (20k in x 0.003 + 4096 out x 0.015 per 1K = $0.12144)
    assert "3 trial(s) x $5.1214 = $15.3643" in r.output
    r = CliRunner().invoke(app, ["budget", "plan", "--task", task, "--trials", "1", "--calls", "100", "--prices", fx,
                                 "--verifier-calls", "10", "--verifier-input-tokens", "1000",
                                 "--verifier-max-tokens", "100"])
    # M11b: + nova-pro 10 x (1000 x 0.0008 + 100 x 0.0032) / 1000 = $0.0112
    assert r.exit_code == 0 and "$5.1326" in r.output, r.output
    r = CliRunner().invoke(app, ["budget", "plan", "--prices", str(repo_root() / "config/prices/fixture.yaml"),
                                 "--calls", "10", "--input-tokens", "1000", "--max-tokens", "100"])
    assert r.exit_code == 0 and "$0.0450" in r.output


def test_budget_status_exit_code_over_alarm(tmp_path):
    from treehouse.providers.prices import Price, PriceTable

    big = PriceTable(version="b", region="any", synthetic=True, models={"claude-sonnet-5-5": Price(input=1.0, output=5.0)})
    led = new_ledger(prices=big)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        led.commit(led.reserve("claude-sonnet-5-5", 0, 72_000, allow_over_alarm=True, reason="t"),
                   Usage(input_tokens=0, output_tokens=72_000))
    r = CliRunner().invoke(app, ["budget", "status"])
    assert r.exit_code == 2 and "STOP" in r.output
