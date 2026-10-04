from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import eks_cluster_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["include", "name"]]
    assert "filters" not in options["argument_spec"]


def test_named_lookup_only_requires_describe():
    client = Mock(describe_cluster=Mock(return_value={"cluster": {"name": "one"}}))
    module = FakeModule({"include": None, "name": "one"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require_methods.assert_called_once_with(module, client, "EKS", {"describe_cluster": ("name",)})


def test_empty_name_requires_list_clusters():
    client = Mock()
    module = FakeModule({"include": None, "name": ""}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require_methods.assert_called_once_with(
        module,
        client,
        "EKS",
        {"list_clusters": ("maxResults", "nextToken")},
    )


def test_malformed_cluster_list_is_rejected():
    client = Mock()
    module = FakeModule({"include": None, "name": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "EKS returned an invalid cluster list"


def test_malformed_describe_response_is_rejected():
    client = Mock(describe_cluster=Mock(return_value={"cluster": None}))
    module = FakeModule({"include": None, "name": "one"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "EKS returned an invalid cluster for one"


def test_named_missing_cluster_returns_an_empty_list():
    client = Mock()
    client.describe_cluster.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}}, "DescribeCluster"
    )
    module = FakeModule({"include": None, "name": "missing"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["clusters"] == []


def test_listed_cluster_deleted_before_describe_is_skipped():
    client = Mock()
    client.describe_cluster.side_effect = [
        plugin.ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}}, "DescribeCluster"),
        {"cluster": {"name": "two"}},
    ]
    module = FakeModule({"include": None, "name": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=["one", "two"]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [cluster["name"] for cluster in raised.value.values["clusters"]] == ["two"]
