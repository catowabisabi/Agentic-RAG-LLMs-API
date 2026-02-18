"""Send chat and check traces"""
import requests, json, time

BASE = "http://localhost:1130"

# Send chat
r = requests.post(f"{BASE}/chat/send", json={
    "message": "What is a golden cross in trading?",
    "session_id": "debug_test_2",
    "user_id": "test_user"
})
print(f"Chat response: {r.status_code}")
time.sleep(3)

# Check traces
r = requests.get(f"{BASE}/agents/debug/traces/recent", params={"limit": 50})
data = r.json()
traces = data.get("traces", [])
print(f"\nTotal traces: {len(traces)}")
for t in traces:
    tt = t.get("trace_type", "?")
    an = t.get("agent_name", "?")
    src = t.get("source", "?")
    tgt = t.get("target", "?")
    print(f"  [{tt:20s}] {an:20s} | {src} -> {tgt}")
