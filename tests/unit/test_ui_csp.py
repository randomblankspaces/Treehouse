"""The product UI's CSP: same-origin everything, plus GSI aerial tiles as images for the map."""

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from treehouse.ui.web import create_app

ORIGIN = "http://localhost:8765"


def test_csp_allows_only_gsi_tiles_beyond_self(tmp_path):
    (tmp_path / "store").mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>shell</html>")
    with TestClient(create_app(tmp_path / "store", origin=ORIGIN, frontend_dist=dist, judge_app=None), base_url=ORIGIN) as c:
        csp = c.get("/").headers["content-security-policy"]
    rules = dict(part.strip().split(" ", 1) for part in csp.split(";"))
    assert rules["img-src"] == "'self' https://cyberjapandata.gsi.go.jp"
    for name in ("default-src", "script-src", "style-src", "connect-src"):
        assert rules[name] == "'self'", name
