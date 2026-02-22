"""
Tools Router

API endpoints for:
  - Accounting (accounts, transactions, reconciliation, audit)
  - OCR (image/PDF text extraction)
  - PDF Report generation
  - File management (move, copy, list, info)
  - Excel operations
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from utils.path_security import sanitize_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])

# Workspace root for OCR path sandboxing (same as FileManagerService)
_OCR_WORKSPACE_ROOT = Path(os.getenv("FILE_MANAGER_ROOT", ".")).resolve()


def _require_safe_file_path(file_path: str) -> str:
    """Validate a file path is within the workspace root. Raises HTTP 400 if not."""
    try:
        safe = sanitize_path(file_path, allowed_root=_OCR_WORKSPACE_ROOT)
        return str(safe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# ============================================================
# Pydantic request models
# ============================================================

# --- Accounting ---

class CreateAccountRequest(BaseModel):
    name: str
    account_type: str = "general"
    currency: str = "HKD"
    description: str = ""

class AddTransactionRequest(BaseModel):
    account_id: int
    type: str  # income | expense | transfer | adjustment
    amount: float
    description: str = ""
    reference: str = ""
    counterparty: str = ""
    category: str = ""
    transaction_date: str = ""

class ListTransactionsRequest(BaseModel):
    account_id: Optional[int] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 100
    offset: int = 0

class ReconcileRequest(BaseModel):
    transaction_ids: List[int]

class VoidRequest(BaseModel):
    transaction_id: int

class AuditLogRequest(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    limit: int = 100

class UpdateTransactionRequest(BaseModel):
    description: Optional[str] = None
    reference: Optional[str] = None
    counterparty: Optional[str] = None
    category: Optional[str] = None
    transaction_date: Optional[str] = None
    amount: Optional[float] = None
    tax_amount: Optional[float] = None
    tax_rate: Optional[float] = None

class CategoryRequest(BaseModel):
    name: str
    description: str = ""

class BudgetRequest(BaseModel):
    account_id: int
    period: str  # YYYY-MM
    amount: float
    category: str = ""

class BudgetStatusRequest(BaseModel):
    account_id: int
    period: str  # YYYY-MM

class PeriodCloseRequest(BaseModel):
    period: str  # YYYY-MM
    notes: str = ""

class ImportCSVRequest(BaseModel):
    account_id: int
    csv_text: str

class InvoiceRequest(BaseModel):
    account_id: int
    invoice_number: str
    amount: float
    counterparty: str = ""
    due_date: str = ""
    description: str = ""
    tax_amount: float = 0.0
    currency: str = "HKD"

class ListInvoicesRequest(BaseModel):
    account_id: Optional[int] = None
    status: Optional[str] = None

class AccountingReportRequest(BaseModel):
    account_id: int
    title: str = "Accounting Report"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

# --- OCR ---

class OCRFileRequest(BaseModel):
    file_path: str

class OCRBatchRequest(BaseModel):
    file_paths: List[str]

# --- PDF Report ---

class GenerateReportRequest(BaseModel):
    title: str
    markdown_content: str
    author: str = "System"

# (AccountingReportRequest defined above in accounting section)

# --- File Manager ---

class FileMoveRequest(BaseModel):
    src: str
    dest_folder: str
    overwrite: bool = False

class FileCopyRequest(BaseModel):
    src: str
    dest_folder: str
    overwrite: bool = False

class FileMoveBatchRequest(BaseModel):
    file_paths: List[str]
    dest_folder: str
    overwrite: bool = False

class MkdirRequest(BaseModel):
    path: str


# ============================================================
# Helper – lazily instantiate services
# ============================================================

def _get_accounting_service():
    from services.accounting_service import AccountingService
    return AccountingService()

def _get_ocr_service():
    from services.ocr_service import OCRService
    return OCRService()

def _get_pdf_report_service():
    from services.pdf_report_service import PDFReportService
    return PDFReportService()

def _get_file_manager_service():
    from services.file_manager_service import FileManagerService
    return FileManagerService()

def _get_excel_service():
    from services.excel_service import ExcelService
    return ExcelService()


# ============================================================
# ACCOUNTING endpoints
# ============================================================

@router.post("/accounting/accounts")
async def create_account(req: CreateAccountRequest):
    """Create a new accounting ledger account."""
    try:
        svc = _get_accounting_service()
        result = await svc.create_account(req.name, req.account_type, req.currency, req.description)
        return {"success": True, "account": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/accounting/accounts")
async def list_accounts():
    """List all accounts."""
    svc = _get_accounting_service()
    accounts = await svc.list_accounts()
    return {"success": True, "accounts": accounts, "count": len(accounts)}

@router.get("/accounting/accounts/{account_id}")
async def get_account(account_id: int):
    """Get a single account."""
    svc = _get_accounting_service()
    acct = await svc.get_account(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "account": acct}

@router.get("/accounting/accounts/{account_id}/summary")
async def get_account_summary(account_id: int):
    """Get account summary with totals."""
    try:
        svc = _get_accounting_service()
        result = await svc.get_account_summary(account_id)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/accounting/dashboard")
async def get_dashboard():
    """Get high-level dashboard."""
    svc = _get_accounting_service()
    result = await svc.get_dashboard()
    return {"success": True, **result}

@router.post("/accounting/transactions")
async def add_transaction(req: AddTransactionRequest):
    """Add a new transaction (入數)."""
    try:
        svc = _get_accounting_service()
        result = await svc.add_transaction(
            account_id=req.account_id,
            txn_type=req.type,
            amount=req.amount,
            description=req.description,
            reference=req.reference,
            counterparty=req.counterparty,
            category=req.category,
            transaction_date=req.transaction_date,
        )
        return {"success": True, "transaction": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/accounting/transactions/list")
async def list_transactions(req: ListTransactionsRequest):
    """List transactions with filters (對數)."""
    svc = _get_accounting_service()
    result = await svc.list_transactions(
        account_id=req.account_id,
        status=req.status,
        start_date=req.start_date,
        end_date=req.end_date,
        limit=req.limit,
        offset=req.offset,
    )
    return {"success": True, **result}

@router.post("/accounting/reconcile")
async def reconcile_transactions(req: ReconcileRequest):
    """Reconcile transactions (對數/核數)."""
    try:
        svc = _get_accounting_service()
        result = await svc.batch_reconcile(req.transaction_ids)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/accounting/void")
async def void_transaction(req: VoidRequest):
    """Void a transaction."""
    try:
        svc = _get_accounting_service()
        result = await svc.void_transaction(req.transaction_id)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/accounting/audit")
async def get_audit_log(req: AuditLogRequest):
    """Get audit trail."""
    svc = _get_accounting_service()
    logs = await svc.get_audit_log(
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        limit=req.limit,
    )
    return {"success": True, "audit_log": logs, "count": len(logs)}


@router.patch("/accounting/transactions/{transaction_id}")
async def update_transaction(transaction_id: int, req: UpdateTransactionRequest):
    """Update a pending transaction's fields."""
    svc = _get_accounting_service()
    result = await svc.update_transaction(
        transaction_id,
        description=req.description,
        reference=req.reference,
        counterparty=req.counterparty,
        category=req.category,
        transaction_date=req.transaction_date,
        amount=req.amount,
        tax_amount=req.tax_amount,
        tax_rate=req.tax_rate,
    )
    return {"success": True, **result}


