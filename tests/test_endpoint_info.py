from ds_provider_powerofficego_py_lib.endpoint_info import EndpointInfo


def test_get_endpoint_for_product_found():
    # Known product
    ep = EndpointInfo.get_endpoint_for_product("SupplierLedgerStatement")
    assert ep == "SupplierLedger/Statement"


def test_get_endpoint_for_product_not_found():
    # Unknown product returns the product name
    ep = EndpointInfo.get_endpoint_for_product("UnknownProduct")
    assert ep == "UnknownProduct"
