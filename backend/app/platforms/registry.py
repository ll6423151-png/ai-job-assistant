from app.platforms.base import PlatformAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        if adapter.key in self._adapters:
            raise ValueError(f"Adapter already registered: {adapter.key}")
        self._adapters[adapter.key] = adapter

    def get(self, key: str) -> PlatformAdapter | None:
        return self._adapters.get(key)

    def all(self) -> list[PlatformAdapter]:
        return list(self._adapters.values())
