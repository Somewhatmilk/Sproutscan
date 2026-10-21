"""Basic app smoke tests — verify the Flask app creates its DB and serves routes.

These are optional: they need the app's Python deps installed
(pip install -r req.txt pytest). The JS tests in tests/crop-utils.test.js
are the default runnable suite (node --test tests/crop-utils.test.js).
"""
import os
import re
import sys
import tempfile

import pyotp

# S1: app refuses to start without SECRET_KEY — tests must supply one
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _client():
    """Build a test client with a throwaway SQLite DB. Database() takes the
    db filename as its constructor arg, so a fresh path keeps tests isolated."""
    import app as app_module

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    test_db = app_module.Database(db_name=tmp.name)
    test_db.init_db()  # schema-once: DDL no longer runs in __init__; force it here
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


# --- Fix2 regression tests (2026-10-21 re-review blockers) ---

def test_login_page_has_visible_named_username_input():
    # B1: login was impossible — username input was hidden and only populated by
    # clicking a profile card (and app.py:548 renders login.html without users,
    # so zero cards rendered). Direct entry must work.
    for c in _client():
        resp = c.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8", "replace")
        assert 'id="usernameInput"' in html
        assert 'type="text" id="usernameInput" name="username"' in html, \
            "username input must be a visible text input with a name"
        # stale default-password hint must be gone (S3 seeds are random one-time passwords)
        assert "Password (Default: 123)" not in html


def test_verify_mfa_rejects_bad_token_and_keeps_db_unchanged():
    # B2: success return was dedented out of the if totp.verify(token) block, so a
    # wrong TOTP skipped the DB UPDATE yet returned success=True.
    for c in _client():
        secret = pyotp.random_base32()
        with c.session_transaction() as sess:
            sess["user_id"] = 1  # seeded admin (fresh throwaway DB seeds 3 users)
            sess["temp_mfa_secret"] = secret

        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        bad_code = "000000" if valid_code != "000000" else "111111"

        # CSRFProtect is live for JSON POSTs — fetch a token from the rendered page
        page = c.get("/")
        m = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
        assert m, "csrf_token not rendered on login page"
        csrf = m.group(1).decode()
        headers = {"X-CSRFToken": csrf}

        resp = c.post("/api/verify-mfa", json={"token": bad_code}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["success"] is False, "bad TOTP must NOT report success"

        # DB must be untouched after a failed verify
        import app as app_module
        conn = app_module.db.get_connection()
        row = conn.execute("SELECT mfa_secret FROM users WHERE id = 1").fetchone()
        conn.close()
        assert row["mfa_secret"] is None, "failed verify must not write mfa_secret"

        # and a valid code still succeeds (the re-indent must not break the happy path)
        resp = c.post("/api/verify-mfa", json={"token": valid_code}, headers=headers)
        assert resp.get_json()["success"] is True


def test_permanent_delete_with_csrf_token():
    # B3: permanent-delete form POSTed without csrf_token -> CSRFProtect 400 ->
    # hard delete always failed. The restore form beside it already had the token.
    for c in _client():
        import app as app_module
        # seed a soft-deleted plantation directly (throwaway DB)
        conn = app_module.db.get_connection()
        cur = conn.execute(
            "INSERT INTO plantations (number, name, date_created, is_deleted, date_deleted) "
            "VALUES ('B3-TEST', 'Delete Me', '21/10/2026', 1, '21/10/2026')"
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()

        # login as the seeded admin
        with c.session_transaction() as sess:
            sess["user_id"] = 1

        # grab a csrf token from the recycle-bin page (restore form renders one)
        page = c.get("/farms/deleted")
        assert page.status_code == 200
        m = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
        assert m, "csrf_token input not rendered on /farms/deleted"
        token = m.group(1).decode()

        resp = c.post(
            f"/plantations/{pid}/permanent-delete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert resp.status_code == 200, "permanent delete with token must not 400"

        conn = app_module.db.get_connection()
        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM plantations WHERE id = ?", (pid,)
        ).fetchone()["n"]
        conn.close()
        assert remaining == 0, "plantation must be hard-deleted"