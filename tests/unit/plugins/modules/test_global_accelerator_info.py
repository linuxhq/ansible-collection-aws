from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import global_accelerator_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_accelerator_disappearing_during_tag_lookup_is_omitted():
    client = Mock()
    client.describe_accelerator.return_value = {"Accelerator": {"AcceleratorArn": "arn:gone"}}
    client.list_tags_for_resource.side_effect = plugin.ClientError(
        {
            "Error": {
                "Code": "AcceleratorNotFoundException",
                "Message": "gone",
            }
        },
        "ListTagsForResource",
    )
    module = FakeModule(
        {
            "arn": "arn:gone",
            "include_endpoint_groups": False,
            "include_listeners": False,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["accelerators"] == []


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["include_endpoint_groups"]["default"] is False


def test_malformed_accelerator_is_rejected():
    client = Mock(describe_accelerator=Mock(return_value={"Accelerator": None}))
    module = FakeModule(
        {
            "arn": "arn:accelerator",
            "include_endpoint_groups": False,
            "include_listeners": False,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Global Accelerator returned an invalid accelerator"


def test_malformed_tags_are_rejected():
    client = Mock()
    client.describe_accelerator.return_value = {"Accelerator": {"AcceleratorArn": "arn:accelerator"}}
    client.list_tags_for_resource.return_value = {"Tags": None}
    module = FakeModule(
        {
            "arn": "arn:accelerator",
            "include_endpoint_groups": False,
            "include_listeners": False,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Global Accelerator returned invalid tags"


def test_empty_results_defer_listener_methods():
    module = FakeModule(
        {"arn": None, "include_endpoint_groups": True, "include_listeners": False},
        client=Mock(),
    )
    require = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", require),
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_count == 1
    assert "list_listeners" not in require.call_args.args[3]
    assert "list_endpoint_groups" not in require.call_args.args[3]


def test_empty_results_do_not_require_tag_lookup():
    module = FakeModule(
        {"arn": None, "include_endpoint_groups": False, "include_listeners": False},
        client=Mock(),
    )
    require = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", require),
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_count == 1
    assert "list_tags_for_resource" not in require.call_args.args[3]


def test_endpoint_groups_are_nested_under_their_listener():
    client = Mock()
    client.describe_accelerator.return_value = {"Accelerator": {"AcceleratorArn": "arn:accelerator", "Name": "main"}}
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule(
        {
            "arn": "arn:accelerator",
            "include_endpoint_groups": True,
            "include_listeners": False,
        },
        client=client,
    )
    require = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", require),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[
                {"Listeners": [{"ListenerArn": "arn:listener"}]},
                {"EndpointGroups": [{"EndpointGroupArn": "arn:endpoint-group"}]},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    listener = raised.value.values["accelerators"][0]["listeners"][0]
    assert listener["accelerator_arn"] == "arn:accelerator"
    assert listener["endpoint_groups"][0]["endpoint_group_arn"] == "arn:endpoint-group"
    required_methods = {method for call in require.call_args_list for method in call.args[3]}
    assert "list_listeners" in required_methods
    assert "list_endpoint_groups" in required_methods


def test_missing_accelerator_arn_returns_an_empty_list():
    client = Mock()
    client.describe_accelerator.side_effect = plugin.ClientError(
        {"Error": {"Code": "AcceleratorNotFoundException", "Message": "missing"}}, "DescribeAccelerator"
    )
    module = FakeModule(
        {"arn": "arn:missing", "include_endpoint_groups": False, "include_listeners": False},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["accelerators"] == []
