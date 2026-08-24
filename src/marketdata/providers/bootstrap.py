from marketdata.providers.bcb import BcbProvider
from marketdata.providers.cvm import CvmProvider
from marketdata.providers.registry import registry
from marketdata.providers.tesouro import TesouroProvider


def register_default_providers() -> None:
    known = {name.lower() for name in registry.names()}
    for provider in (CvmProvider(), TesouroProvider(), BcbProvider()):
        if provider.name not in known:
            registry.register(provider)
            known.add(provider.name)
