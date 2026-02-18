"""Quick test for remaining endpoints that failed in batch test"""
import requests, json, time

BASE = "http://localhost:1130"

def pp(data, max_len=800):
    s = json.dumps(data, indent=2, ensure_ascii=False)
    if len(s) > max_len:
        s = s[:max_len] + "\n... (truncated)"
    print(s)

print("\n=== 1. MEMORY DASHBOARD ===")
r = requests.get(f"{BASE}/memory/dashboard/test_user")
print(f"Status: {r.status_code}")
pp(r.json())

print("\n=== 2. CREATE OBSERVATION ===")
r = requests.post(f"{BASE}/memory/observations", json={
    "user_id": "test_user",
    "title": "Test Preference",
    "subtitle": "API Testing",
    "facts": ["User prefers Chinese responses", "User works with PineScript"],
    "concepts": ["language_preference", "trading"],
    "memory_type": "preference",
    "importance": "high"
})
print(f"Status: {r.status_code}")
pp(r.json())

print("\n=== 3. GET OBSERVATIONS ===")
r = requests.get(f"{BASE}/memory/observations/test_user")
print(f"Status: {r.status_code}")
data = r.json()
pp(data)

obs_id = None
observations = data.get("observations", [])
if observations:
    obs_id = observations[0].get("id")
    print(f"  First obs ID: {obs_id}")

if obs_id:
    print("\n=== 4. UPDATE OBSERVATION ===")
    r = requests.put(f"{BASE}/memory/observations/{obs_id}", json={
        "facts": ["User prefers Chinese", "PineScript expert", "Likes debug info"],
        "importance": "critical"
    })
    print(f"Status: {r.status_code}")
    pp(r.json())

print("\n=== 5. MEMORY CONTEXT (for injection) ===")
r = requests.get(f"{BASE}/memory/context/test_user", params={"query": "trading"})
print(f"Status: {r.status_code}")
pp(r.json())

print("\n=== 6. DEBUG TRACES - RECENT ===")
r = requests.get(f"{BASE}/agents/debug/traces/recent", params={"limit": 20})
print(f"Status: {r.status_code}")
data = r.json()
traces = data.get("traces", [])
print(f"  Total traces: {len(traces)}")
for t in traces[:10]:
    print(f"  [{t.get('trace_type')}] {t.get('agent_name')}: {str(t.get('data',{}))[:80]}")

print("\n=== 7. DEBUG SESSION FLOW ===")
r = requests.get(f"{BASE}/agents/debug/session/test_debug_session/flow")
print(f"Status: {r.status_code}")
pp(r.json())

print("\n=== 8. KB SKILLS (use existing db) ===")
# Get list of actual databases first
r = requests.get(f"{BASE}/rag/databases")
dbs = [d.get("name") for d in r.json().get("databases", [])]
print(f"Available DBs: {dbs[:5]}")
if dbs:
    db = dbs[0]
    r = requests.get(f"{BASE}/rag/databases/{db}/skills")
    print(f"Skills for '{db}': Status {r.status_code}")
    pp(r.json())

print("\n=== 9. SMART INSERT (real DB) ===")
r = requests.post(f"{BASE}/rag/databases/smart-insert", json={
    "content": "This is a test about moving average crossover in PineScript for detecting golden cross patterns.",
    "title": "Test MA Crossover",
    "source": "api_test",
    "tags": ["test"],
    "summarize": False,
    "auto_create": False
})
print(f"Status: {r.status_code}")
pp(r.json())

print("\n=== 10. LIST ALL DATABASES WITH SKILLS ===")
r = requests.get(f"{BASE}/rag/databases")
data = r.json()
for db in data.get("databases", [])[:3]:
    skills = db.get("skills", {})
    print(f"  {db['name']}: {skills.get('display_name', 'N/A')} - {skills.get('description', 'N/A')[:50]}")

print("\n\n=== ALL TESTS COMPLETE ===")
