"""Hash-chained JSONL: every tamper (flip, delete, reorder, truncate) is reported at its exact seq."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from treehouse.canon import sha256_bytes
from treehouse.trace.chain import ChainedJsonlWriter, trial_genesis, verify_chain

records = st.lists(
    st.dictionaries(
        st.sampled_from(["a", "b", "name", "n"]),
        st.one_of(st.integers(-5, 5), st.text(max_size=6), st.booleans()),
        max_size=3,
    ),
    min_size=2,
    max_size=8,
)
SETTINGS = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


def _fresh(tmp_path: Path, name: str) -> Path:
    return Path(tempfile.mkdtemp(dir=tmp_path)) / f"{name}.jsonl"


def _write(path: Path, recs):
    w = ChainedJsonlWriter.for_trial(path, "t-0")
    for r in recs:
        w.append(r)
    return w.close()


def test_genesis_and_head(tmp_path):
    p = tmp_path / "t.jsonl"
    assert trial_genesis("t-0") == sha256_bytes(b"treehouse/trial/t-0")
    head = _write(p, [{"x": 1}, {"x": 2}])
    assert head.n_lines == 2
    assert head.file_sha256 == sha256_bytes(p.read_bytes())
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert check.ok and check.head == head.head and check.first_bad_seq is None


def test_empty_chain_head_is_genesis(tmp_path):
    head = ChainedJsonlWriter.for_trial(tmp_path / "e.jsonl", "t-9").close()
    assert head.head == trial_genesis("t-9") and head.n_lines == 0


def test_wrong_genesis_fails_at_zero(tmp_path):
    p = tmp_path / "t.jsonl"
    _write(p, [{"x": 1}, {"x": 2}])
    assert verify_chain(p, genesis=trial_genesis("t-1")).first_bad_seq == 0


@SETTINGS
@given(recs=records, data=st.data())
def test_flip_any_byte(tmp_path, recs, data):
    p = _fresh(tmp_path, "flip")
    head = _write(p, recs)
    lines = p.read_bytes().split(b"\n")[:-1]
    i = data.draw(st.integers(0, len(lines) - 1))
    j = data.draw(st.integers(0, len(lines[i]) - 1))
    mask = data.draw(st.integers(1, 255))
    b = bytearray(lines[i])
    b[j] ^= mask
    lines[i] = bytes(b)
    p.write_bytes(b"\n".join(lines) + b"\n")
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert not check.ok and check.first_bad_seq == i


@SETTINGS
@given(recs=records, data=st.data())
def test_delete_a_line(tmp_path, recs, data):
    p = _fresh(tmp_path, "del")
    head = _write(p, recs)
    lines = p.read_bytes().split(b"\n")[:-1]
    i = data.draw(st.integers(0, len(lines) - 1))
    del lines[i]
    p.write_bytes(b"".join(x + b"\n" for x in lines))
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert not check.ok and check.first_bad_seq == i


@SETTINGS
@given(recs=records, data=st.data())
def test_reorder_two_lines(tmp_path, recs, data):
    p = _fresh(tmp_path, "swap")
    head = _write(p, recs)
    lines = p.read_bytes().split(b"\n")[:-1]
    i = data.draw(st.integers(0, len(lines) - 2))
    j = data.draw(st.integers(i + 1, len(lines) - 1))
    lines[i], lines[j] = lines[j], lines[i]
    p.write_bytes(b"".join(x + b"\n" for x in lines))
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert not check.ok and check.first_bad_seq == i


@SETTINGS
@given(recs=records, data=st.data())
def test_truncate_anywhere(tmp_path, recs, data):
    p = _fresh(tmp_path, "trunc")
    head = _write(p, recs)
    raw = p.read_bytes()
    cut = data.draw(st.integers(0, len(raw) - 1))
    p.write_bytes(raw[:cut])
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert not check.ok and check.first_bad_seq == raw[:cut].count(b"\n")


def test_rewritten_chain_caught_by_head(tmp_path):
    p = tmp_path / "t.jsonl"
    head = _write(p, [{"x": 1}, {"x": 2}])
    p.unlink()
    _write(p, [{"x": 1}, {"x": 3}])  # a forger recomputes every hash
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert not check.ok and check.first_bad_seq == 1


def test_appended_line_caught_by_head(tmp_path):
    p = tmp_path / "t.jsonl"
    head = _write(p, [{"x": 1}])
    p.unlink()
    _write(p, [{"x": 1}, {"x": 2}])
    check = verify_chain(p, genesis=trial_genesis("t-0"), expected=head)
    assert not check.ok and check.first_bad_seq == 1


def test_writer_refuses_existing_file_and_closed_append(tmp_path):
    p = tmp_path / "t.jsonl"
    w = ChainedJsonlWriter.for_trial(p, "t-0")
    w.append({"a": 1})
    w.close()
    with pytest.raises(ValueError):
        w.append({"a": 2})
    with pytest.raises(FileExistsError):
        ChainedJsonlWriter.for_trial(p, "t-0")
