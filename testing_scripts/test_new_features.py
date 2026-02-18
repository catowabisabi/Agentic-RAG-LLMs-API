#!/usr/bin/env python3
"""
Comprehensive API tests for new features:
1. KB Skills metadata
2. Smart ingestion
3. Backup/restore/consolidation
4. Agent debug traces
5. Memory CRUD + dashboard
"""

import requests
import json
import time
import sys

BASE = "http://localhost:1130"

def pp(data, max_len=500):
    """Pretty print JSON, truncated"""
    s = json.dumps(data, indent=2, ensure_ascii=False)
    if len(s) > max_len:
        s = s[:max_len] + "\n... (truncated)"
    print(s)

def test(name, method, url, expected_status=200, **kwargs):
    """Run a test and print result"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  {method.upper()} {url}")
    
    try:
        r = getattr(requests, method)(f"{BASE}{url}", **kwargs)
        status_ok = r.status_code == expected_status
        icon = "PASS" if status_ok else "FAIL"
        print(f"  Status: {r.status_code} [{icon}]")
        
        try:
            data = r.json()
            pp(data)
        except:
            print(f"  Body: {r.text[:200]}")
        
        if not status_ok:
            print(f"  Expected: {expected_status}")
        
        return r
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    print("=" * 60)
    print("NEW FEATURES API TEST SUITE")
    print("=" * 60)
    
    # 0. Health check
    test("Health Check", "get", "/health")
    
    # ========== 1. KB SKILLS ==========
    print("\n\n" + "#" * 60)
    print("# 1. KNOWLEDGE BASE SKILLS")
    print("#" * 60)
    
    test("Get All Skills (auto-generated defaults)", "get", "/rag/databases/skills")
    
    test("Get Single DB Skills", "get", "/rag/databases/trading_strategies/skills")
    
    # Generate skills with LLM for one DB
    test("Generate Skills with LLM (single DB)", "post", 
         "/rag/databases/trading_strategies/skills/generate")
    
    # Update skills manually
    test("Update Skills Manually", "put",
         "/rag/databases/trading_strategies/skills",
         json={
             "display_name": "Trading Strategies KB",
             "description": "Knowledge base for trading strategies including PineScript, Golden Cross, technical analysis",
             "capabilities": ["PineScript code", "trading indicators", "backtesting"],
             "keywords": ["pine", "strategy", "indicator", "TradingView"],
             "topics": ["technical analysis", "automated trading"]
         })
    
    # Verify update
    test("Verify Updated Skills", "get", "/rag/databases/trading_strategies/skills")
    
    # ========== 2. SMART INGESTION ==========
    print("\n\n" + "#" * 60)
    print("# 2. SMART INGESTION")
    print("#" * 60)
    
    # Suggest target without inserting
    test("Suggest Target DB for Trading Content", "post",
         "/rag/databases/suggest-target",
         data={
             "content": "PineScript strategy for detecting golden cross with EMA 50 and 200",
             "title": "Golden Cross Strategy"
         })
    
    # Smart insert (will auto-route)
    test("Smart Insert - Trading Content", "post",
         "/rag/databases/smart-insert",
         json={
             "content": "This is a test document about moving average crossover strategies in PineScript. The golden cross occurs when MA50 crosses above MA200.",
             "title": "Test: MA Crossover",
             "source": "api_test",
             "category": "trading",
             "tags": ["test", "pinescript"],
             "summarize": False,
             "auto_create": False
         })
    
    # ========== 3. BACKUP & CONSOLIDATION ==========
    print("\n\n" + "#" * 60)
    print("# 3. BACKUP & CONSOLIDATION")
    print("#" * 60)
    
    # List existing backups
    test("List Backups", "get", "/rag/databases/backups")
    
    # Create new backup
    test("Create Backup", "post", "/rag/databases/backup")
    
    # List backups again
    r = test("List Backups After Create", "get", "/rag/databases/backups")
    if r and r.status_code == 200:
        backups = r.json().get("backups", [])
        if backups:
            first_backup = backups[0]["filename"]
            test(f"Download Backup Check", "get", 
                 f"/rag/databases/backup/download/{first_backup}")
    
    # ========== 4. AGENT DEBUG TRACES ==========
    print("\n\n" + "#" * 60)
    print("# 4. AGENT DEBUG TRACES")
    print("#" * 60)
    
    # First, send a chat message to generate traces
    test("Send Chat (to generate traces)", "post", "/chat/send",
         json={
             "message": "What is a golden cross in trading?",
             "session_id": "test_debug_session",
             "user_id": "test_user"
         })
    
    time.sleep(3)  # Wait for processing
    
    test("Get Recent Debug Traces", "get", "/agents/debug/traces/recent?limit=20")
    
    test("Get Traces by Agent", "get", "/agents/debug/traces?agent_name=manager_agent&limit=10")
    
    test("Get Session Flow", "get", "/agents/debug/session/test_debug_session/flow")
    
    # ========== 5. MEMORY CRUD + DASHBOARD ==========
    print("\n\n" + "#" * 60)
    print("# 5. MEMORY CRUD + DASHBOARD")
    print("#" * 60)
    
    # Create observation
    test("Create Observation", "post", "/memory/observations",
         json={
             "user_id": "test_user",
             "title": "Test Preference",
             "subtitle": "API Testing",
             "facts": ["User prefers Chinese responses", "User works with PineScript"],
             "concepts": ["language_preference", "trading"],
             "memory_type": "preference",
             "importance": 8
         })
    
    # Get observations
    r = test("Get User Observations", "get", "/memory/observations/test_user")
    
    obs_id = None
    if r and r.status_code == 200:
        obs = r.json().get("observations", [])
        if obs:
            obs_id = obs[0].get("id")
    
    # Update observation
    if obs_id:
        test("Update Observation", "put", f"/memory/observations/{obs_id}",
             json={
                 "facts": ["User prefers Chinese responses", "User works with PineScript", "User likes detailed debug info"],
                 "importance": 9
             })
    
    # Dashboard
    test("Memory Dashboard", "get", "/memory/dashboard/test_user")
    
    # Memory context (used for injection)
    test("Memory Context for Prompt", "get", "/memory/context/test_user?query=trading")
    
    # ========== 6. LIST ALL DATABASES (verify skills included) ==========
    print("\n\n" + "#" * 60)
    print("# 6. VERIFY DATABASES LIST INCLUDES SKILLS")
    print("#" * 60)
    
    test("List All Databases (with skills)", "get", "/rag/databases")
    
    # ========== SUMMARY ==========
    print("\n\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
