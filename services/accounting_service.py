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
            """)
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

    def _list_accounts_sync(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
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
            accounts = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
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
