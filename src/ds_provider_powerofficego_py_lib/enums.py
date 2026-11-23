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


class DataProduct(StrEnum):
    """PowerOfficeGo / DS config data product names with specialized read behavior."""

    TRIAL_BALANCE = "TrialBalance"


class TrialBalanceFilter(StrEnum):
    """Provider-only ``ReadSettings.filters`` keys for TrialBalance history.

    These are not forwarded as native PowerOffice query params. Native as-of
    date for each call is still ``date``.
    """

    DATE_FROM = "date_from"
    DATE_TO = "date_to"
