from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import iam_policy_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["path_prefix"]["type"] == "str"


def test_explicit_entity_name_skips_listing():
    module = SimpleNamespace(params={"group_name": "admins", "path_prefix": "/", "role_name": None, "user_name": None})
    assert plugin.entity_names(None, module, "Group") == ["admins"]


def test_explicit_names_do_not_require_entity_list_operations():
    client = Mock()
    module = FakeModule(
        {
            "group_name": "admins",
            "path_prefix": "/",
            "policy_name": None,
            "role_name": None,
            "user_name": "alice",
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "build_entity_policies", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require_methods.assert_not_called()


def test_empty_results_only_require_entity_list_operations():
    client = Mock()
    module = FakeModule(
        {
            "group_name": "",
            "path_prefix": None,
            "policy_name": None,
            "role_name": "",
            "user_name": "",
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "build_entity_policies", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert [call.args[3] for call in require_methods.call_args_list] == [
        {"list_groups": ("Marker", "MaxItems")},
        {"list_roles": ("Marker", "MaxItems")},
        {"list_users": ("Marker", "MaxItems")},
    ]


def test_policy_name_filters_documents_after_preserving_all_names():
    client = Mock(get_user_policy=Mock(return_value={"PolicyDocument": {"Statement": ["selected"]}}))
    module = SimpleNamespace(params={"policy_name": "selected"})
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"PolicyNames": ["ignored", "selected"]},
        ),
    ):
        result = plugin.build_entity_policies(client, module, "User", ["alice"])

    assert result[0]["all_policy_names"] == ["ignored", "selected"]
    assert result[0]["policy_names"] == ["selected"]
    client.get_user_policy.assert_called_once_with(UserName="alice", PolicyName="selected", aws_retry=True)


def test_entity_names_rejects_invalid_response():
    module = FakeModule({"group_name": None, "path_prefix": None, "role_name": None, "user_name": None})
    with (
        patch.object(plugin, "query_list", return_value=[{}]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.entity_names(Mock(), module, "User")

    assert raised.value.values["msg"] == "Unable to list AWS IAM users: AWS returned an invalid response"


def test_policy_names_reject_invalid_response():
    module = FakeModule({"policy_name": None})
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value={}),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.build_entity_policies(Mock(), module, "User", ["alice"])

    assert (
        raised.value.values["msg"] == "Unable to list AWS IAM user policies for alice: AWS returned an invalid response"
    )


def test_policy_document_rejects_invalid_response():
    client = Mock(get_user_policy=Mock(return_value={}))
    module = FakeModule({"policy_name": None})
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value={"PolicyNames": ["main"]}),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.build_entity_policies(client, module, "User", ["alice"])

    assert (
        raised.value.values["msg"]
        == "Unable to get AWS IAM user policy main for alice: AWS returned an invalid response"
    )


@pytest.mark.parametrize("path_prefix", ["service", "/service prefix/", "/" + "a" * 512])
def test_invalid_path_prefix_is_rejected_before_api_calls(path_prefix):
    module = FakeModule(
        {
            "group_name": None,
            "path_prefix": path_prefix,
            "policy_name": None,
            "role_name": None,
            "user_name": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == (
        "path_prefix must begin with /, contain only printable ASCII characters, and contain at most 512 characters"
    )


@pytest.mark.parametrize("path_prefix", ["/", "/aws-serv", "/service/", "/" + "a" * 511])
def test_api_valid_path_prefix_is_accepted(path_prefix):
    module = FakeModule(
        {
            "group_name": None,
            "path_prefix": path_prefix,
            "policy_name": None,
            "role_name": None,
            "user_name": None,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "entity_names", return_value=[]),
        patch.object(plugin, "build_entity_policies", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()


def test_empty_entity_names_require_no_policy_operations():
    module = SimpleNamespace(params={"policy_name": None})
    with patch.object(plugin, "require_client_methods") as require_methods:
        assert plugin.build_entity_policies(Mock(), module, "User", []) == []

    require_methods.assert_not_called()


def test_unmatched_policy_name_does_not_require_get_operation():
    module = SimpleNamespace(params={"policy_name": "selected"})
    client = Mock()
    with (
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"PolicyNames": ["ignored"]},
        ),
    ):
        plugin.build_entity_policies(client, module, "User", ["alice"])

    require_methods.assert_called_once_with(
        module,
        client,
        "IAM",
        {"list_user_policies": ("UserName", "Marker", "MaxItems")},
    )


def test_named_entity_scopes_the_query_to_its_type():
    module = SimpleNamespace(params={"group_name": None, "path_prefix": None, "role_name": "app", "user_name": None})
    with patch.object(plugin, "query_list") as query:
        assert plugin.entity_names(Mock(), module, "Role") == ["app"]
        assert plugin.entity_names(Mock(), module, "Group") == []
        assert plugin.entity_names(Mock(), module, "User") == []

    query.assert_not_called()


def test_role_policies_use_the_role_operations():
    client = Mock(get_role_policy=Mock(return_value={"PolicyDocument": {"Statement": []}}))
    module = SimpleNamespace(params={"policy_name": None})
    with (
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "paginated_query_with_retries", return_value={"PolicyNames": ["main"]}) as query,
    ):
        result = plugin.build_entity_policies(client, module, "Role", ["app"])

    assert result[0]["policies"] == [{"policy_name": "main", "policy_document": {"Statement": []}}]
    query.assert_called_once_with(client, "list_role_policies", RoleName="app")
    client.get_role_policy.assert_called_once_with(RoleName="app", PolicyName="main", aws_retry=True)
    assert [call.args[3] for call in require_methods.call_args_list] == [
        {"list_role_policies": ("RoleName", "Marker", "MaxItems")},
        {"get_role_policy": ("RoleName", "PolicyName")},
    ]


def test_missing_entity_is_not_included_in_the_results():
    error = plugin.ClientError({"Error": {"Code": "NoSuchEntity", "Message": "missing"}}, "ListUserPolicies")
    module = FakeModule({"policy_name": None})
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=error),
    ):
        assert plugin.build_entity_policies(Mock(), module, "User", ["missing"]) == []
