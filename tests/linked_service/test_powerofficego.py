"""
**File:** ``test_powerofficego.py``
**Region:** ``tests/linked_service/test_powerofficego``

Linked Service tests for PowerOfficeGo provider.
"""

from unittest.mock import patch

from ds_provider_powerofficego_py_lib.enums import ResourceType
from ds_provider_powerofficego_py_lib.linked_service.powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings,
)


class DummyBasicAuth:
    def __init__(self, username, password):
        self.username = username
        self.password = password


def test_settings_headers_and_basic_default_and_post_init():
    # headers and basic should be None before __post_init__, then set after
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", headers=None, basic=None
    )
    # Before __post_init__, headers and basic are None
    assert settings.headers is None
    assert settings.basic is None
    # After __post_init__, headers and basic are set
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    service.__post_init__()
    assert settings.headers == {"Ocp-Apim-Subscription-Key": "subkey"}
    assert settings.basic is not None
    assert settings.basic.username == "appkey"
    assert settings.basic.password == "clientid"


def test_settings_headers_and_basic_override():
    # If headers and basic are provided, they should not be overwritten
    custom_headers = {"X-Test": "value"}

    class DummyBasic:
        def __init__(self, username, password):
            self.username = username
            self.password = password

    custom_basic = DummyBasic("u", "p")
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", headers=custom_headers, basic=custom_basic
    )
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    service.__post_init__()
    assert settings.headers == custom_headers
    assert settings.basic == custom_basic


def test_linked_service_type():
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", headers=None
    )
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    service.__post_init__()
    assert service.type == ResourceType.POWEROFFICEGO_LINKED_SERVICE


def test_linked_service_post_init_calls_super():
    settings = PowerOfficeGoLinkedServiceSettings(application_key="appkey", client_id="clientid", subscription_key="subkey")
    service = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    with patch("ds_protocol_http_py_lib.HttpLinkedService.__post_init__") as mock_super:
        service.__post_init__()
        mock_super.assert_called_once()
