from __future__ import annotations

import asyncio
import html
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from config import Settings
from models import NormalizedSourceDocument, ProviderRequest

# The SEC requires a descriptive User-Agent on EDGAR document requests and will
# block requests without one. Override via SEC_USER_AGENT (e.g. "name email").
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "preciso-agent (contact@example.com)")

# How much of a filing to ingest, and how:
#   SEC_FILING_MODE = "truncate" (default) -> one document, capped at MAX_CHARS.
#                     "chunks"             -> split the whole filing into pieces
#                                             of MAX_CHARS each (up to MAX_CHUNKS),
#                                             so the full document is covered.
# Raise SEC_FILING_MAX_CHARS to ingest more text per document/chunk (0 = no cap,
# only meaningful in truncate mode). A full 10-K is ~200K+ chars.
SEC_FILING_MODE = (os.getenv("SEC_FILING_MODE", "truncate").strip().lower() or "truncate")
SEC_FILING_MAX_CHARS = int(os.getenv("SEC_FILING_MAX_CHARS", "50000"))
SEC_FILING_MAX_CHUNKS = int(os.getenv("SEC_FILING_MAX_CHUNKS", "6"))


class OpenBBProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_documents(self, request: ProviderRequest) -> list[NormalizedSourceDocument]:
        previous_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.settings.openbb_home)
        try:
            return asyncio.run(self._fetch_documents_async(request))
        finally:
            if previous_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = previous_home

    async def _fetch_documents_async(self, request: ProviderRequest) -> list[NormalizedSourceDocument]:
        from openbb_sec.models.company_filings import SecCompanyFilingsFetcher
        from openbb_sec.models.management_discussion_analysis import (
            SecManagementDiscussionAnalysisFetcher,
        )

        docs: list[NormalizedSourceDocument] = []
        fetched_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        form_types = ",".join(request.form_types)
        source_format = self.settings.openbb_source_format

        if "sec_filing" in request.source_types:
            filings = await SecCompanyFilingsFetcher.fetch_data(
                {
                    "symbol": request.ticker,
                    "form_type": form_types,
                    "limit": request.max_documents,
                    "use_cache": True,
                },
                {},
            )
            for filing in filings[: request.max_documents]:
                filing_payload = filing.model_dump() if hasattr(filing, "model_dump") else {}
                filing_symbol = str(getattr(filing, "symbol", request.ticker) or request.ticker)
                filing_reference = str(
                    getattr(filing, "report_url", None)
                    or getattr(filing, "filing_url", None)
                    or getattr(filing, "filing_detail_url", None)
                    or ""
                )
                base_metadata = {
                    "symbol": filing_symbol,
                    "report_type": filing.report_type,
                    "report_date": str(filing.report_date),
                    "filing_url": str(
                        getattr(filing, "filing_url", None)
                        or getattr(filing, "filing_detail_url", None)
                        or ""
                    ),
                    "report_url": str(filing.report_url or ""),
                    "primary_doc_description": str(filing.primary_doc_description or ""),
                }

                # Download the actual filing document at report_url; fall back to
                # the metadata-only render if the document can't be fetched.
                filing_text = self._download_filing_text(filing_reference)
                if filing_text:
                    segments = self._segment_filing_text(filing_text)
                else:
                    segments = [
                        self._render_filing_raw(symbol=filing_symbol, payload=filing_payload)
                        if source_format == "raw"
                        else self._render_filing_summary(filing)
                    ]

                total = len(segments)
                for idx, segment in enumerate(segments, start=1):
                    suffix = f"_part{idx}" if total > 1 else ""
                    part_label = f" (part {idx}/{total})" if total > 1 else ""
                    body = (
                        self._render_filing_document(
                            symbol=filing_symbol,
                            report_type=str(filing.report_type),
                            filing_date=str(filing.filing_date),
                            url=filing_reference,
                            text=segment,
                            part_label=part_label,
                        )
                        if filing_text
                        else segment
                    )
                    docs.append(
                        NormalizedSourceDocument(
                            document_id=f"{filing_symbol}_{filing.report_type}_{filing.filing_date}{suffix}",
                            title=f"{filing_symbol} {filing.report_type} filed {filing.filing_date}{part_label}",
                            source_type="sec_filing",
                            ticker=filing_symbol,
                            source_reference=filing_reference,
                            event_date=str(filing.filing_date),
                            fetch_timestamp=fetched_at,
                            body_markdown=body,
                            metadata={**base_metadata, "part": idx, "parts_total": total},
                        )
                    )

        if "management_discussion" in request.source_types:
            mda = await SecManagementDiscussionAnalysisFetcher.fetch_data(
                {"symbol": request.ticker, "use_cache": True},
                {},
            )
            mda_payload = mda.model_dump() if hasattr(mda, "model_dump") else {}
            docs.append(
                NormalizedSourceDocument(
                    document_id=f"{request.ticker}_management_discussion_{mda.period_ending}",
                    title=f"{request.ticker} management discussion analysis",
                    source_type="management_discussion",
                    ticker=request.ticker,
                    source_reference=str(mda.url),
                    event_date=str(mda.period_ending),
                    fetch_timestamp=fetched_at,
                    body_markdown=(
                        self._render_mda_raw(symbol=request.ticker, payload=mda_payload)
                        if source_format == "raw"
                        else self._render_mda(mda)
                    ),
                    metadata={
                        "calendar_year": int(mda.calendar_year),
                        "calendar_period": str(mda.calendar_period),
                        "report_type": str(mda.report_type),
                    },
                )
            )

        if "earnings_calendar" in request.source_types:
            docs.append(
                NormalizedSourceDocument(
                    document_id=f"{request.ticker}_earnings_context_{fetched_at[:10]}",
                    title=f"{request.ticker} earnings context snapshot",
                    source_type="earnings_calendar",
                    ticker=request.ticker,
                    source_reference="openbb-sec-derived-context",
                    event_date=fetched_at[:10],
                    fetch_timestamp=fetched_at,
                    body_markdown=self._render_earnings_context(request),
                    metadata={"note": "OpenBB SEC-backed earnings context placeholder for v1"},
                )
            )

        if not docs:
            raise ValueError(
                f"No OpenBB documents were returned for ticker {request.ticker} and source types {request.source_types}."
            )

        return docs

    @staticmethod
    def _download_filing_text(url: str) -> str | None:
        """Fetch the actual SEC filing document and reduce it to readable text.

        Returns None on any failure (missing URL, network error, empty body) so
        the caller can fall back to the metadata-only render.
        """
        if not url:
            return None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, ValueError, TimeoutError, OSError):
            return None

        # Drop script/style blocks, then strip remaining tags and collapse space.
        without_blocks = re.sub(
            r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.IGNORECASE | re.DOTALL
        )
        text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", without_blocks))).strip()
        if not text:
            return None

        # Inline-XBRL filings begin with a large block of taxonomy/metadata noise.
        # Skip to the cover page so the ingested body is the readable filing.
        anchors = ("UNITED STATES SECURITIES AND EXCHANGE COMMISSION", "FORM 10-K", "FORM 10-Q", "FORM 8-K")
        starts = [text.find(a) for a in anchors]
        starts = [pos for pos in starts if pos != -1]
        if starts:
            text = text[min(starts):].strip()
        return text or None

    @staticmethod
    def _segment_filing_text(text: str) -> list[str]:
        """Split filing text into ingestion segments per SEC_FILING_MODE.

        truncate -> a single (optionally capped) segment.
        chunks   -> consecutive slices of SEC_FILING_MAX_CHARS, up to MAX_CHUNKS,
                    so the whole filing is covered across multiple documents.
        """
        if SEC_FILING_MODE == "chunks" and SEC_FILING_MAX_CHARS > 0:
            size = SEC_FILING_MAX_CHARS
            pieces = [text[i : i + size] for i in range(0, len(text), size)]
            if SEC_FILING_MAX_CHUNKS and len(pieces) > SEC_FILING_MAX_CHUNKS:
                pieces = pieces[:SEC_FILING_MAX_CHUNKS]
                pieces[-1] = pieces[-1].rstrip() + "\n\n[... filing truncated: raised SEC_FILING_MAX_CHUNKS to ingest more ...]"
            return [p.strip() for p in pieces if p.strip()]

        # truncate mode (default)
        if SEC_FILING_MAX_CHARS and len(text) > SEC_FILING_MAX_CHARS:
            text = text[:SEC_FILING_MAX_CHARS].rstrip() + "\n\n[... filing truncated: raise SEC_FILING_MAX_CHARS or use SEC_FILING_MODE=chunks ...]"
        return [text]

    @staticmethod
    def _render_filing_document(
        *, symbol: str, report_type: str, filing_date: str, url: str, text: str, part_label: str = ""
    ) -> str:
        return "\n".join(
            [
                f"# {symbol} {report_type} filing (full document){part_label}",
                "",
                f"- Filing date: {filing_date}",
                f"- Source URL: {url}",
                "",
                "## Filing text",
                "",
                text,
            ]
        )

    @staticmethod
    def _render_filing_summary(filing: Any) -> str:
        symbol = str(getattr(filing, "symbol", "") or "UNKNOWN")
        filing_url = str(
            getattr(filing, "filing_url", None)
            or getattr(filing, "filing_detail_url", None)
            or ""
        )
        return "\n".join(
            [
                f"# {symbol} {filing.report_type} filing",
                "",
                f"- Filing date: {filing.filing_date}",
                f"- Report date: {filing.report_date}",
                f"- Filing type: {filing.report_type}",
                f"- Filing URL: {filing_url}",
                f"- Report URL: {filing.report_url}",
                f"- Primary document description: {filing.primary_doc_description or 'N/A'}",
                "",
                "## Filing metadata",
                "",
                f"The company filed a {filing.report_type} with accession number {filing.accession_number}. "
                f"The filing references the primary document {filing.primary_doc or 'unknown'}. "
                f"Use this filing as a graph memory anchor for company reporting events, timelines, and disclosures.",
            ]
        )

    @staticmethod
    def _render_mda(mda: Any) -> str:
        return "\n".join(
            [
                f"# {mda.symbol} management discussion and analysis",
                "",
                f"- Report type: {mda.report_type}",
                f"- Period ending: {mda.period_ending}",
                f"- Calendar year: {mda.calendar_year}",
                f"- Calendar period: {mda.calendar_period}",
                f"- Source URL: {mda.url}",
                "",
                "## Extracted discussion",
                "",
                str(mda.content).strip(),
            ]
        )

    @staticmethod
    def _render_earnings_context(request: ProviderRequest) -> str:
        return "\n".join(
            [
                f"# {request.ticker} earnings context",
                "",
                "## Context",
                "",
                f"This document was created as a v1 earnings context placeholder for {request.ticker}. "
                "It should be used alongside SEC filing and management discussion artifacts when building the graph.",
                "",
                "## Intended usage",
                "",
                "- Pair with the latest 10-K or 10-Q filing metadata.",
                "- Pair with management discussion text for narrative context.",
                "- Use graph queries after ingestion to ask about recurring risks, strategy shifts, or management themes.",
            ]
        )

    @staticmethod
    def _render_filing_raw(*, symbol: str, payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# {symbol} SEC filing (raw OpenBB payload)",
                "",
                "```json",
                json.dumps(payload, indent=2, default=str),
                "```",
            ]
        )

    @staticmethod
    def _render_mda_raw(*, symbol: str, payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# {symbol} management discussion (raw OpenBB payload)",
                "",
                "```json",
                json.dumps(payload, indent=2, default=str),
                "```",
            ]
        )
