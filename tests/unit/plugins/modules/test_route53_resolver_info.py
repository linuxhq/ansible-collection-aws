from unittest.mock import Mock, patch

import pytest
import yaml

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_documents_shape,
    assert_module_contract,
    documented_returns,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["filters"]["type"] == "dict"


def test_documented_returns_cover_the_sdk_shapes():
    contains = documented_returns(plugin)["resolver_endpoints"]["contains"]
    assert_documents_shape(contains, "route53resolver", "ResolverEndpoint")
    assert_documents_shape(contains["ip_addresses"]["contains"], "route53resolver", "IpAddressResponse")


def test_empty_endpoint_list_skips_detail_calls():
    module = FakeModule({"filters": None}, client=Mock())
    details = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "paginated_query_with_retries", details),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    details.assert_not_called()
    require_methods.assert_called_once()
    assert list(require_methods.call_args.args[3]) == ["list_resolver_endpoints"]
    assert raised.value.values["resolver_endpoints"] == []


def test_endpoints_are_enriched_with_ip_addresses_and_tags():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"Arn": "arn:endpoint", "Id": "rslvr-1"}],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[
                {"IpAddresses": [{"Ip": "192.0.2.1", "SubnetId": "subnet-1"}]},
                {"Tags": [{"Key": "Name", "Value": "main"}]},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    endpoint = raised.value.values["resolver_endpoints"][0]
    assert endpoint["ip_addresses"][0]["ip"] == "192.0.2.1"
    assert endpoint["tags"] == {"Name": "main"}


def test_unnamed_endpoint_result_omits_name_as_documented():
    returned = yaml.safe_load(plugin.RETURN)["resolver_endpoints"]["contains"]["name"]["returned"]
    assert returned != "always"

    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"Arn": "arn:endpoint", "Id": "rslvr-in-1", "Status": "OPERATIONAL"}],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[{"IpAddresses": [{"SubnetId": "subnet-1"}]}, {"Tags": []}],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    endpoint = raised.value.values["resolver_endpoints"][0]
    assert endpoint["id"] == "rslvr-in-1"
    assert "name" not in endpoint
