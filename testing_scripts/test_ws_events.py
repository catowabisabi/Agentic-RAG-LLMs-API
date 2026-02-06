#!/usr/bin/env python3
"""
Test WebSocket events flow
"""
import asyncio
import aiohttp
import json
import sys

API_BASE = "http://localhost:1130"
WS_URL = "ws://localhost:1130/ws"

async def test_ws_events():
    """Test that events are properly broadcast over WebSocket"""
    
    # Use a unique session_id
    session_id = f"test-ws-session-{int(asyncio.get_event_loop().time() * 1000)}"
    print(f"[Test] Using session_id: {session_id}")
    
    events_received = []
    
    async with aiohttp.ClientSession() as session:
        # 1. Connect to WebSocket first
        print("[Test] Step 1: Connecting to WebSocket...")
        try:
            ws = await session.ws_connect(WS_URL, timeout=10)
            print("[Test] WebSocket connected!")
        except Exception as e:
            print(f"[Test] Failed to connect WebSocket: {e}")
            return
        
        # 2. Subscribe to session
        print(f"[Test] Step 2: Subscribing to session {session_id}...")
        await ws.send_json({
            "type": "subscribe_session",
            "session_id": session_id
        })
        
        # Wait for subscription confirmation
        await asyncio.sleep(0.5)
        
        # 3. Create a task to receive WebSocket messages
        async def receive_messages():
            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=60)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        events_received.append(data)
                        event_type = data.get('type', 'unknown')
                        print(f"[WS] Received event: {event_type} - {data.get('content', {}).get('message', '')[:50] if isinstance(data.get('content'), dict) else str(data)[:50]}")
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        print("[WS] Connection closed")
                        break
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"[WS] Error: {ws.exception()}")
                        break
                except asyncio.TimeoutError:
                    print("[WS] Receive timeout")
                    break
        
        ws_task = asyncio.create_task(receive_messages())
        
        # 4. Send HTTP request
        print(f"[Test] Step 3: Sending chat message...")
        await asyncio.sleep(0.5)  # Small delay to ensure WS is ready
        
        async with session.post(
            f"{API_BASE}/chat/send",
            json={
                "message": "什麼是 OpenDoc6 API?",
                "conversation_id": session_id,
                "async_mode": True
            }
        ) as resp:
            result = await resp.json()
            print(f"[HTTP] Response: {json.dumps(result, indent=2)}")
        
        # 5. Wait for events
        print("[Test] Step 4: Waiting for WebSocket events (max 30s)...")
        await asyncio.sleep(30)  # Wait for processing
        
        # Cancel ws_task
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
        
        await ws.close()
        
        # 6. Report
        print(f"\n[Test] ===== SUMMARY =====")
        print(f"[Test] Total events received: {len(events_received)}")
        print(f"[Test] Event types: {[e.get('type') for e in events_received]}")
        
        # Check for unified events
        unified_events = [e for e in events_received if e.get('type') in ['init', 'thinking', 'status', 'progress', 'result', 'error']]
        print(f"[Test] Unified events: {len(unified_events)}")
        for e in unified_events:
            print(f"  - {e.get('type')}/{e.get('stage')}: {e.get('content', {}).get('message', '')[:60]}")

if __name__ == "__main__":
    asyncio.run(test_ws_events())
