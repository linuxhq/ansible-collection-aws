from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_malformed_endpoint_is_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"Arn": "arn:endpoint"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "without a valid ID" in raised.value.values["msg"]


def test_malformed_detail_response_is_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"Id": "rslvr-1"}]),
        patch.object(plugin, "paginated_query_with_retries", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "list_resolver_endpoint_ip_addresses: AWS returned an invalid response"


def test_malformed_ip_address_and_tag_are_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    endpoint = {"Arn": "arn:endpoint", "Id": "rslvr-1"}
    cases = [
        ([{"Ip": "192.0.2.1"}], "without a subnet ID"),
        ([{"Key": "Name"}], "invalid tag"),
    ]
    for index, (items, message) in enumerate(cases):
        responses = (
            [{"IpAddresses": items}]
            if index == 0
            else [
                {"IpAddresses": [{"SubnetId": "subnet-1"}]},
                {"Tags": items},
            ]
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[endpoint]),
            patch.object(plugin, "paginated_query_with_retries", side_effect=responses),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert message in raised.value.values["msg"]


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["filters"]["type"] == "dict"


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


def test_endpoint_with_a_malformed_name_is_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"Id": "rslvr-1", "Name": 1}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "list_resolver_endpoints: AWS returned an invalid resolver endpoint Name"
