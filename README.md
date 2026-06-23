# Preciso Agent

`preciso-agent` is a local chat agent that uses:
- **OpenBB** as the data provider layer
- **Groq** as the orchestration and extraction model
- **Preciso** from the parent repo as the graph ingestion and query engine

## Workflow

1. Ask the agent to fetch finance data.
2. The agent pulls SEC-oriented source material through OpenBB.
3. It writes normalized Markdown files to `workspace/to_be_extracted/`.
4. It generates Preciso-compatible extraction JSON into `workspace/extractions/`.
5. It calls Preciso ingestion tools from the parent repo.
6. It can optionally run a graph query after ingestion.

## Current v1 data path

- SEC filing metadata
- Management discussion and analysis text
- Earnings context placeholder document

This keeps the provider layer source-first and compatible with Preciso's parser-free contract.

## Environment

Create `preciso-agent/.env` with:

```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Optional:

```bash
PRECISO_REPO_ROOT=/absolute/path/to/preciso-graphrag
PRECISO_AGENT_WORKSPACE=/absolute/path/to/workspace
OPENBB_SEC_FORM_TYPES=10-K,10-Q,8-K
PRECISO_QUERY_MODE=mix
```

## Run

```bash
cd preciso-agent
python3 main.py
```

## Example prompts

- `Fetch AAPL latest filing data from OpenBB, ingest it into Preciso, and stop after ingestion.`
- `Fetch NVDA filing and management discussion data, ingest it, then tell me the main strategic themes.`
- `Query the existing graph for TSLA risk factors.`

## Workspace

- `workspace/to_be_extracted/`: normalized source Markdown files
- `workspace/extractions/`: graph extraction JSON files
- `workspace/manifests/`: provenance manifests for stored documents

## Notes

- The current OpenBB install in this environment uses the newer package-builder layout, so the agent integrates with the SEC fetchers directly.
- The agent uses a local `HOME` override while fetching OpenBB data so OpenBB cache/settings stay inside this project instead of trying to write to the global home directory.
- Streamlit is intentionally out of scope for v1. The primary entrypoint is the CLI chat loop.

