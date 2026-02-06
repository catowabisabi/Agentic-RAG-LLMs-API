import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket():
    uri = "ws://localhost:1130/ws"
    logger.info(f"Connecting to {uri}")
    try:
        async with websockets.connect(uri, ping_interval=None) as websocket: # Disable auto-ping
            logger.info("Connected! Waiting for 20 seconds (idle)...")
            
            # Wait for initial message
            msg = await websocket.recv()
            logger.info(f"Initial message: {msg}")
            
            # Just wait to see if it closes
            try:
                # We expect a timeout because we're not sending anything and server isn't either
                response = await asyncio.wait_for(websocket.recv(), timeout=20.0)
                logger.info(f"Received unexpected: {response}")
            except asyncio.TimeoutError:
                logger.info("No data received for 20s (expected). checking if open...")
                await websocket.ping()
                await asyncio.sleep(1)
                logger.info("Ping sent successfully. Connection is still open.")
            
            logger.info("Test finished successfully - Idle connection persisted.")
            
    except Exception as e:
        logger.error(f"Connection failed or dropped: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
