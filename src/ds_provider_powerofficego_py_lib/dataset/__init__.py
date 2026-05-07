"""
**File:** ``__init__.py``
**Region:** ``ds_provider_powerofficego_py_lib/dataset``

This module contains dataset-related classes and functions for the PowerOfficeGo provider.
"""

from .powerofficego import PowerOfficeGoDataset, PowerOfficeGoDatasetSettings, ReadSettings

__all__ = [
    "PowerOfficeGoDataset",
    "PowerOfficeGoDatasetSettings",
    "ReadSettings",
]
