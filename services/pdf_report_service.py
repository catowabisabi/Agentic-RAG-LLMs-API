"""
PDF Report Generator Service

Generates PDF reports from Markdown content.
Uses markdown → HTML → PDF pipeline (via xhtml2pdf / pdfkit fallback).

If no PDF library is available, falls back to saving the raw Markdown file.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPORT_OUTPUT_DIR = Path("data/reports")

# CSS for PDF styling
PDF_CSS = """
body {
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
    line-height: 1.6;
    color: #333;
    padding: 20px 40px;
}
h1 { font-size: 24px; color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 10px; }
h2 { font-size: 18px; color: #16213e; margin-top: 20px; }
h3 { font-size: 14px; color: #0f3460; }
table { border-collapse: collapse; width: 100%; margin: 15px 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background-color: #16213e; color: white; font-weight: bold; }
tr:nth-child(even) { background-color: #f8f9fa; }
code { background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
pre { background-color: #f4f4f4; padding: 12px; border-radius: 5px; overflow-x: auto; }
blockquote { border-left: 3px solid #16213e; padding-left: 15px; color: #666; margin: 10px 0; }
.header { text-align: center; margin-bottom: 30px; }
.footer { text-align: center; font-size: 10px; color: #999; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }
"""


class PDFReportError(Exception):
    """PDF Report generation errors."""
    pass


class PDFReportService:
    """
    Generate PDF (or Markdown) reports.

    Public async API:
      - ``generate_report(title, markdown_content, **opts)`` → create a report file
      - ``list_reports()`` → list generated reports
      - ``get_report(report_id)`` → get metadata for a report

    The service tries these backends in order:
      1. xhtml2pdf (pure-Python, no external deps)
      2. Raw Markdown saved as .md (fallback)
    """

    _instance: Optional["PDFReportService"] = None

    def __new__(cls) -> "PDFReportService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._backend = self._detect_backend()
        self._initialized = True
        logger.info(f"PDFReportService initialized – backend={self._backend}")

    @staticmethod
    def _detect_backend() -> str:
        try:
            import xhtml2pdf  # noqa: F401
            return "xhtml2pdf"
        except ImportError:
            pass
        try:
            import markdown  # noqa: F401
            return "markdown_only"
        except ImportError:
            pass
        return "raw_md"

    # -------------------------------------------------------- #
    # Public API
    # -------------------------------------------------------- #

    async def generate_report(
        self,
        title: str,
        markdown_content: str,
        author: str = "System",
        filename: Optional[str] = None,
        include_toc: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a report from Markdown content.

        Returns metadata dict including ``file_path``.
        """
        report_id = str(uuid.uuid4())[:8]
        ts = datetime.now()
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title).strip()
        base_name = filename or f"{safe_title}_{ts.strftime('%Y%m%d_%H%M%S')}"

        if self._backend == "xhtml2pdf":
            ext = ".pdf"
            out_path = REPORT_OUTPUT_DIR / f"{base_name}{ext}"
            await self._generate_pdf_xhtml2pdf(title, markdown_content, author, out_path, include_toc)
        else:
            ext = ".md"
            out_path = REPORT_OUTPUT_DIR / f"{base_name}{ext}"
            await self._save_markdown(title, markdown_content, author, out_path)

        meta = {
            "report_id": report_id,
            "title": title,
            "author": author,
            "format": ext.lstrip("."),
            "backend": self._backend,
            "file_path": str(out_path.resolve()),
            "file_name": out_path.name,
            "size_bytes": out_path.stat().st_size,
            "created_at": ts.isoformat(),
        }
        self._reports[report_id] = meta
        logger.info(f"Report generated: {out_path.name} ({meta['size_bytes']} bytes)")
        return meta

    async def list_reports(self, limit: int = 50) -> List[Dict[str, Any]]:
        items = list(self._reports.values())
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items[:limit]

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        return self._reports.get(report_id)

    async def generate_accounting_report(
        self,
        account_summary: Dict[str, Any],
        transactions: List[Dict[str, Any]],
        title: str = "Accounting Report",
        author: str = "System",
    ) -> Dict[str, Any]:
        """
        Generate an accounting report from structured data.
        Builds Markdown content then calls ``generate_report``.
        """
        acct = account_summary.get("account", {})
        lines = [
            f"# {title}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Author:** {author}",
            "",
            "---",
            "",
            "## Account Overview",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Name | {acct.get('name', 'N/A')} |",
            f"| Type | {acct.get('type', 'N/A')} |",
            f"| Currency | {acct.get('currency', 'N/A')} |",
            f"| Balance | ${account_summary.get('balance_display', acct.get('balance_display', 0)):.2f} |",
            f"| Total Income | ${account_summary.get('total_income', 0):.2f} |",
            f"| Total Expense | ${account_summary.get('total_expense', 0):.2f} |",
            f"| Pending | {account_summary.get('pending_count', 0)} |",
            f"| Reconciled | {account_summary.get('reconciled_count', 0)} |",
            "",
            "## Transactions",
            "",
        ]

        if transactions:
            lines.append("| # | Date | Type | Amount | Description | Status |")
            lines.append("|---|------|------|--------|-------------|--------|")
            for i, txn in enumerate(transactions, 1):
                amt = txn.get("amount_display", txn.get("amount", 0) / 100.0)
                lines.append(
                    f"| {i} "
                    f"| {txn.get('transaction_date', '')} "
                    f"| {txn.get('type', '')} "
                    f"| ${amt:.2f} "
                    f"| {txn.get('description', '')} "
                    f"| {txn.get('status', '')} |"
                )
        else:
            lines.append("*No transactions found.*")

        lines += ["", "---", f"*Report ID: auto-generated | Total transactions: {len(transactions)}*"]

        md_content = "\n".join(lines)
        return await self.generate_report(title=title, markdown_content=md_content, author=author)

    # -------------------------------------------------------- #
    # Backend implementations
    # -------------------------------------------------------- #

    async def _generate_pdf_xhtml2pdf(
        self, title: str, md_content: str, author: str, out_path: Path, include_toc: bool
    ) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._xhtml2pdf_sync(title, md_content, author, out_path, include_toc),
        )

    @staticmethod
    def _xhtml2pdf_sync(title: str, md_content: str, author: str, out_path: Path, include_toc: bool) -> None:
        import markdown
        from xhtml2pdf import pisa

        # Convert Markdown → HTML
        extensions = ["tables", "fenced_code", "codehilite", "toc"] if include_toc else ["tables", "fenced_code"]
        html_body = markdown.markdown(md_content, extensions=extensions)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>{PDF_CSS}</style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Author: {author} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
    {html_body}
    <div class="footer">
        <p>Generated by Agentic RAG System</p>
    </div>
</body>
</html>"""

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(out_path), "wb") as f:
            status = pisa.CreatePDF(html, dest=f)
            if status.err:
                raise PDFReportError(f"xhtml2pdf error: {status.err}")

    async def _save_markdown(
        self, title: str, md_content: str, author: str, out_path: Path
    ) -> None:
        header = (
            f"---\n"
            f"title: {title}\n"
            f"author: {author}\n"
            f"date: {datetime.now().isoformat()}\n"
            f"---\n\n"
        )
        full_content = header + md_content
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: out_path.write_text(full_content, encoding="utf-8"),
        )
