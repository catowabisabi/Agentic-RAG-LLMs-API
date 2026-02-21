"""
Accounting DB – Lightweight FastAPI server
Serves the accounting.db as REST endpoints for the HTML frontend.
"""

from __future__ import annotations
import sqlite3, json, os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# ── Paths ────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
DB_PATH = HERE.parent.parent / "data" / "accounting" / "accounting.db"

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Accounting DB Viewer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(table: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def serve_index():
    return FileResponse(HERE / "index.html")


@app.get("/accounting.db")
def serve_db():
    """Serve the raw SQLite DB file so the browser can auto-load it."""
    if not DB_PATH.exists():
        raise HTTPException(404, "DB file not found")
    from fastapi.responses import FileResponse as FR
    return FR(DB_PATH, media_type="application/octet-stream",
              filename="accounting.db")


@app.get("/api/tables")
def list_tables():
    """Return all user table names + row count + columns."""
    with get_conn() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        result = []
        for (name,) in tables:
            # columns
            cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
            count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
            result.append({
                "name": name,
                "count": count,
                "columns": [
                    {"name": c["name"], "type": c["type"], "pk": bool(c["pk"])}
                    for c in cols
                ],
            })
        return result


@app.get("/api/{table}")
def get_rows(
    table: str,
    limit: int = 200,
    offset: int = 0,
    search: str = "",
    sort_col: str = "",
    sort_dir: str = "asc",
):
    """Return paginated rows from a table."""
    if not table_exists(table):
        raise HTTPException(404, f"Table '{table}' not found")

    with get_conn() as conn:
        cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]

        where_clause = ""
        params: list[Any] = []
        if search:
            conditions = [f"CAST([{c}] AS TEXT) LIKE ?" for c in cols]
            where_clause = "WHERE " + " OR ".join(conditions)
            params = [f"%{search}%"] * len(cols)

        order_clause = ""
        if sort_col and sort_col in cols:
            direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
            order_clause = f"ORDER BY [{sort_col}] {direction}"

        total = conn.execute(
            f"SELECT COUNT(*) FROM [{table}] {where_clause}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM [{table}] {where_clause} {order_clause} LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return {
            "table": table,
            "columns": cols,
            "total": total,
            "offset": offset,
            "limit": limit,
            "rows": [dict(r) for r in rows],
        }


@app.get("/api/{table}/{row_id}")
def get_row(table: str, row_id: int):
    """Return a single row by primary key (assumes first INTEGER PK = id)."""
    if not table_exists(table):
        raise HTTPException(404, f"Table '{table}' not found")
    with get_conn() as conn:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        pk_col = next((c["name"] for c in cols if c["pk"]), "id")
        row = conn.execute(
            f"SELECT * FROM [{table}] WHERE [{pk_col}] = ?", (row_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Row not found")
        return dict(row)


@app.post("/api/{table}")
async def insert_row(table: str, request: Request):
    """Insert a new row. Body = JSON object."""
    if not table_exists(table):
        raise HTTPException(404, f"Table '{table}' not found")
    data: dict = await request.json()
    if not data:
        raise HTTPException(400, "Empty body")
    cols = ", ".join(f"[{k}]" for k in data)
    placeholders = ", ".join("?" for _ in data)
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO [{table}] ({cols}) VALUES ({placeholders})",
            list(data.values()),
        )
        conn.commit()
        return {"inserted_id": cur.lastrowid}


@app.patch("/api/{table}/{row_id}")
async def update_row(table: str, row_id: int, request: Request):
    """Update columns of an existing row."""
    if not table_exists(table):
        raise HTTPException(404, f"Table '{table}' not found")
    data: dict = await request.json()
    if not data:
        raise HTTPException(400, "Empty body")
    with get_conn() as conn:
        cols_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        pk_col = next((c["name"] for c in cols_info if c["pk"]), "id")
        set_clause = ", ".join(f"[{k}] = ?" for k in data)
        conn.execute(
            f"UPDATE [{table}] SET {set_clause} WHERE [{pk_col}] = ?",
            list(data.values()) + [row_id],
        )
        conn.commit()
        return {"updated": True}


@app.delete("/api/{table}/{row_id}")
def delete_row(table: str, row_id: int):
    """Delete a row by primary key."""
    if not table_exists(table):
        raise HTTPException(404, f"Table '{table}' not found")
    with get_conn() as conn:
        cols_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        pk_col = next((c["name"] for c in cols_info if c["pk"]), "id")
        conn.execute(
            f"DELETE FROM [{table}] WHERE [{pk_col}] = ?", (row_id,)
        )
        conn.commit()
        return {"deleted": True}


@app.get("/api/{table}/export/json")
def export_json(table: str):
    """Export full table as JSON."""
    if not table_exists(table):
        raise HTTPException(404, f"Table '{table}' not found")
    with get_conn() as conn:
        rows = conn.execute(f"SELECT * FROM [{table}]").fetchall()
        return [dict(r) for r in rows]


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"DB path: {DB_PATH}")
    print("Starting server at http://localhost:8765")
    uvicorn.run(app, host="0.0.0.0", port=8765, reload=False)
