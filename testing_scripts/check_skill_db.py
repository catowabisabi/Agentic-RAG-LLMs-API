import sqlite3

conn = sqlite3.connect(r'.claude\skills\sw-api-skill\asset\sw_api_doc.db')
c = conn.cursor()

# Find real API members with syntax
print('=== Real API Members with Syntax ===')
c.execute('''
SELECT m.interface_name, m.name, m.member_type, m.syntax_vb, m.syntax_csharp, m.description, m.return_type
FROM api_members m
WHERE m.syntax_vb IS NOT NULL AND m.syntax_vb != ''
LIMIT 5
''')
for r in c.fetchall():
    print(f'{r[0]}.{r[1]} ({r[2]})')
    vb = r[3][:120] if r[3] else "N/A"
    cs = r[4][:120] if r[4] else "N/A"
    print(f'  VB: {vb}')
    print(f'  C#: {cs}')
    print(f'  Returns: {r[6]}')
    print()

# Check FTS capability
print('=== FTS Search Test: "circle" ===')
c.execute('''
SELECT d.title, d.doc_type, d.interface_name
FROM documents d
JOIN documents_fts fts ON d.rowid = fts.rowid
WHERE documents_fts MATCH 'circle'
LIMIT 5
''')
for r in c.fetchall():
    print(f'  {r[0]} | {r[1]} | {r[2]}')

print()
print('=== FTS Search Test: "OpenDoc" ===')
c.execute('''
SELECT d.title, d.doc_type, d.interface_name
FROM documents d
JOIN documents_fts fts ON d.rowid = fts.rowid
WHERE documents_fts MATCH 'OpenDoc'
LIMIT 5
''')
for r in c.fetchall():
    print(f'  {r[0]} | {r[1]} | {r[2]}')

conn.close()
