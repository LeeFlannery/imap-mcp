"""Account registry. Loads non-secret config from accounts.toml; resolves each
account's password from the environment at runtime (export it, use direnv, a
secrets manager like 1Password's `op run`, whatever fits your setup)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Default when $IMAP_MCP_ACCOUNTS is unset: accounts.toml at the project root
# (src/imap_mcp/accounts.py -> two parents up).
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "accounts.toml"


@dataclass(frozen=True)
class Account:
    key: str
    label: str
    email: str
    host: str
    port: int
    password_env: str
    enabled: bool

    def password(self) -> str | None:
        """Password from the named env var, or None if unset/empty."""
        pw = os.environ.get(self.password_env) or None
        # Google shows app passwords with spaces for readability; IMAP wants them bare.
        if pw and self.host.endswith("gmail.com"):
            pw = pw.replace(" ", "")
        return pw

    def require_password(self) -> str:
        pw = self.password()
        if not pw:
            raise RuntimeError(f"no password for {self.key} (env {self.password_env} unset)")
        return pw


@lru_cache(maxsize=1)
def _load() -> dict[str, Account]:
    override = os.environ.get("IMAP_MCP_ACCOUNTS")
    path = Path(override) if override else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"no account config at {path}; copy accounts.example.toml to "
            "accounts.toml and fill in your accounts (or point "
            "IMAP_MCP_ACCOUNTS at a config file)"
        )
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    out: dict[str, Account] = {}
    for a in raw.get("account", []):
        acct = Account(
            key=a["key"],
            label=a.get("label", a["email"]),
            email=a["email"],
            host=a["host"],
            port=int(a.get("port", 993)),
            password_env=a["password_env"],
            enabled=bool(a.get("enabled", True)),
        )
        out[acct.key] = acct
    return out


def reset() -> None:
    """Forget the cached registry so the next call reloads from disk."""
    _load.cache_clear()


def all_accounts() -> list[Account]:
    return list(_load().values())


def enabled_accounts() -> list[Account]:
    return [a for a in all_accounts() if a.enabled]


def get_account(key: str) -> Account:
    accts = _load()
    if key not in accts:
        raise KeyError(f"unknown account {key!r}; known: {', '.join(accts)}")
    return accts[key]
