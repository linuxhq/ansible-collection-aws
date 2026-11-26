from unittest.mock import Mock, call, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import global_accelerator_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


def test_accelerator_disappearing_during_tag_lookup_is_omitted():
    client = Mock()
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
        patch.object(plugin, "get_accelerator_by_arn", return_value={"AcceleratorArn": "arn:gone"}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["accelerators"] == []


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["include_endpoint_groups"]["default"] is False


def test_empty_arn_lists_every_accelerator():
    module = FakeModule({"arn": "", "include_endpoint_groups": False, "include_listeners": False}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query_list,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert query_list.call_args.args[2] == "list_accelerators"
    module.client().describe_accelerator.assert_not_called()
    assert raised.value.values["accelerators"] == []


def test_empty_results_require_only_the_accelerator_listing():
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

    # Listener, endpoint group, and tag methods are checked only when an accelerator is found.
    assert require.call_args_list == [
        call(module, module.client(), "Global Accelerator", {"list_accelerators": ("MaxResults", "NextToken")})
    ]


def test_endpoint_groups_are_nested_under_their_listener():
    client = Mock()
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
            plugin, "get_accelerator_by_arn", return_value={"AcceleratorArn": "arn:accelerator", "Name": "main"}
        ),
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


def test_listing_methods_are_checked_once_for_every_accelerator_and_listener():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule({"arn": None, "include_endpoint_groups": True, "include_listeners": False}, client=client)
    require = Mock()
    accelerators = [{"AcceleratorArn": "arn:a", "Name": "a"}, {"AcceleratorArn": "arn:b", "Name": "b"}]
    listeners = {"Listeners": [{"ListenerArn": "arn:l1"}, {"ListenerArn": "arn:l2"}]}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", require),
        patch.object(plugin, "query_list", return_value=accelerators),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=lambda client, method, **kwargs: (
                listeners if method == "list_listeners" else {"EndpointGroups": []}
            ),
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert len(raised.value.values["accelerators"]) == 2
    checked = [method for call in require.call_args_list for method in call.args[3]]
    assert checked.count("list_listeners") == 1
    assert checked.count("list_endpoint_groups") == 1


def test_missing_accelerator_arn_returns_an_empty_list():
    client = Mock()
    module = FakeModule(
        {"arn": "arn:missing", "include_endpoint_groups": False, "include_listeners": False},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_accelerator_by_arn", return_value=None) as get_accelerator_by_arn,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["accelerators"] == []
    get_accelerator_by_arn.assert_called_once_with(client, module, "arn:missing")
    client.list_tags_for_resource.assert_not_called()