@router.delete("/accounting/accounts/{account_id}")
async def archive_account(account_id: int):
    """Archive (soft-delete) an account."""
    svc = _get_accounting_service()
    result = await svc.archive_account(account_id)
    return {"success": True, **result}


@router.post("/accounting/categories")
async def create_category(req: CategoryRequest):
    """Create a transaction category."""
    svc = _get_accounting_service()
    result = await svc.create_category(req.name, req.description)
    return {"success": True, **result}


@router.get("/accounting/categories")
async def list_categories():
    """List all categories."""
    svc = _get_accounting_service()
    cats = await svc.list_categories()
    return {"success": True, "categories": cats, "count": len(cats)}


@router.delete("/accounting/categories/{category_id}")
async def delete_category(category_id: int):
    """Delete a category."""
    svc = _get_accounting_service()
    result = await svc.delete_category(category_id)
    return {"success": True, **result}


@router.post("/accounting/budgets")
async def set_budget(req: BudgetRequest):
    """Set (upsert) a budget for an account/period/category."""
    svc = _get_accounting_service()
    result = await svc.set_budget(req.account_id, req.period, req.amount, req.category)
    return {"success": True, **result}


@router.post("/accounting/budgets/status")
async def budget_status(req: BudgetStatusRequest):
    """Check budget utilisation for an account in a given period."""
    svc = _get_accounting_service()
    result = await svc.check_budget_status(req.account_id, req.period)
    return {"success": True, **result}


@router.post("/accounting/periods/close")
async def close_period(req: PeriodCloseRequest):
    """Close an accounting period (月結)."""
    svc = _get_accounting_service()
    result = await svc.close_period(req.period, req.notes)
    return {"success": True, **result}


@router.get("/accounting/periods")
async def list_periods():
    """List accounting periods."""
    svc = _get_accounting_service()
    periods = await svc.list_periods()
    return {"success": True, "periods": periods, "count": len(periods)}


@router.post("/accounting/import/csv")
async def import_csv(req: ImportCSVRequest):
    """Bulk-import transactions from CSV text."""
    svc = _get_accounting_service()
    result = await svc.import_transactions_csv(req.account_id, req.csv_text)
    return {"success": True, **result}


