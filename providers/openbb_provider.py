from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any

from config import Settings
from models import NormalizedSourceDocument, ProviderRequest


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
                body = self._render_filing_summary(filing)
                docs.append(
                    NormalizedSourceDocument(
                        document_id=f"{request.ticker}_{filing.report_type}_{filing.filing_date}",
                        title=f"{request.ticker} {filing.report_type} filed {filing.filing_date}",
                        source_type="sec_filing",
                        ticker=request.ticker,
                        source_reference=str(filing.report_url or filing.filing_url or ""),
                        event_date=str(filing.filing_date),
                        fetch_timestamp=fetched_at,
                        body_markdown=body,
                        metadata={
                            "report_type": filing.report_type,
                            "report_date": str(filing.report_date),
                            "filing_url": str(filing.filing_url or ""),
                            "report_url": str(filing.report_url or ""),
                            "primary_doc_description": str(filing.primary_doc_description or ""),
                        },
                    )
                )

        if "management_discussion" in request.source_types:
            mda = await SecManagementDiscussionAnalysisFetcher.fetch_data(
                {"symbol": request.ticker, "use_cache": True},
                {},
            )
            docs.append(
                NormalizedSourceDocument(
                    document_id=f"{request.ticker}_management_discussion_{mda.period_ending}",
                    title=f"{request.ticker} management discussion analysis",
                    source_type="management_discussion",
                    ticker=request.ticker,
                    source_reference=str(mda.url),
                    event_date=str(mda.period_ending),
                    fetch_timestamp=fetched_at,
                    body_markdown=self._render_mda(mda),
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
    def _render_filing_summary(filing: Any) -> str:
        return "\n".join(
            [
                f"# {filing.symbol} {filing.report_type} filing",
                "",
                f"- Filing date: {filing.filing_date}",
                f"- Report date: {filing.report_date}",
                f"- Filing type: {filing.report_type}",
                f"- Filing URL: {filing.filing_url}",
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
