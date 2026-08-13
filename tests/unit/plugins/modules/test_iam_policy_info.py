from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import iam_policy_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class IamPolicyInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["path_prefix"]["type"] == "str"

    def test_explicit_entity_name_skips_listing(self):
        module = SimpleNamespace(params={"group_name": "admins", "path_prefix": "/", "user_name": None})
        assert plugin.entity_names(None, module, "Group") == ["admins"]

    def test_explicit_names_do_not_require_entity_list_operations(self):
        client = Mock()
        module = FakeModule(
            {
                "group_name": "admins",
                "path_prefix": "/",
                "policy_name": None,
                "user_name": "alice",
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "build_entity_policies", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_methods.assert_not_called()

    def test_empty_results_only_require_entity_list_operations(self):
        client = Mock()
        module = FakeModule(
            {
                "group_name": "",
                "path_prefix": None,
                "policy_name": None,
                "user_name": "",
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "query_list", return_value=[]),
            patch.object(plugin, "build_entity_policies", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(
            [call.args[3] for call in require_methods.call_args_list],
            [
                {"list_groups": ("Marker", "MaxItems")},
                {"list_users": ("Marker", "MaxItems")},
            ],
        )

    def test_policy_name_filters_documents_after_preserving_all_names(self):
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

        self.assertEqual(result[0]["all_policy_names"], ["ignored", "selected"])
        self.assertEqual(result[0]["policy_names"], ["selected"])
        client.get_user_policy.assert_called_once_with(UserName="alice", PolicyName="selected", aws_retry=True)

    def test_empty_entity_names_require_no_policy_operations(self):
        module = SimpleNamespace(params={"policy_name": None})
        with patch.object(plugin, "require_client_methods") as require_methods:
            assert plugin.build_entity_policies(Mock(), module, "User", []) == []
        require_methods.assert_not_called()

    def test_unmatched_policy_name_does_not_require_get_operation(self):
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
