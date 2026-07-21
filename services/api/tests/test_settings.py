import pytest
from pydantic import ValidationError

from app.core.config import ProviderMode, Settings


def test_mock_mode_does_not_require_cloud_credentials() -> None:
    settings = Settings(_env_file=None)
    assert settings.provider_mode is ProviderMode.MOCK
    assert settings.has_gmi_credentials() is False


def test_live_mode_requires_private_storage_and_provider_secrets() -> None:
    with pytest.raises(ValidationError) as raised:
        Settings(_env_file=None, provider_mode=ProviderMode.LIVE)
    assert "GMI_API_KEY" in str(raised.value)
    assert "B2_BUCKET" in str(raised.value)
