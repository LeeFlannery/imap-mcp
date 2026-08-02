"""Read-only IMAP helpers built on imap-tools.

Every fetch uses mark_seen=False, so imap-tools issues BODY.PEEK and reading a
message never sets the \\Seen flag in the real mailbox.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from imap_tools import AND, OR, MailBox, MailMessageFlags

from .accounts import Account


@contextmanager
def open_box(account: Account) -> Iterator[MailBox]:
    """Yield a logged-in, read-only mailbox for the account. Raises on failure."""
    pw = account.require_password()
    box = MailBox(account.host, port=account.port)
    box.login(account.email, pw, initial_folder="INBOX")
    try:
        yield box
    finally:
        with suppress(Exception):
            box.logout()


def _snippet(msg, length: int = 200) -> str:
    body = (msg.text or msg.html or "").strip().replace("\r", " ").replace("\n", " ")
    return body[:length]


def _base_fields(msg, account_key: str) -> dict:
    return {
        "account": account_key,
        "id": msg.uid,
        "from": msg.from_,
        "to": list(msg.to),
        "subject": msg.subject,
        "date": msg.date.isoformat() if msg.date else None,
        "unread": MailMessageFlags.SEEN not in msg.flags,
    }


def row(msg, account_key: str) -> dict:
    """Compact metadata row for list/search results."""
    return {**_base_fields(msg, account_key), "snippet": _snippet(msg)}


def _criteria(query: str | None, since: dt.date | None, unread_only: bool):
    if not (query or since or unread_only):
        return AND(all=True)
    text = [OR(from_=query, subject=query, text=query)] if query else []
    # AND drops None-valued kwargs, so absent filters simply vanish.
    return AND(*text, date_gte=since, seen=False if unread_only else None)


def fetch_rows(
    account: Account,
    *,
    query: str | None = None,
    since: dt.date | None = None,
    unread_only: bool = False,
    limit: int = 25,
) -> list[dict]:
    crit = _criteria(query, since, unread_only)
    with open_box(account) as box:
        msgs = box.fetch(
            crit,
            limit=limit,
            reverse=True,  # newest first
            mark_seen=False,  # BODY.PEEK -- never touch \Seen
            bulk=True,
        )
        return [row(m, account.key) for m in msgs]


def fetch_one(account: Account, uid: str) -> dict | None:
    """Full message by UID (INBOX). Returns None if not found."""
    with open_box(account) as box:
        msgs = list(box.fetch(AND(uid=uid), mark_seen=False))
        if not msgs:
            return None
        m = msgs[0]
        return {
            **_base_fields(m, account.key),
            "cc": list(m.cc),
            "message_id": m.headers.get("message-id", [None])[0],
            "body": (m.text or m.html or "").strip(),
        }
