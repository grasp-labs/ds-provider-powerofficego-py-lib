"""
**File:** ``__init__.py``
**Region:** ``ds_provider_powerofficego_py_lib/linked_service``

PowerOfficeGo Linked Service

This module defines the PowerOfficeGo linked service for the PowerOfficeGo provider.

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
    >>> linked_service.test_connection()
"""

from .powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings,
)

__all__ = ["PowerOfficeGoLinkedService", "PowerOfficeGoLinkedServiceSettings"]
