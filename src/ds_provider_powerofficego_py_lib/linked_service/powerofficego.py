"""
**File:** ``powerofficego.py``
**Region:** ``ds_provider_powerofficego_py_lib/linked_service/powerofficego``

PowerOfficeGo Linked Service.

This module defines the PowerOfficeGo linked service, which is used to connect
to the PowerOfficeGo API. It includes the necessary configuration and
authentication details required to establish a connection with the PowerOfficeGo service.

Example:
    >>> from uuid import UUID
    >>> linked_service = PowerOfficeGoLinkedService(
    ...     id=UUID("12345678-1234-5678-1234-1234567890ab"),
    ...     name="pogo-linked-service",
    ...     version="v1.0.0",
    ...     settings=PowerOfficeGoLinkedServiceSettings(
    ...         application_key="my-application-key",
    ...         client_id="my-client-id",
    ...         subscription_key="my-subscription-key",
    ...     ),
    ... )
    >>> linked_service.connect()
"""

import base64
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ds_protocol_http_py_lib import HttpLinkedService, HttpLinkedServiceSettings
from ds_protocol_http_py_lib.enums import AuthType
from ds_protocol_http_py_lib.linked_service import OAuth2AuthSettings

from ..enums import ResourceType


@dataclass(kw_only=True)
class PowerOfficeGoLinkedServiceSettings(HttpLinkedServiceSettings):
    """
    Settings for PowerOfficeGo linked service in order to connect to the PowerOfficeGo API.

    Attributes:
    """

    application_key: str = field(metadata={"mask": True})
    """Application key for PowerOfficeGo API authentication."""

    client_id: str = field(metadata={"mask": True})
    """Client ID for PowerOfficeGo API authentication."""

    subscription_key: str = field(metadata={"mask": True})
    """Subscription key for PowerOfficeGo API authentication."""

    headers: dict[str, str] | None = None
    """Headers for PowerOfficeGo API requests."""

    token_endpoint: str = "https://goapi.poweroffice.net/OAuth/Token"
    """Token endpoint URL for PowerOfficeGo API authentication."""

    host: str = "https://goapi.poweroffice.net/"
    """Host URL for PowerOfficeGo API."""

    api_version: str = "v2"
    """API version for PowerOfficeGo API."""

    auth_type: AuthType = AuthType.OAUTH2
    """Authentication type for PowerOfficeGo API."""

    oauth2: OAuth2AuthSettings | None = None
    """OAuth2 authentication settings for PowerOfficeGo API."""


PowerOfficeGoLinkedServiceSettingsType = TypeVar(
    "PowerOfficeGoLinkedServiceSettingsType", bound=PowerOfficeGoLinkedServiceSettings
)


@dataclass(kw_only=True)
class PowerOfficeGoLinkedService(
    HttpLinkedService[PowerOfficeGoLinkedServiceSettingsType], Generic[PowerOfficeGoLinkedServiceSettingsType]
):
    """
    PowerOfficeGo linked service for connecting to the PowerOfficeGo API.

    This class extends the HttpLinkedService and provides specific settings for
    connecting to the PowerOfficeGo API. It includes the necessary authentication
    details and configuration required to establish a connection with the PowerOfficeGo service.
    """

    settings: PowerOfficeGoLinkedServiceSettingsType
    """Settings for PowerOfficeGo linked service."""

    @property
    def type(self) -> ResourceType:  # type: ignore[override]
        """
        Get the resource type for PowerOfficeGo linked service.

        Returns:
            ResourceType: The resource type for PowerOfficeGo linked service.
        """
        return ResourceType.POWEROFFICEGO_LINKED_SERVICE

    def __post_init__(self) -> None:
        """
        Post-initialization processing for PowerOfficeGo linked service.

        This method is called after the dataclass has been initialized. It can be used
        to perform any additional setup or validation required for the PowerOfficeGo linked service.
        """
        base64_encoded_credentials = base64.b64encode(
            f"{self.settings.application_key}:{self.settings.client_id}".encode()
        ).decode("utf-8")
        if self.settings.headers is None:
            self.settings.headers = {
                "Authorization": f"Basic {base64_encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Ocp-Apim-Subscription-Key": self.settings.subscription_key,
            }
        if self.settings.auth_type == AuthType.OAUTH2 and self.settings.oauth2 is None:
            self.settings.oauth2 = OAuth2AuthSettings(token_endpoint=self.settings.token_endpoint, client_id="", client_secret="")  # nosec B106
        super().__post_init__()
