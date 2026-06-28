"""
websocket/redis_listener.py

Background task that subscribes to the Redis pub/sub channel and
forwards every received message to all WebSocket clients connected
to THIS backend instance.

Lifecycle
---------
Started as an asyncio Task by the app lifespan in main.py.
Cancelled cleanly on shutdown — the task catches CancelledError and
unsubscribes before exiting.

Why socket_timeout=None
-----------------------
A pub/sub subscriber connection must block indefinitely waiting for
messages.  The default redis-py socket_timeout causes a ReadTimeout
after a short idle period, which shows up as:
    "Redis listener error: Timeout reading from redis:6379"
Setting socket_timeout=None disables the timeout for this connection
so the listener can wait as long as needed between messages.
The publish connection in manager.py keeps a normal timeout since it
sends short-lived commands.
"""

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis

from app.core.config import REDIS_URL
from app.websocket.manager import REDIS_CHANNEL, manager

logger = logging.getLogger(__name__)


async def redis_listener() -> None:
    """
    Subscribe to REDIS_CHANNEL and forward messages to WS clients.

    Runs forever until cancelled.  Reconnects automatically if the
    Redis connection drops (with a short backoff to avoid tight loops).
    """
    while True:
        pubsub: aioredis.client.PubSub | None = None
        redis_client: aioredis.Redis | None = None

        try:
            # socket_timeout=None is required for pub/sub subscriber connections.
            # Without it the connection times out while waiting for messages
            # and the listener logs "Timeout reading from redis" every 2 seconds.
            redis_client = aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=None,
                socket_connect_timeout=5,
            )
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
            logger.info("Redis listener subscribed to channel: %s", REDIS_CHANNEL)

            async for raw_message in pubsub.listen():
                # pubsub.listen() yields a subscription-confirmation dict
                # first; skip anything that isn't a real message.
                if raw_message["type"] != "message":
                    continue

                try:
                    payload = json.loads(raw_message["data"])
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("Malformed Redis message ignored: %s", exc)
                    continue

                await manager.broadcast(payload)

        except asyncio.CancelledError:
            # Clean shutdown — unsubscribe before exiting.
            logger.info("Redis listener shutting down.")
            if pubsub:
                try:
                    await pubsub.unsubscribe(REDIS_CHANNEL)
                    await pubsub.aclose()
                except Exception:
                    pass
            if redis_client:
                try:
                    await redis_client.aclose()
                except Exception:
                    pass
            return  # exit the task cleanly

        except Exception as exc:
            logger.error(
                "Redis listener error: %s — reconnecting in 2 s.", exc
            )
            if pubsub:
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
            if redis_client:
                try:
                    await redis_client.aclose()
                except Exception:
                    pass
            await asyncio.sleep(2)