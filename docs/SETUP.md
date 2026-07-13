# Preciso Agent — Setup Guide

Zero-to-running steps for trying the agent out. At the end you'll have a CLI
chat agent that fetches SEC data (or reads your own files), extracts a
knowledge graph with an LLM, and ingests it into Preciso — all locally.

## What you're setting up

```
preciso-agent/                  ← this repo: the CLI chat agent
├── preciso-graphrag/           ← the graph engine, cloned INSIDE the agent folder
│   └── GRAPH_IS_HERE/          ← your knowledge graph lives here after ingestion
├── workspace/
│   ├── inbox/                  ← drop your own .md/.txt files here
│   ├── to_be_extracted/        ← normalized source documents (agent writes these)
│   ├── extractions/            ← graph extraction JSON (agent writes these)
│   └── manifests/              ← provenance records
└── .env                        ← your configuration
```

The agent talks to Preciso through the same `graphrag-mcp` stdio server any
external agent (Claude Code, Codex, ...) uses — you're dogfooding the real
product surface.

## Prerequisites

- **Python 3.10+** (`python3 --version`)
- **git**
- An API key for **one** LLM provider: [Groq](https://console.groq.com),
  [Nebius Token Factory](https://tokenfactory.nebius.com),
  [Anthropic](https://console.anthropic.com), or AWS credentials for Bedrock.

## 1. Clone both repos

```bash
git clone https://github.com/Preciso-GR/preciso-agent-.git preciso-agent
cd preciso-agent

# The graph engine goes INSIDE the agent folder (it's gitignored here).
git clone https://github.com/Preciso-GR/preciso-graphrag.git
```

The agent auto-detects the nested checkout — no path configuration needed. If
you already have `preciso-graphrag` checked out somewhere else (e.g. as a
sibling in the PRECISO workspace), skip the second clone; a sibling checkout
is detected too, and `PRECISO_REPO_ROOT` in `.env` overrides everything.

## 2. Create a virtualenv and install dependencies

One venv covers both the agent and the graph engine (the MCP server is spawned
from the agent's environment, so it inherits the activated venv):

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt                    # agent deps
pip install -r preciso-graphrag/requirements.txt   # graph engine deps
```

> Using Bedrock? Also run `pip install 'anthropic[bedrock]'`.
>
> Alternative: if you keep `preciso-graphrag` elsewhere with its own `.venv`,
> the MCP launcher prefers that venv automatically — nothing else to wire up.

## 3. Configure `.env`

```bash
cp .env.example .env
```

Then edit `.env`. Pick **one** LLM provider block:

```bash
# --- Groq (default) ---
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# --- or Nebius Token Factory (OpenAI-compatible) ---
# LLM_PROVIDER=nebius
# NEBIUS_API_KEY=your_key_here
# NEBIUS_MODEL=meta-llama/Llama-3.3-70B-Instruct

# --- or Claude via the Anthropic API ---
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your_key_here

# --- or Claude via Amazon Bedrock (uses your AWS credential chain) ---
# LLM_PROVIDER=bedrock
# AWS_REGION=us-east-1
```

And set your SEC identity — **EDGAR blocks document downloads without a
descriptive User-Agent**, and without it filings silently fall back to
metadata-only stubs:

```bash
SEC_USER_AGENT=Your Name your@email.com
```

Optional knobs (sane defaults, skip on a first run):

```bash
# How much of each SEC filing to ingest:
#   truncate (default) -> one document capped at SEC_FILING_MAX_CHARS
#   chunks             -> split the whole filing across multiple documents
SEC_FILING_MODE=truncate
SEC_FILING_MAX_CHARS=50000

# mcp (default, talks to the graphrag-mcp server) | inprocess (direct import)
PRECISO_CLIENT_MODE=mcp
```

## 4. Run it

```bash
python3 main.py
```

You'll see the PRECISO wordmark in the red-velvet terminal theme, followed by
the active configuration:

```
██████╗ ██████╗ ███████╗ ██████╗██╗███████╗ ██████╗
...
           · local-first GraphRAG agent ·
────────────────────────────────────────────────────
  LLM provider  groq
  Data sources  OpenBB SEC + local inbox (...)
  Graph engine  Preciso via mcp backend
  Preciso repo  /path/to/preciso-agent/preciso-graphrag
────────────────────────────────────────────────────
Type 'quit' to exit.
```

Check the `Preciso repo` line — it should point at your `preciso-graphrag`
checkout. (Set `NO_COLOR=1` if you don't want the colors.)

## 5. First prompts to try

```
Fetch AAPL latest filing data from OpenBB, ingest it into Preciso, and stop after ingestion.
```

Then query what you just built:

```
Query the existing graph for AAPL risk factors.
```

Or do both in one shot:

```
Fetch NVDA filing and management discussion data, ingest it, then tell me the main strategic themes.
```

To use **your own documents** instead of SEC data, drop `.md`/`.txt` files
into `workspace/inbox/` and say:

```
Ingest my files in the inbox folder, then summarize the key themes.
```

## 6. Where things end up

| Location | What |
|----------|------|
| `workspace/to_be_extracted/` | normalized Markdown of every fetched document |
| `workspace/extractions/` | the extraction JSON the LLM produced |
| `workspace/manifests/` | provenance record per document (source URL, timestamps) |
| `preciso-graphrag/GRAPH_IS_HERE/` | the knowledge graph itself |

The graph persists between runs — re-running the agent adds to it, and any MCP
client (Claude Code, Codex, ...) pointed at the same `preciso-graphrag`
checkout queries the same graph.

## Troubleshooting

**`Failed to start graphrag-mcp server: ...`**
The Preciso checkout wasn't found or its dependencies aren't installed. Check
the `Preciso repo` line in the startup banner; if it's wrong, set
`PRECISO_REPO_ROOT=/absolute/path/to/preciso-graphrag` in `.env`. If the path
is right, make sure step 2 installed `preciso-graphrag/requirements.txt` into
the active venv.

**Filings come back as short metadata stubs instead of full text**
`SEC_USER_AGENT` isn't set (or isn't descriptive). EDGAR rejects anonymous
downloads and the agent falls back to metadata-only rendering.

**Answers look generic / extraction is shallow**
The LLM provider isn't configured (no API key), so the agent is running on its
deterministic fallback heuristics. Set the key for your chosen `LLM_PROVIDER`
in `.env` — the startup banner shows which provider is active.

**`Unknown LLM_PROVIDER '...'`**
Use one of `groq`, `nebius`, `anthropic`, `bedrock`.

**Nebius errors about the model or endpoint**
Model IDs are the full Hugging Face-style names (e.g.
`meta-llama/Llama-3.3-70B-Instruct`). If your account uses the legacy AI
Studio endpoint, set `NEBIUS_BASE_URL=https://api.studio.nebius.com/v1/`.

**No banner colors**
Colors are disabled on non-TTY output and when `NO_COLOR` is set — that's by
design (pipes, CI logs).
