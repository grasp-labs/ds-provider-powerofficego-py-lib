"""
**File:** ``enums.py``
**Region:** ``ds_provider_powerofficego_py_lib/enums``

Enums for PowerOfficeGo provider.
"""

from enum import StrEnum


class ResourceType(StrEnum):
    """
    Resource types for PowerOfficeGo provider.
    """

    POWEROFFICEGO_LINKED_SERVICE = "ds.resource.linked-service.powerofficego"
    POWEROFFICEGO_DATASET = "ds.resource.dataset.powerofficego"
