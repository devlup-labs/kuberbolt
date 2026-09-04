import asyncio
from typing import Any

class AgentRegistry:
    """Thread-safe registry of active KuberboltAgent instances in session."""

    def __init__(self):
        self._agents: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent: Any) -> str:
        async with self._lock:
            pubkey = agent.pubkey_hex
            self._agents[pubkey] = agent
            return pubkey

    async def get(self, pubkey: str) -> Any | None:
        async with self._lock:
            return self._agents.get(pubkey)

    async def remove(self, pubkey: str) -> None:
        async with self._lock:
            agent = self._agents.pop(pubkey, None)
            if agent and hasattr(agent, "disconnect"):
                await agent.disconnect()


_registry = AgentRegistry()


async def get_agent_registry() -> AgentRegistry:
    return _registry
