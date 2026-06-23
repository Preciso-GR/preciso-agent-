from __future__ import annotations

import json
import re
from pathlib import Path

from config import Settings
from models import NormalizedSourceDocument


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return cleaned or "document"


def write_source_documents(
    settings: Settings,
    documents: list[NormalizedSourceDocument],
) -> list[NormalizedSourceDocument]:
    written: list[NormalizedSourceDocument] = []
    for document in documents:
        event_date = (document.event_date or document.fetch_timestamp[:10]).replace(":", "-")
        filename = f"{slugify(document.ticker)}_{slugify(document.source_type)}_{slugify(event_date)}.md"
        source_path = settings.sources_dir / filename
        manifest_path = settings.manifests_dir / f"{source_path.stem}.json"

        source_path.write_text(document.body_markdown, encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "document_id": document.document_id,
                    "title": document.title,
                    "ticker": document.ticker,
                    "source_type": document.source_type,
                    "source_reference": document.source_reference,
                    "event_date": document.event_date,
                    "fetch_timestamp": document.fetch_timestamp,
                    "metadata": document.metadata,
                    "source_path": str(source_path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        written.append(document.model_copy(update={"output_path": str(source_path)}))
    return written


def write_extraction_payload(settings: Settings, document_stem: str, payload: dict) -> Path:
    output_path = settings.extractions_dir / f"{document_stem}_extracted.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path

