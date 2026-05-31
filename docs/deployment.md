# Deployment

## Runtime

The first backend is a small HTTP API that accepts challenge requests and Codex usage
snapshot uploads. It stores only the metadata required to grant and audit badges.

Install the package and runtime dependency:

```bash
python3 -m pip install -e .
```

Configure TiDB with either environment variable:

```bash
export TiDB_DSN='mysql://user:password@host:4000/token_badge?ssl=true'
```

`TiDB_DSN` is preferred. `TiDB_DNS` is also accepted as an alias because that was the
name used during early project setup.

Initialize the database schema:

```bash
token-badge init-db
```

Run the API:

```bash
token-badge serve --host 0.0.0.0 --port "${PORT:-8000}"
```

Health check:

```bash
curl http://localhost:8000/healthz
```

## Collector Upload

Users can upload Codex usage metadata directly from the collector:

```bash
token-badge codex \
  --github <github-login> \
  --github-node-id <github-node-id> \
  --collector-id <collector-installation-id> \
  --upload-url https://token-badge.example.com \
  --json
```

If `--challenge` is omitted, the collector asks the backend for a fresh challenge first.

Claude Code uses the same upload path:

```bash
token-badge claude \
  --github <github-login> \
  --github-node-id <github-node-id> \
  --collector-id <collector-installation-id> \
  --upload-url https://token-badge.example.com \
  --json
```

## Stored Metadata

The backend accepts and stores only:

- `github_login`
- `github_node_id`
- `collector_installation_id`
- `provider`
- `usage_kind`
- `source`
- `total_tokens`
- `trust_level`
- `challenge_nonce`
- `report_hash`
- summarized `raw_totals`

The API rejects full `ccusage` reports, monthly/session rows, model breakdowns, prompts,
messages, file paths, and other logs. The current providers accepted by the backend are
`codex` and `claude`; future provider adapters are tracked separately.
