"""
websocket/manager.py

Connection manager for WebSocket clients.

Architecture
------------
Publishing uses Redis pub/sub so that multiple backend instances can all
broadcast to their own connected clients:

    API handler  →  manager.publish(msg)  →  Redis channel "csa:events"
                                                      ↓
                                    redis_listener (background task, per instance)
                                                      ↓
                                    manager.broadcast(msg)  →  WS clients

manager.broadcast() is still available for direct in-process use (e.g.
tests, single-instance dev without Redis).  All production paths go
through manager.publish() so every instance participates.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.core.config import REDIS_URL, ENV

logger = logging.getLogger(__name__)

# Redis channel name — all backend instances publish and subscribe here.
REDIS_CHANNEL = "csa:events"


class ConnectionManager:
    """
    Manages WebSocket connections for this process instance and owns
    the async Redis client used for pub/sub publishing.
    """

    def __init__(self) -> None:
        self.active: list[WebSocket] = []
        self._redis: Optional[aioredis.Redis] = None

    # ------------------------------------------------------------------
    # Redis lifecycle — called from app lifespan in main.py
    # ------------------------------------------------------------------

    async def connect_redis(self) -> bool:
        """Open the async Redis connection.  Called once at app startup.

        Returns True when Redis is reachable. In production an unreachable or
        misconfigured Redis fails fast (raises). In development it degrades to
        single-instance mode — ``publish()`` falls back to in-process broadcast —
        so the stack runs without a Redis server (see the module docstring).
        """
        client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            # Verify the connection is alive immediately so a misconfigured
            # REDIS_URL surfaces at startup rather than at first broadcast.
            await client.ping()
        except Exception as exc:
            if ENV == "production":
                raise
            logger.warning(
                "Redis unavailable (%s) — running single-instance dev mode; "
                "WebSocket events are broadcast in-process only.", exc,
            )
            try:
                await client.aclose()
            except Exception:
                pass
            self._redis = None
            return False

        self._redis = client
        logger.info("Redis connected: %s", REDIS_URL)
        return True

    async def disconnect_redis(self) -> None:
        """Close the async Redis connection.  Called once at app shutdown."""
        if self._redis:
            await self._redis.aclose()
            logger.info("Redis connection closed.")

    # ------------------------------------------------------------------
    # WebSocket connection management
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)
        logger.debug("WS client connected. Total: %d", len(self.active))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)
        logger.debug("WS client disconnected. Total: %d", len(self.active))

    # ------------------------------------------------------------------
    # Publishing (goes through Redis — use this in API handlers)
    # ------------------------------------------------------------------

    async def publish(self, message: dict) -> None:
        """
        Publish a message to the Redis channel.

        All backend instances (including this one) will receive it via
        their redis_listener background task and forward to WS clients.

        Falls back to direct broadcast if Redis is unavailable (e.g.
        during local development without Docker).
        """
        if self._redis is None:
            logger.warning(
                "Redis not connected — falling back to direct broadcast."
            )
            await self.broadcast(message)
            return

        try:
            payload = json.dumps(message)
            await self._redis.publish(REDIS_CHANNEL, payload)
        except Exception as exc:
            logger.error("Redis publish failed (%s) — falling back.", exc)
            await self.broadcast(message)

    # ------------------------------------------------------------------
    # Broadcasting (sends directly to this instance's WS clients)
    # ------------------------------------------------------------------

    async def broadcast(self, message: dict) -> None:
        """
        Send a message to all WebSocket clients connected to THIS instance.

        Called by the redis_listener background task after receiving a
        published event.  Can also be called directly in tests or single-
        instance dev mode.
        """
        dead: list[WebSocket] = []

        for connection in self.active:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)

        for connection in dead:
            self.disconnect(connection)


# Single instance shared across the app.
manager = ConnectionManager()