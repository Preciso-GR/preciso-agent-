from __future__ import annotations

from pathlib import Path

from config import Settings
from groq_client import GroqAgentClient
from models import ExtractionArtifact, NormalizedSourceDocument
from storage.files import slugify, write_extraction_payload


def build_extractions(
    settings: Settings,
    groq_client: GroqAgentClient,
    documents: list[NormalizedSourceDocument],
) -> list[ExtractionArtifact]:
    artifacts: list[ExtractionArtifact] = []
    for document in documents:
        if not document.output_path:
            artifacts.append(
                ExtractionArtifact(
                    document_id=document.document_id,
                    source_path="",
                    extraction_path="",
                    status="error",
                    message="document has no stored source path",
                )
            )
            continue

        source_path = Path(document.output_path)
        payload = groq_client.extract_graph_payload(
            document_id=document.document_id,
            file_path=str(source_path),
            markdown=source_path.read_text(encoding="utf-8"),
        )
        payload["document_id"] = document.document_id
        extraction_path = write_extraction_payload(settings, slugify(source_path.stem), payload)
        artifacts.append(
            ExtractionArtifact(
                document_id=document.document_id,
                source_path=str(source_path),
                extraction_path=str(extraction_path),
                status="success",
            )
        )
    return artifacts

