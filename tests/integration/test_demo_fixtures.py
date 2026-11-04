"""scripts/make_demo_fixtures.py rebuilds every committed demo fixture byte-for-byte (§5.3), and the CLI runs
one config in fake and record mode offline."""

from __future__ import annotations

import importlib.util

from typer.testing import CliRunner

from treehouse.cli import app
from treehouse.paths import repo_root
from treehouse.service import demo_root, load_runs


def _script():
    spec = importlib.util.spec_from_file_location("mdf", repo_root() / "scripts" / "make_demo_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rebuild_is_byte_identical(tmp_path):
    _script().main(["--out", str(tmp_path)])
    built = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert len(built) > 25
    committed = sorted(p.relative_to(repo_root()).as_posix() for d in ("fixtures/demo", "keys/synth")
                       for p in (repo_root() / d).rglob("*") if p.is_file()) + ["fixtures/golden/heads.json"]
    assert sorted(built) == sorted(committed)
    diff = [rel for rel in built if (tmp_path / rel).read_bytes() != (repo_root() / rel).read_bytes()]
    assert diff == []


def test_runs_yaml_lists_seven_synth_and_two_nepal_runs():
    runs = load_runs()
    assert [r["task"] for r in runs].count("synth-crossings-v1") == 7
    assert [r["task"] for r in runs].count("nepal-bhote-koshi-bridges") == 2
    assert all((demo_root() / "configs" / f"{r['run_id']}.json").is_file() for r in runs)


def test_cli_run_fake_and_record(tmp_path, offline_guard):
    cfg = demo_root() / "configs" / "synth-looper.json"
    r = CliRunner().invoke(app, ["run", str(cfg), "--mode", "fake", "--store", str(tmp_path / "s"), "--run-id",
                                 "looper-fake"])
    assert r.exit_code == 0, r.output
    assert "sealed looper-fake t-0: stop=completed claims=5" in r.output and "Not issued" in r.output
    r = CliRunner().invoke(app, ["run", str(cfg), "--mode", "record", "--store", str(tmp_path / "s"), "--run-id",
                                 "synth-looper", "--cassette-out", str(tmp_path / "cas"), "--no-evaluate"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "cas" / "synth-looper.model.jsonl").read_bytes() == \
        (demo_root() / "cassettes" / "synth-looper.model.jsonl").read_bytes()
    r = CliRunner().invoke(app, ["run", str(cfg), "--mode", "live", "--store", str(tmp_path / "s")])
    assert r.exit_code == 2 and "P6" in r.output
    r = CliRunner().invoke(app, ["verify", "--store", str(tmp_path / "s")])
    assert r.exit_code == 0, r.output
    assert offline_guard.attempts == []
