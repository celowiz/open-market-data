from marketdata.providers.b3 import B3Provider
from marketdata.providers.bcb import BcbProvider
from marketdata.providers.cftc import CftcProvider
from marketdata.providers.cvm import CvmProvider
from marketdata.providers.edgar import EdgarProvider
from marketdata.providers.fred import FredProvider
from marketdata.providers.ibge import IbgeProvider
from marketdata.providers.registry import registry
from marketdata.providers.tesouro import TesouroProvider
from marketdata.providers.yahoo import YahooProvider


def register_default_providers() -> None:
    known = {name.lower() for name in registry.names()}
    for provider in (
        CvmProvider(),
        TesouroProvider(),
        BcbProvider(),
        B3Provider(),
        YahooProvider(),
        FredProvider(),
        IbgeProvider(),
        CftcProvider(),
        EdgarProvider(),
    ):
        if provider.name not in known:
            registry.register(provider)
            known.add(provider.name)
