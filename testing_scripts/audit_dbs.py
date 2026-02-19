import sqlite3
import os

dbs = {
    "SKILL/asset/sw_api_doc.db": r".claude\skills\sw-api-skill\asset\sw_api_doc.db",
    "SKILL/asset/sw_api_doc_vector.db": r".claude\skills\sw-api-skill\asset\sw_api_doc_vector.db",
    "SKILL/assets/founding.db": r".claude\skills\sw-api-skill\assets\founding.db",
    "SKILL/sw_api_doc.db (root)": r".claude\skills\sw-api-skill\sw_api_doc.db",
    "data/solidworks_db/sw_api_doc.db": r"data\solidworks_db\sw_api_doc.db",
    "rag-database/cerebro.db": r"rag-database\cerebro.db",
    "rag-database/sessions.db": r"rag-database\sessions.db",
}

BASE = r"D:\codebase\Agentic-RAG-LLMs-API"

for label, path in dbs.items():
    full = os.path.join(BASE, path)
    size_mb = os.path.getsize(full) / 1024 / 1024 if os.path.exists(full) else -1
    print(f"\n===== {label} ({size_mb:.2f} MB) =====")
    try:
        conn = sqlite3.connect(full)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in c.fetchall()]
        # Skip FTS internal tables (config, data, docsize, idx) - they are huge
        display_tables = [t for t in tables if not any(t.endswith(s) for s in ['_config', '_data', '_docsize', '_idx', '_content'])]
        print(f"Tables ({len(tables)} total, showing {len(display_tables)}): {display_tables}")
        for t in display_tables:
            try:
                c.execute(f"SELECT COUNT(*) FROM [{t}]")
                cnt = c.fetchone()[0]
            except Exception:
                cnt = "?"
            c.execute(f"PRAGMA table_info([{t}])")
            cols = [r[1] for r in c.fetchall()]
            col_str = str(cols[:8]) + "..." if len(cols) > 8 else str(cols)
            print(f"  {t}: {cnt} rows | cols: {col_str}")
        conn.close()
    except Exception as e:
        print(f"  ERROR: {e}")
