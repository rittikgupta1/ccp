# CCP — Central Context Package

A team knowledge base that lives in a GitHub repo. Save analyses, queries, playbooks, and decisions with one command. Role-based access control, AI quality review, and auto-generated summaries.

## Why

Work gets duplicated. One person does an analysis, another doesn't know and redoes it. CCP fixes this by giving every team a shared, searchable knowledge base with quality gates.

## Quick Start

### Setup (one-time, 2 minutes)

```bash
curl -sL https://raw.githubusercontent.com/your-org/ccp/main/setup.sh | bash
```

This clones the repo, configures your identity, installs the `kb` command, and sets up auto-sync.

### Save knowledge

```bash
# Save an analysis
kb "Weekend SLA drops 15% in Bangalore" --team data --type analysis

# Save from a file
kb "Fill rate model v2" --team data --type model --file output.md

# Pipe content
echo "SELECT * FROM jobs WHERE status='delivered'" | kb "Delivery query" --team data --type query

# Preview without saving
kb "Test entry" --team ops --dry-run
```

### What happens when you save

1. Content is scanned for secrets and PII (blocked if found)
2. AI reviews for quality — vague claims get flagged
3. **Admins** → direct commit to main
4. **Contributors** → PR created, second AI review runs, awaits merge

### For non-tech people (Claude Desktop)

After setup, just tell Claude:

> "Save this to the knowledge base under ops team. Title: Weekend runner shortage playbook"

Claude handles everything via the MCP integration.

## Repo Structure

```
ccp/
├── INDEX.md              # Auto-generated index of all entries
├── MASTER-CONTEXT.md     # AI summary of everything (updated bi-weekly)
├── ccp.yaml              # Configuration: teams, roles, scanner rules
├── teams/
│   ├── data/             # Data team entries
│   ├── ops/              # Ops team entries
│   ├── product/          # Product team entries
│   └── engineering/      # Engineering team entries
├── company/              # Cross-team entries
└── scripts/              # CCP engine
```

## Roles

| Role | Can do | Configured in |
|------|--------|---------------|
| **Admin** | Direct commit, skip AI review, merge PRs | `ccp.yaml` → `roles.admin.users` |
| **Reviewer** | Approve PRs from their team | `ccp.yaml` → `roles.reviewer.users` |
| **Contributor** | Submit PRs (needs approval) | Everyone else |

## Content Types

| Type | Description | Expiry |
|------|-------------|--------|
| `analysis` | SQL-backed findings, metrics | 90 days |
| `query` | Reusable SQL/PySpark snippets | 180 days |
| `playbook` | Operational processes | 90 days |
| `decision` | Decisions and rationale | 365 days |
| `insight` | Observations without hard data | 45 days |
| `model` | ML models and results | 180 days |

## AI Review

Two layers of quality control:

1. **Local review (Haiku)** — runs before commit, catches vague/unclear content
2. **PR review (Sonnet)** — runs on GitHub, catches duplicates and conflicts

The reviewer blocks content that:
- Makes vague claims without numbers
- States opinions as facts
- References queries without including them
- Contains secrets or PII

## Configuration

Edit `ccp.yaml` to customize teams, roles, content types, AI provider, and scanner patterns.

### AI Provider

```yaml
ai:
  provider: vertex              # "vertex" (GCP) or "anthropic" (direct API)
  project: your-gcp-project     # for vertex
  region: global                # for vertex
```

For Vertex AI: run `gcloud auth application-default login` once.
For Anthropic: set `ANTHROPIC_API_KEY` environment variable.

## Open Source

CCP is MIT licensed. To use it for your own team:

1. Fork this repo
2. Copy `ccp.example.yaml` → `ccp.yaml`
3. Edit teams, roles, and AI config
4. Share `setup.sh` with your team

## License

MIT
