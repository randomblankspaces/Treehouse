import pytest

from treehouse import paths


def test_repo_root_has_pyproject():
    root = paths.repo_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "treehouse").is_dir()


def test_roots_are_under_repo():
    root = paths.repo_root()
    assert paths.fixtures_root() == root / "fixtures"
    assert paths.keys_root() == root / "keys"
    assert paths.tasks_root() == root / "tasks"


def test_is_under():
    root = paths.repo_root()
    assert paths.is_under(root / "keys" / "synth" / "a.json", root / "keys")
    assert not paths.is_under(root / "keysx" / "a.json", root / "keys")
    assert not paths.is_under(root / "fixtures" / ".." / "keys" / "a", root / "fixtures")


def test_assert_not_key_path_rejects_keys():
    with pytest.raises(paths.KeyPathError):
        paths.assert_not_key_path(paths.keys_root() / "synth" / "x.key.json")
    with pytest.raises(paths.KeyPathError):
        paths.assert_not_key_path(paths.fixtures_root() / ".." / "keys" / "x.json")
    paths.assert_not_key_path(paths.fixtures_root() / "stac" / "a.json")


def test_key_roots_are_outside_tool_roots():
    for tool_root in paths.tool_roots():
        assert not paths.is_under(paths.keys_root(), tool_root)
        assert not paths.is_under(tool_root, paths.keys_root())


def test_key_guard_is_case_and_normalisation_insensitive():
    """On case-insensitive APFS/NTFS, KEYS/ opens keys/; the deny check must catch it on any OS."""
    root = paths.repo_root()
    for p in (root / "KEYS" / "synth" / "x.key.json", root / "fixtures" / ".." / "Keys" / "x.json"):
        with pytest.raises(paths.KeyPathError):
            paths.assert_not_key_path(p)
    assert not paths.may_be_under(root / "keysx" / "a.json", root / "keys")


def test_key_guard_uses_file_identity(tmp_path, monkeypatch):
    real = tmp_path / "repo"
    (real / "keys").mkdir(parents=True)
    (real / "src" / "treehouse").mkdir(parents=True)
    (real / "pyproject.toml").write_text("")
    monkeypatch.setenv("TREEHOUSE_ROOT", str(real))
    calls = []

    def samefile(a, b):  # simulate a filesystem where another spelling is the same directory
        calls.append(a)
        return str(a).endswith("alias")

    monkeypatch.setattr(paths.os.path, "samefile", samefile)
    alias = real / "alias"
    alias.mkdir()
    with pytest.raises(paths.KeyPathError):
        paths.assert_not_key_path(alias / "x.json")
    assert calls
