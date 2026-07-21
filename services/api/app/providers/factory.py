from app.core.config import ProviderMode, Settings
from app.providers.contracts import MediaOrchestrator
from app.providers.gmi import GenblazeGMICloudOrchestrator
from app.providers.mock import MockMediaOrchestrator


def build_media_orchestrator(settings: Settings) -> MediaOrchestrator:
    if settings.provider_mode is ProviderMode.MOCK:
        return MockMediaOrchestrator()
    return GenblazeGMICloudOrchestrator(settings)
