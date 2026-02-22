"""
Accounting Service

SQLite-based accounting database for:
- Transaction management (入數 / data entry)
- Reconciliation (對數 / matching)
- Audit trail
- Account balances and reports

All monetary values stored in cents (integer) for precision.
"""

import logging
import sqlite3
import json
import asyncio
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from functools import partial

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

DB_DIR = Path("data/accounting")
DB_NAME = "accounting.db"


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    RECONCILED = "reconciled"
    VOIDED = "voided"
    FLAGGED = "flagged"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RECONCILE = "reconcile"
    VOID = "void"
    EXPORT = "export"


# ============================================================
# AccountingService
# ============================================================

class AccountingService:
    """
    SQLite-backed accounting service.

    Thread-safe via asyncio.Lock + run_in_executor for all DB calls.
    """

    _instance: Optional["AccountingService"] = None

    def __new__(cls) -> "AccountingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._lock = asyncio.Lock()
        self._db_path = DB_DIR / DB_NAME
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._initialized = True
        logger.info(f"AccountingService initialized – DB at {self._db_path}")

    # ------------------------------------------------------ #
    # DB bootstrap
    # ------------------------------------------------------ #

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL UNIQUE,
                    type        TEXT NOT NULL DEFAULT 'general',
                    currency    TEXT NOT NULL DEFAULT 'HKD',
                    balance     INTEGER NOT NULL DEFAULT 0,
                    description TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id      INTEGER NOT NULL REFERENCES accounts(id),
                    type            TEXT NOT NULL,
                    amount          INTEGER NOT NULL,
                    description     TEXT,
                    reference       TEXT,
                    counterparty    TEXT,
                    category        TEXT,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    reconciled_at   TEXT,
                    transaction_date TEXT NOT NULL DEFAULT (date('now')),
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id   INTEGER NOT NULL,
                    action      TEXT NOT NULL,
                    old_value   TEXT,
                    new_value   TEXT,
                    user        TEXT DEFAULT 'system',
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account_id);
                CREATE INDEX IF NOT EXISTS idx_txn_status  ON transactions(status);
                CREATE INDEX IF NOT EXISTS idx_txn_date    ON transactions(transaction_date);
                CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);

                -- Categories lookup table
                CREATE TABLE IF NOT EXISTS categories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );

                -- Budget tracking per account per period
                CREATE TABLE IF NOT EXISTS budgets (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id  INTEGER NOT NULL REFERENCES accounts(id),
                    category    TEXT,
                    period      TEXT NOT NULL,  -- YYYY-MM
                    amount      INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(account_id, category, period)
                );

                -- Accounting periods (月結)
                CREATE TABLE IF NOT EXISTS periods (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    period      TEXT NOT NULL UNIQUE,  -- YYYY-MM
                    status      TEXT NOT NULL DEFAULT 'open',  -- open | closed
                    closed_at   TEXT,
                    notes       TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );

                -- Invoices / receivables
                CREATE TABLE IF NOT EXISTS invoices (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id      INTEGER NOT NULL REFERENCES accounts(id),
                    invoice_number  TEXT NOT NULL UNIQUE,
                    counterparty    TEXT,
                    amount          INTEGER NOT NULL DEFAULT 0,
                    tax_amount      INTEGER NOT NULL DEFAULT 0,
                    currency        TEXT NOT NULL DEFAULT 'HKD',
                    status          TEXT NOT NULL DEFAULT 'unpaid',  -- unpaid | paid | overdue | cancelled
                    due_date        TEXT,
                    paid_at         TEXT,
                    description     TEXT,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_budget_account ON budgets(account_id);
                CREATE INDEX IF NOT EXISTS idx_budget_period  ON budgets(period);
                CREATE INDEX IF NOT EXISTS idx_invoice_account ON invoices(account_id);
                CREATE INDEX IF NOT EXISTS idx_invoice_status  ON invoices(status);
            """)

            # Migrate existing transactions table: add tax columns if missing
            cursor = conn.execute("PRAGMA table_info(transactions)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            if "tax_amount" not in existing_cols:
                conn.execute("ALTER TABLE transactions ADD COLUMN tax_amount INTEGER NOT NULL DEFAULT 0")
            if "tax_rate" not in existing_cols:
                conn.execute("ALTER TABLE transactions ADD COLUMN tax_rate  REAL    NOT NULL DEFAULT 0.0")
            # Migrate accounts table: add archived column if missing
            cursor = conn.execute("PRAGMA table_info(accounts)")
            acct_cols = {row["name"] for row in cursor.fetchall()}
            if "archived" not in acct_cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")

            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------ #

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    async def _run(self, fn, *args, **kwargs):
        """Run blocking DB call in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    def _audit(self, conn: sqlite3.Connection, entity_type: str,
               entity_id: int, action: str, old_val=None, new_val=None,
               user: str = "system") -> None:
        conn.execute(
            "INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, user) "
            "VALUES (?,?,?,?,?,?)",
            (
                entity_type, entity_id, action,
                json.dumps(old_val, default=str) if old_val else None,
                json.dumps(new_val, default=str) if new_val else None,
                user,
            ),
        )

    # ====================================================== #
    # Account CRUD
    # ====================================================== #

    def _create_account_sync(self, name: str, account_type: str = "general",
                             currency: str = "HKD", description: str = "") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO accounts (name, type, currency, description) VALUES (?,?,?,?)",
                (name, account_type, currency, description),
            )
            aid = cur.lastrowid
            self._audit(conn, "account", aid, AuditAction.CREATE,
                        new_val={"name": name, "type": account_type})
            conn.commit()
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    async def create_account(self, name: str, account_type: str = "general",
                             currency: str = "HKD", description: str = "") -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._create_account_sync, name, account_type, currency, description)

    def _list_accounts_sync(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            where = "" if include_archived else " WHERE archived=0"
            rows = conn.execute(f"SELECT * FROM accounts{where} ORDER BY id").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    async def list_accounts(self) -> List[Dict[str, Any]]:
        return await self._run(self._list_accounts_sync)

    def _get_account_sync(self, account_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    async def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        return await self._run(self._get_account_sync, account_id)

    # ====================================================== #
    # Transaction CRUD (入數)
    # ====================================================== #

    def _add_transaction_sync(
        self,
        account_id: int,
        txn_type: str,
        amount: float,
        description: str = "",
        reference: str = "",
        counterparty: str = "",
        category: str = "",
        transaction_date: str = "",
    ) -> Dict[str, Any]:
        # amount comes as float dollars – store as cents
        amount_cents = int(round(amount * 100))
        if not transaction_date:
            transaction_date = date.today().isoformat()

        conn = self._get_conn()
        try:
            # Verify account exists
            acct = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not acct:
                raise ValueError(f"Account {account_id} not found")

            cur = conn.execute(
                "INSERT INTO transactions "
                "(account_id, type, amount, description, reference, counterparty, category, transaction_date) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (account_id, txn_type, amount_cents, description, reference,
                 counterparty, category, transaction_date),
            )
            txn_id = cur.lastrowid

            # Update account balance
            delta = amount_cents if txn_type == TransactionType.INCOME else -amount_cents
            conn.execute(
                "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id=?",
                (delta, account_id),
            )

            self._audit(conn, "transaction", txn_id, AuditAction.CREATE,
                        new_val={"amount": amount, "type": txn_type, "account_id": account_id})
            conn.commit()

            row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
            result = self._row_to_dict(row)
            # Return amount as dollars for display
            result["amount_display"] = result["amount"] / 100.0
            return result
        finally:
            conn.close()

    async def add_transaction(self, account_id: int, txn_type: str, amount: float, **kwargs) -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._add_transaction_sync, account_id, txn_type, amount, **kwargs)

    def _list_transactions_sync(
        self,
        account_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conditions = []
            params: list = []
            if account_id:
                conditions.append("account_id = ?")
                params.append(account_id)
            if status:
                conditions.append("status = ?")
                params.append(status)
            if start_date:
                conditions.append("transaction_date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("transaction_date <= ?")
                params.append(end_date)

            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            count_row = conn.execute(f"SELECT COUNT(*) as cnt FROM transactions{where}", params).fetchone()
            total = count_row["cnt"]

            rows = conn.execute(
                f"SELECT * FROM transactions{where} ORDER BY transaction_date DESC, id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()

            items = []
            for r in rows:
                d = self._row_to_dict(r)
                d["amount_display"] = d["amount"] / 100.0
                items.append(d)

            return {"total": total, "limit": limit, "offset": offset, "transactions": items}
        finally:
            conn.close()

    async def list_transactions(self, **kwargs) -> Dict[str, Any]:
        return await self._run(self._list_transactions_sync, **kwargs)

    # ====================================================== #
    # Reconciliation (對數)
    # ====================================================== #

    def _reconcile_transaction_sync(self, txn_id: int, user: str = "system") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
            if not row:
                raise ValueError(f"Transaction {txn_id} not found")
            old = self._row_to_dict(row)
            if old["status"] == TransactionStatus.RECONCILED:
                return {"message": "Already reconciled", "transaction": old}

            conn.execute(
                "UPDATE transactions SET status=?, reconciled_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (TransactionStatus.RECONCILED, txn_id),
            )
            self._audit(conn, "transaction", txn_id, AuditAction.RECONCILE,
                        old_val={"status": old["status"]},
                        new_val={"status": TransactionStatus.RECONCILED},
                        user=user)
            conn.commit()

            new_row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
            result = self._row_to_dict(new_row)
            result["amount_display"] = result["amount"] / 100.0
            return {"message": "Transaction reconciled", "transaction": result}
        finally:
            conn.close()

    async def reconcile_transaction(self, txn_id: int, user: str = "system") -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._reconcile_transaction_sync, txn_id, user)

    def _batch_reconcile_sync(self, txn_ids: List[int], user: str = "system") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            reconciled = []
            errors = []
            for tid in txn_ids:
                row = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
                if not row:
                    errors.append({"id": tid, "error": "Not found"})
                    continue
                old = self._row_to_dict(row)
                if old["status"] == TransactionStatus.RECONCILED:
                    reconciled.append(tid)
                    continue
                conn.execute(
                    "UPDATE transactions SET status=?, reconciled_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                    (TransactionStatus.RECONCILED, tid),
                )
                self._audit(conn, "transaction", tid, AuditAction.RECONCILE,
                            old_val={"status": old["status"]},
                            new_val={"status": TransactionStatus.RECONCILED},
                            user=user)
                reconciled.append(tid)
            conn.commit()
            return {"reconciled": reconciled, "errors": errors, "count": len(reconciled)}
        finally:
            conn.close()

    async def batch_reconcile(self, txn_ids: List[int], user: str = "system") -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._batch_reconcile_sync, txn_ids, user)

    # ====================================================== #
    # Void transaction
    # ====================================================== #

    def _void_transaction_sync(self, txn_id: int, user: str = "system") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
            if not row:
                raise ValueError(f"Transaction {txn_id} not found")
            old = self._row_to_dict(row)
            if old["status"] == TransactionStatus.VOIDED:
                return {"message": "Already voided", "transaction": old}

            # Reverse the balance change
            amount = old["amount"]
            txn_type = old["type"]
            delta = -amount if txn_type == TransactionType.INCOME else amount
            conn.execute(
                "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id=?",
                (delta, old["account_id"]),
            )

            conn.execute(
                "UPDATE transactions SET status=?, updated_at=datetime('now') WHERE id=?",
                (TransactionStatus.VOIDED, txn_id),
            )
            self._audit(conn, "transaction", txn_id, AuditAction.VOID,
                        old_val={"status": old["status"]},
                        new_val={"status": TransactionStatus.VOIDED},
                        user=user)
            conn.commit()

            new_row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
            result = self._row_to_dict(new_row)
            result["amount_display"] = result["amount"] / 100.0
            return {"message": "Transaction voided", "transaction": result}
        finally:
            conn.close()

    async def void_transaction(self, txn_id: int, user: str = "system") -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._void_transaction_sync, txn_id, user)

    # ====================================================== #
    # Audit trail
    # ====================================================== #

    def _get_audit_log_sync(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            conditions = []
            params: list = []
            if entity_type:
                conditions.append("entity_type = ?")
                params.append(entity_type)
            if entity_id:
                conditions.append("entity_id = ?")
                params.append(entity_id)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            rows = conn.execute(
                f"SELECT * FROM audit_log{where} ORDER BY id DESC LIMIT ?",
                params + [limit],
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    async def get_audit_log(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._run(self._get_audit_log_sync, **kwargs)

    # ====================================================== #
    # Summary / Reports
    # ====================================================== #

    def _get_account_summary_sync(self, account_id: int) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            acct = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not acct:
                raise ValueError(f"Account {account_id} not found")
            acct_dict = self._row_to_dict(acct)
            acct_dict["balance_display"] = acct_dict["balance"] / 100.0

            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as total_income,
                    SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as total_expense,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN status='reconciled' THEN 1 ELSE 0 END) as reconciled_count
                FROM transactions WHERE account_id=? AND status != 'voided'
            """, (account_id,)).fetchone()

            return {
                "account": acct_dict,
                "total_transactions": stats["total_transactions"] or 0,
                "total_income": (stats["total_income"] or 0) / 100.0,
                "total_expense": (stats["total_expense"] or 0) / 100.0,
                "pending_count": stats["pending_count"] or 0,
                "reconciled_count": stats["reconciled_count"] or 0,
            }
        finally:
            conn.close()

    async def get_account_summary(self, account_id: int) -> Dict[str, Any]:
        return await self._run(self._get_account_summary_sync, account_id)

    def _get_dashboard_sync(self) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            accounts = conn.execute("SELECT * FROM accounts WHERE archived=0 ORDER BY id").fetchall()
            acct_list = []
            for a in accounts:
                d = self._row_to_dict(a)
                d["balance_display"] = d["balance"] / 100.0
                acct_list.append(d)

            totals = conn.execute("""
                SELECT
                    COUNT(*) as total_txn,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status='reconciled' THEN 1 ELSE 0 END) as reconciled,
                    SUM(CASE WHEN status='voided' THEN 1 ELSE 0 END) as voided
                FROM transactions
            """).fetchone()

            return {
                "accounts": acct_list,
                "account_count": len(acct_list),
                "total_transactions": totals["total_txn"] or 0,
                "pending_transactions": totals["pending"] or 0,
                "reconciled_transactions": totals["reconciled"] or 0,
                "voided_transactions": totals["voided"] or 0,
            }
        finally:
            conn.close()

    async def get_dashboard(self) -> Dict[str, Any]:
        return await self._run(self._get_dashboard_sync)

    # ------------------------------------------------------ #
    # Update Transaction
    # ------------------------------------------------------ #

    def _update_transaction_sync(self, transaction_id: int, **fields) -> Dict[str, Any]:
        allowed = {"description", "reference", "counterparty", "category",
                   "transaction_date", "amount", "tax_amount", "tax_rate"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            raise ValueError("No valid fields to update")
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM transactions WHERE id=?", (transaction_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Transaction {transaction_id} not found")
            if row["status"] == "voided":
                raise ValueError("Cannot edit a voided transaction")

            old_val = self._row_to_dict(row)

            # Handle amount update: convert dollars → cents, adjust balance
            if "amount" in updates:
                new_cents = int(round(updates["amount"] * 100))
                old_cents = row["amount"]
                diff = new_cents - old_cents
                txn_type = row["type"]
                if txn_type == "expense":
                    diff = -diff
                conn.execute(
                    "UPDATE accounts SET balance=balance+?, updated_at=datetime('now') WHERE id=?",
                    (diff, row["account_id"]),
                )
                updates["amount"] = new_cents

            # Convert tax_amount from dollars to cents
            if "tax_amount" in updates:
                updates["tax_amount"] = int(round(updates["tax_amount"] * 100))

            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [transaction_id]
            conn.execute(
                f"UPDATE transactions SET {set_clause}, updated_at=datetime('now') WHERE id=?",
                values,
            )
            self._audit(conn, "transaction", transaction_id, AuditAction.UPDATE,
                        old_val=old_val)
            conn.commit()
            updated = self._row_to_dict(
                conn.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,)).fetchone()
            )
            updated["amount_display"] = updated["amount"] / 100.0
            return {"transaction": updated}
        finally:
            conn.close()

    async def update_transaction(self, transaction_id: int, **fields) -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._update_transaction_sync, transaction_id, **fields)

    # ------------------------------------------------------ #
    # Archive / Delete Account
    # ------------------------------------------------------ #

    def _archive_account_sync(self, account_id: int) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not row:
                raise ValueError(f"Account {account_id} not found")
            conn.execute(
                "UPDATE accounts SET archived=1, updated_at=datetime('now') WHERE id=?",
                (account_id,),
            )
            self._audit(conn, "account", account_id, AuditAction.DELETE,
                        old_val=self._row_to_dict(row))
            conn.commit()
            return {"archived": True, "account_id": account_id}
        finally:
            conn.close()

    async def archive_account(self, account_id: int) -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._archive_account_sync, account_id)

    # ------------------------------------------------------ #
    # Categories
    # ------------------------------------------------------ #

    def _create_category_sync(self, name: str, description: str = "") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO categories(name,description) VALUES(?,?)",
                (name, description),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM categories WHERE id=?", (cursor.lastrowid,)).fetchone()
            return {"category": self._row_to_dict(row)}
        finally:
            conn.close()

    async def create_category(self, name: str, description: str = "") -> Dict[str, Any]:
        return await self._run(self._create_category_sync, name, description)

    def _list_categories_sync(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    async def list_categories(self) -> List[Dict[str, Any]]:
        return await self._run(self._list_categories_sync)

    def _delete_category_sync(self, category_id: int) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
            conn.commit()
            return {"deleted": True, "category_id": category_id}
        finally:
            conn.close()

    async def delete_category(self, category_id: int) -> Dict[str, Any]:
        return await self._run(self._delete_category_sync, category_id)

    # ------------------------------------------------------ #
    # Budgets
    # ------------------------------------------------------ #

    def _set_budget_sync(self, account_id: int, period: str, amount: float,
                         category: str = "") -> Dict[str, Any]:
        cents = int(round(amount * 100))
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO budgets(account_id, category, period, amount)
                VALUES(?,?,?,?)
                ON CONFLICT(account_id, category, period)
                DO UPDATE SET amount=excluded.amount, updated_at=datetime('now')
            """, (account_id, category, period, cents))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM budgets WHERE account_id=? AND category=? AND period=?",
                (account_id, category, period),
            ).fetchone()
            d = self._row_to_dict(row)
            d["amount_display"] = d["amount"] / 100.0
            return {"budget": d}
        finally:
            conn.close()

    async def set_budget(self, account_id: int, period: str, amount: float,
                         category: str = "") -> Dict[str, Any]:
        return await self._run(self._set_budget_sync, account_id, period, amount, category)

    def _check_budget_status_sync(self, account_id: int, period: str) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            start_date = f"{period}-01"
            # Last day: cheat by taking first day of next month minus 1 day
            end_date = f"{period}-31"  # SQL date comparison handles overflow naturally for this

            budgets = conn.execute(
                "SELECT * FROM budgets WHERE account_id=? AND period=?",
                (account_id, period),
            ).fetchall()

            results = []
            for b in budgets:
                cat = b["category"] or ""
                cat_filter = "AND category=?" if cat else "AND (category IS NULL OR category='')"
                params = [account_id, "expense", start_date, end_date]
                if cat:
                    params.append(cat)
                actual = conn.execute(f"""
                    SELECT COALESCE(SUM(amount),0) as total
                    FROM transactions
                    WHERE account_id=? AND type=? AND status!='voided'
                      AND transaction_date>=? AND transaction_date<=?
                      {cat_filter}
                """, params).fetchone()["total"]

                budget_cents = b["amount"]
                over = actual > budget_cents
                results.append({
                    "category": cat,
                    "budget": budget_cents / 100.0,
                    "actual": actual / 100.0,
                    "remaining": (budget_cents - actual) / 100.0,
                    "over_budget": over,
                    "utilisation_pct": round((actual / budget_cents * 100) if budget_cents else 0, 1),
                })

            return {"period": period, "account_id": account_id, "budgets": results}
        finally:
            conn.close()

    async def check_budget_status(self, account_id: int, period: str) -> Dict[str, Any]:
        return await self._run(self._check_budget_status_sync, account_id, period)

    # ------------------------------------------------------ #
    # Accounting Periods (月結)
    # ------------------------------------------------------ #

    def _close_period_sync(self, period: str, notes: str = "") -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO periods(period, status, closed_at, notes)
                VALUES(?, 'closed', datetime('now'), ?)
                ON CONFLICT(period)
                DO UPDATE SET status='closed', closed_at=datetime('now'), notes=excluded.notes
            """, (period, notes))
            # Flag all pending transactions in this period as reconciled if caller wants strict close
            conn.commit()
            row = conn.execute("SELECT * FROM periods WHERE period=?", (period,)).fetchone()
            return {"period": self._row_to_dict(row)}
        finally:
            conn.close()

    async def close_period(self, period: str, notes: str = "") -> Dict[str, Any]:
        return await self._run(self._close_period_sync, period, notes)

    def _list_periods_sync(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM periods ORDER BY period DESC").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    async def list_periods(self) -> List[Dict[str, Any]]:
        return await self._run(self._list_periods_sync)

    # ------------------------------------------------------ #
    # CSV Import
    # ------------------------------------------------------ #

    def _import_csv_sync(self, account_id: int, csv_text: str) -> Dict[str, Any]:
        import csv, io
        reader = csv.DictReader(io.StringIO(csv_text))
        imported, errors = 0, []
        conn = self._get_conn()
        try:
            # Verify account exists
            acct = conn.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not acct:
                raise ValueError(f"Account {account_id} not found")
            for i, row in enumerate(reader, start=1):
                try:
                    txn_type = (row.get("type") or "expense").strip().lower()
                    amount_str = (row.get("amount") or "0").replace(",", "").strip()
                    amount_cents = int(round(float(amount_str) * 100))
                    description = (row.get("description") or "").strip()
                    reference = (row.get("reference") or "").strip()
                    counterparty = (row.get("counterparty") or "").strip()
                    category = (row.get("category") or "").strip()
                    txn_date = (row.get("transaction_date") or row.get("date") or "").strip()
                    tax_amount = int(round(float((row.get("tax_amount") or "0").replace(",", "").strip()) * 100))
                    tax_rate = float((row.get("tax_rate") or "0").strip())

                    # Balance adjustment
                    if txn_type == "income":
                        delta = amount_cents
                    elif txn_type == "expense":
                        delta = -amount_cents
                    else:
                        delta = 0

                    cursor = conn.execute("""
                        INSERT INTO transactions
                          (account_id, type, amount, description, reference, counterparty,
                           category, tax_amount, tax_rate, transaction_date)
                        VALUES(?,?,?,?,?,?,?,?,?,?)
                    """, (account_id, txn_type, amount_cents, description, reference,
                          counterparty, category, tax_amount, tax_rate,
                          txn_date or datetime.now().strftime("%Y-%m-%d")))
                    conn.execute(
                        "UPDATE accounts SET balance=balance+?, updated_at=datetime('now') WHERE id=?",
                        (delta, account_id),
                    )
                    self._audit(conn, "transaction", cursor.lastrowid, AuditAction.CREATE,
                                new_val=f"csv_row_{i}")
                    imported += 1
                except Exception as row_err:
                    errors.append({"row": i, "error": str(row_err)})
            conn.commit()
        finally:
            conn.close()
        return {"imported": imported, "errors": errors, "error_count": len(errors)}

    async def import_transactions_csv(self, account_id: int, csv_text: str) -> Dict[str, Any]:
        async with self._lock:
            return await self._run(self._import_csv_sync, account_id, csv_text)

    # ------------------------------------------------------ #
    # Invoices
    # ------------------------------------------------------ #

    def _create_invoice_sync(self, account_id: int, invoice_number: str,
                              amount: float, counterparty: str = "",
                              due_date: str = "", description: str = "",
                              tax_amount: float = 0.0, currency: str = "HKD") -> Dict[str, Any]:
        cents = int(round(amount * 100))
        tax_cents = int(round(tax_amount * 100))
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO invoices
                  (account_id, invoice_number, counterparty, amount, tax_amount,
                   currency, due_date, description)
                VALUES(?,?,?,?,?,?,?,?)
            """, (account_id, invoice_number, counterparty, cents, tax_cents,
                  currency, due_date, description))
            conn.commit()
            row = conn.execute("SELECT * FROM invoices WHERE id=?", (cursor.lastrowid,)).fetchone()
            d = self._row_to_dict(row)
            d["amount_display"] = d["amount"] / 100.0
            d["tax_amount_display"] = d["tax_amount"] / 100.0
            return {"invoice": d}
        finally:
            conn.close()

    async def create_invoice(self, account_id: int, invoice_number: str,
                             amount: float, counterparty: str = "",
                             due_date: str = "", description: str = "",
                             tax_amount: float = 0.0, currency: str = "HKD") -> Dict[str, Any]:
        return await self._run(self._create_invoice_sync, account_id, invoice_number,
                               amount, counterparty, due_date, description, tax_amount, currency)

    def _list_invoices_sync(self, account_id: Optional[int] = None,
                            status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            clauses, params = [], []
            if account_id:
                clauses.append("account_id=?"); params.append(account_id)
            if status:
                clauses.append("status=?"); params.append(status)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM invoices {where} ORDER BY created_at DESC", params
            ).fetchall()
            result = []
            for r in rows:
                d = self._row_to_dict(r)
                d["amount_display"] = d["amount"] / 100.0
                d["tax_amount_display"] = d["tax_amount"] / 100.0
                result.append(d)
            return result
        finally:
            conn.close()

    async def list_invoices(self, account_id: Optional[int] = None,
                            status: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._run(self._list_invoices_sync, account_id, status)

    def _mark_invoice_paid_sync(self, invoice_id: int) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            if not row:
                raise ValueError(f"Invoice {invoice_id} not found")
            conn.execute(
                "UPDATE invoices SET status='paid', paid_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (invoice_id,),
            )
            conn.commit()
            updated = self._row_to_dict(
                conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            )
            updated["amount_display"] = updated["amount"] / 100.0
            return {"invoice": updated}
        finally:
            conn.close()

    async def mark_invoice_paid(self, invoice_id: int) -> Dict[str, Any]:
        return await self._run(self._mark_invoice_paid_sync, invoice_id)
