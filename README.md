# imap-mcp

Read-only MCP server that searches and reads mail across all your IMAP
accounts at once. Point it at any number of mailboxes (Gmail, Fastmail,
Migadu, iCloud, self-hosted, anything that speaks IMAP) and an MCP client
like Claude Code can list, search, and read across every one of them in a
single call.

Strictly read-only: no send, no delete, no flag changes. Fetches use
`BODY.PEEK`, so reading a message never marks it as read.

## Why IMAP

Most assistant integrations connect one Gmail or Outlook account at a time.
IMAP is the one protocol nearly every mail provider speaks, so one small
server covers all your accounts with a single read-only code path.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/LeeFlannery/imap-mcp
cd imap-mcp
cp accounts.example.toml accounts.toml
```

Edit `accounts.toml` with your accounts. It is gitignored and holds no
secrets: each account names an environment variable that must contain the
IMAP password at runtime. Provide those however you like:

```sh
export PERSONAL_IMAP_PASSWORD='...'   # plain env var
# or direnv, or a secrets manager, e.g. 1Password:
# op run --env-file=op.env -- uv run imap-mcp
```

Set `IMAP_MCP_ACCOUNTS=/path/to/accounts.toml` to keep the config elsewhere.

### Gmail / Google Workspace

With 2FA enabled, Google rejects the account password for IMAP. Generate an
app password at <https://myaccount.google.com/apppasswords> and use that.
The spaces Google displays in it are stripped automatically.

## Run

```sh
uv run imap-mcp
```

## Register with an MCP client

For Claude Code, add to `.mcp.json` (project) or your user MCP config:

```json
{
  "mcpServers": {
    "imap": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/imap-mcp", "imap-mcp"]
    }
  }
}
```

Make sure the password env vars are visible to the spawned process, or wrap
the command in your secret injector (`op run`, etc.).

## Tools

- `list_accounts()` -- configured accounts + live reachable status
- `list_emails(account?, since?, unread_only?, limit?)` -- recent mail, newest first; omit `account` to merge all
- `search_emails(query, account?, since?, limit?)` -- free-text search over sender/subject/body
- `get_email(account, id)` -- one full message (plain text preferred)

## License

MIT
