"""
**File:** ``test_powerofficego.py``
**Region:** ``tests/linked_service/test_powerofficego``

Linked Service tests for PowerOfficeGo provider.
"""

import base64
from unittest.mock import patch

from ds_provider_powerofficego_py_lib.enums import ResourceType
from ds_provider_powerofficego_py_lib.linked_service.powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings,
)


def test_settings_headers_and_basic_default_and_post_init():
    # headers should be None before __post_init__, then set after
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", headers=None
    )
    # Before __post_init__, headers is None
    assert settings.headers is None
    # After constructing the service, __post_init__ is called and fields are set
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    assert service is not None

    expected_auth = base64.b64encode(b"appkey:clientid").decode("utf-8")
    assert settings.headers == {
        "Authorization": f"Basic {expected_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Ocp-Apim-Subscription-Key": "subkey",
    }
    assert settings.oauth2 is not None
    assert settings.oauth2.token_endpoint == settings.token_endpoint


def test_settings_headers_and_basic_override():
    # If headers and oauth2 are provided, they should not be overwritten
    custom_headers = {"X-Test": "value"}

    class DummyOAuth2:
        def __init__(self, token_endpoint, client_id, client_secret):
            self.token_endpoint = token_endpoint
            self.client_id = client_id
            self.client_secret = client_secret

    custom_oauth2 = DummyOAuth2("https://custom-token-endpoint", "cid", "csecret")
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", headers=custom_headers, oauth2=custom_oauth2
    )
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    assert service is not None
    assert settings.headers == custom_headers
    assert settings.oauth2 == custom_oauth2


def test_linked_service_type():
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", headers=None
    )
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    assert service.type == ResourceType.POWEROFFICEGO_LINKED_SERVICE


def test_linked_service_post_init_calls_super():
    settings = PowerOfficeGoLinkedServiceSettings(application_key="appkey", client_id="clientid", subscription_key="subkey")
    with patch("ds_protocol_http_py_lib.HttpLinkedService.__post_init__") as mock_super:
        PowerOfficeGoLinkedService(
            id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
        )
        mock_super.assert_called_once()