@router.post("/accounting/invoices")
async def create_invoice(req: InvoiceRequest):
    """Create an invoice / receivable."""
    svc = _get_accounting_service()
    result = await svc.create_invoice(
        account_id=req.account_id,
        invoice_number=req.invoice_number,
        amount=req.amount,
        counterparty=req.counterparty,
        due_date=req.due_date,
        description=req.description,
        tax_amount=req.tax_amount,
        currency=req.currency,
    )
    return {"success": True, **result}


@router.post("/accounting/invoices/list")
async def list_invoices(req: ListInvoicesRequest):
    """List invoices with optional filters."""
    svc = _get_accounting_service()
    invoices = await svc.list_invoices(account_id=req.account_id, status=req.status)
    return {"success": True, "invoices": invoices, "count": len(invoices)}


@router.patch("/accounting/invoices/{invoice_id}/paid")
async def mark_invoice_paid(invoice_id: int):
    """Mark an invoice as paid."""
    svc = _get_accounting_service()
    result = await svc.mark_invoice_paid(invoice_id)
    return {"success": True, **result}


# ============================================================
# OCR endpoints
# ============================================================

@router.post("/ocr/file")
async def ocr_file(req: OCRFileRequest):
    """Run OCR on a single file."""
    try:
        safe_path = _require_safe_file_path(req.file_path)
        svc = _get_ocr_service()
        result = await svc.ocr_file(safe_path)
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ocr/batch")
async def ocr_batch(req: OCRBatchRequest):
    """Run OCR on multiple files."""
    try:
        safe_paths = [_require_safe_file_path(p) for p in req.file_paths]
        svc = _get_ocr_service()
        result = await svc.ocr_batch(safe_paths)
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ocr/results")
async def list_ocr_results(limit: int = 50):
    """List recent OCR results."""
    svc = _get_ocr_service()
    results = await svc.list_results(limit=limit)
    return {"success": True, "results": results, "count": len(results)}

@router.get("/ocr/results/{result_id}")
async def get_ocr_result(result_id: str):
    """Get a specific OCR result."""
    svc = _get_ocr_service()
    result = await svc.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="OCR result not found")
    return {"success": True, **result}

@router.post("/ocr/upload")
async def ocr_upload(file: UploadFile = File(...)):
    """Upload a file and run OCR on it."""
    import tempfile, os
    try:
        svc = _get_ocr_service()
        # Save uploaded file to temp location
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = await svc.ocr_file(tmp_path)
            return {"success": True, **result}
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# PDF Report endpoints
# ============================================================

@router.post("/reports/generate")
async def generate_report(req: GenerateReportRequest):
    """Generate a PDF/MD report from Markdown content."""
    try:
        svc = _get_pdf_report_service()
        result = await svc.generate_report(req.title, req.markdown_content, author=req.author)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reports/accounting")
async def generate_accounting_report(req: AccountingReportRequest):
    """Generate an accounting report for a specific account with optional date range."""
    try:
        acct_svc = _get_accounting_service()
        pdf_svc = _get_pdf_report_service()
        summary = await acct_svc.get_account_summary(req.account_id)
        txn_data = await acct_svc.list_transactions(
            account_id=req.account_id,
            start_date=req.start_date,
            end_date=req.end_date,
            limit=500,
        )
        result = await pdf_svc.generate_accounting_report(
            account_summary=summary,
            transactions=txn_data.get("transactions", []),
            title=req.title,
            start_date=req.start_date,
            end_date=req.end_date,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/reports")
async def list_reports(limit: int = 50):
    """List generated reports."""
    svc = _get_pdf_report_service()
    reports = await svc.list_reports(limit=limit)
    return {"success": True, "reports": reports, "count": len(reports)}

@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get report metadata by ID."""
    svc = _get_pdf_report_service()
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True, **report}


# ============================================================
# File Manager endpoints
# ============================================================

@router.post("/files/move")
async def move_file(req: FileMoveRequest):
    """Move a file to a destination folder."""
    try:
        svc = _get_file_manager_service()
        result = await svc.move_file(req.src, req.dest_folder, overwrite=req.overwrite)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files/copy")
async def copy_file(req: FileCopyRequest):
    """Copy a file to a destination folder."""
    try:
        svc = _get_file_manager_service()
        result = await svc.copy_file(req.src, req.dest_folder, overwrite=req.overwrite)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files/move-batch")
async def move_batch(req: FileMoveBatchRequest):
    """Move multiple files to a destination folder."""
    try:
        svc = _get_file_manager_service()
        result = await svc.move_batch(req.file_paths, req.dest_folder, overwrite=req.overwrite)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/files/list")
async def list_directory(path: str = "."):
    """List files and folders in a directory."""
    try:
        svc = _get_file_manager_service()
        result = await svc.list_directory(path)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/files/info")
async def get_file_info(path: str):
    """Get file metadata."""
    try:
        svc = _get_file_manager_service()
        result = await svc.get_file_info(path)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files/mkdir")
async def create_directory(req: MkdirRequest):
    """Create a directory."""
    try:
        svc = _get_file_manager_service()
        result = await svc.create_directory(req.path)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
