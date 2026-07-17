from app.platforms.manual_import import ManualImportAdapter
from app.platforms.registry import AdapterRegistry
from app.platforms.recruitment import ZhaopinAdapter


adapter_registry = AdapterRegistry()
adapter_registry.register(ManualImportAdapter())
adapter_registry.register(ZhaopinAdapter())

__all__ = [
    "AdapterRegistry",
    "ManualImportAdapter",
    "ZhaopinAdapter",
    "adapter_registry",
]
