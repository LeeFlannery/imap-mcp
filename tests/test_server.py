import asyncio
import datetime as dt
from contextlib import nullcontext

import pytest

from imap_mcp import imap, server


def test_targets(config):
    assert [a.key for a in server._targets(None)] == ["alpha", "gmailish"]
    assert [a.key for a in server._targets("alpha")] == ["alpha"]
    assert server._targets("off") == []  # disabled account resolves to nothing
    with pytest.raises(KeyError):
        server._targets("nope")


def test_list_accounts_statuses(config, monkeypatch):
    def open_box(account):
        if account.key == "gmailish":
            raise ConnectionRefusedError("nope")
        return nullcontext()

    monkeypatch.setenv("ALPHA_PW", "pw")
    monkeypatch.setenv("BETA_PW", "pw")
    monkeypatch.setattr(imap, "open_box", open_box)

    status = {e["account"]: e["status"] for e in server.list_accounts()}
    assert status == {
        "alpha": "ok",
        "gmailish": "unreachable: ConnectionRefusedError",
        "off": "disabled",
    }

    monkeypatch.delenv("ALPHA_PW")
    status = {e["account"]: e["status"] for e in server.list_accounts()}
    assert status["alpha"] == "no-credential"


def test_list_emails_merges_and_sorts(config, monkeypatch):
    def fetch_rows(account, **kwargs):
        return {
            "alpha": [
                {"account": "alpha", "id": "1", "date": "2026-07-01T00:00:00+00:00"},
                {"account": "alpha", "id": "2", "date": "2026-07-03T00:00:00+00:00"},
            ],
            "gmailish": [
                {"account": "gmailish", "id": "9", "date": "2026-07-02T00:00:00+00:00"},
            ],
        }[account.key]

    monkeypatch.setattr(imap, "fetch_rows", fetch_rows)
    rows = server.list_emails()
    assert [(r["account"], r["id"]) for r in rows] == [
        ("alpha", "2"),
        ("gmailish", "9"),
        ("alpha", "1"),
    ]


def test_list_emails_single_account_passes_filters(config, monkeypatch):
    seen = {}

    def fetch_rows(account, **kwargs):
        seen[account.key] = kwargs
        return []

    monkeypatch.setattr(imap, "fetch_rows", fetch_rows)
    server.list_emails(account="alpha", since=dt.date(2026, 7, 1), unread_only=True, limit=5)
    assert seen == {
        "alpha": {"since": dt.date(2026, 7, 1), "unread_only": True, "limit": 5},
    }


def test_list_emails_account_failure_is_isolated(config, monkeypatch):
    def fetch_rows(account, **kwargs):
        if account.key == "alpha":
            raise TimeoutError("slow server")
        return [{"account": account.key, "id": "1", "date": "2026-07-01T00:00:00+00:00"}]

    monkeypatch.setattr(imap, "fetch_rows", fetch_rows)
    rows = server.list_emails()
    errors = [r for r in rows if "error" in r]
    assert errors == [{"account": "alpha", "error": "TimeoutError: slow server"}]
    assert [r["account"] for r in rows if "error" not in r] == ["gmailish"]


def test_search_emails_passes_query(config, monkeypatch):
    seen = {}

    def fetch_rows(account, **kwargs):
        seen[account.key] = kwargs
        return []

    monkeypatch.setattr(imap, "fetch_rows", fetch_rows)
    server.search_emails("invoice", since=dt.date(2026, 7, 1), limit=10)
    assert set(seen) == {"alpha", "gmailish"}
    assert seen["alpha"] == {"query": "invoice", "since": dt.date(2026, 7, 1), "limit": 10}


def test_get_email_found(config, monkeypatch):
    monkeypatch.setattr(imap, "fetch_one", lambda a, uid: {"account": a.key, "id": uid})
    assert server.get_email("alpha", "42") == {"account": "alpha", "id": "42"}


def test_get_email_not_found(config, monkeypatch):
    monkeypatch.setattr(imap, "fetch_one", lambda a, uid: None)
    out = server.get_email("alpha", "42")
    assert out["error"] == "not found"


def test_all_tools_registered():
    tools = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert tools == {"list_accounts", "list_emails", "search_emails", "get_email"}


def test_since_param_coerces_iso_strings(config, monkeypatch):
    """The MCP layer parses ISO date strings into datetime.date for `since`."""
    seen = {}

    def fetch_rows(account, **kwargs):
        seen[account.key] = kwargs
        return []

    monkeypatch.setattr(imap, "fetch_rows", fetch_rows)
    asyncio.run(server.mcp.call_tool("list_emails", {"account": "alpha", "since": "2026-07-01"}))
    assert seen["alpha"]["since"] == dt.date(2026, 7, 1)
