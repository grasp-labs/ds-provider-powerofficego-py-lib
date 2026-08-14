"""
**File:** ``endpoint_info.py``
**Region:** ``ds_provider_powerofficego_py_lib/endpoint_info``

This module contains classes and functions related to endpoint information for the PowerOfficeGo provider.
"""


class EndpointInfo:
    """
    Class representing information about an API endpoint for the PowerOfficeGo provider.
    """

    def __init__(
        self,
        name: str,
        endpoint: str,
    ) -> None:
        self.name = name
        self.endpoint = endpoint

    @staticmethod
    def get_endpoint_for_product(data_product: str) -> str:
        """
        Get the endpoint for a given data product.
        If the data product is not found in the ENDPOINTS mapping, it returns the data product name as endpoint.

        Args:
            data_product (str): The name of the data product.
        Returns:
            str: The endpoint URL if found, otherwise the data product name as endpoint.
        """
        endpoint_info = ENDPOINTS.get(data_product)
        if endpoint_info is not None:
            return str(endpoint_info.endpoint)
        return str(data_product)


ENDPOINTS = {
    "SupplierLedgerStatement": EndpointInfo(
        name="SupplierLedgerStatement",
        endpoint="SupplierLedger/Statement",
    ),
    "CustomerLedgerStatement": EndpointInfo(
        name="CustomerLedgerStatement",
        endpoint="CustomerLedger/Statement",
    ),
    "ClientAdminClient": EndpointInfo(
        name="ClientAdminClient",
        endpoint="ClientAdmin/Clients",
    ),
}
