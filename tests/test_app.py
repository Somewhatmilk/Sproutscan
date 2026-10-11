"""Basic app smoke tests — verify the Flask app creates its DB and serves routes.

These are optional: they need the app's Python deps installed
(pip install -r req.txt pytest). The JS tests in tests/crop-utils.test.js
are the default runnable suite (node --test tests/crop-utils.test.js).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _client():
    """Build a test client with a throwaway SQLite DB. Database() takes the
    db filename as its constructor arg, so a fresh path keeps tests isolated."""
    import app as app_module

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    app_module.Database(db_name=tmp.name)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
    os.unlink(tmp.name)


def test_login_page_serves():
    for c in _client():
        resp = c.get("/")
        assert resp.status_code in (200, 302)


def test_dashboard_redirects_when_logged_out():
    for c in _client():
        resp = c.get("/dashboard")
        assert resp.status_code == 302


def test_static_css_serves():
    for c in _client():
        resp = c.get("/static/styles/main.css")
        assert resp.status_code == 200