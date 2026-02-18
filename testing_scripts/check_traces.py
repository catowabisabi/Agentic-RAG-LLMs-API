"""Quick check of debug trace types"""
import requests

r = requests.get('http://localhost:1130/agents/debug/traces', params={'limit': 50})
data = r.json()
traces = data.get('traces', [])
print(f'Total traces: {len(traces)}')
for t in traces:
    tt = t.get("trace_type", "?")
    an = t.get("agent_name", "?")
    tgt = t.get("target", "?")
    print(f'  [{tt:20s}] {an:20s} -> {tgt}')
