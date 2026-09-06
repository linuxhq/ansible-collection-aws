from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import eks_cluster_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class EksClusterInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["mutually_exclusive"] == [["include", "name"]]

    def test_value_matching_supports_wildcards_and_collections(self):
        assert plugin.value_matches(["prod-a", "dev-a"], "prod-*")
        assert not plugin.value_matches(["dev-a"], "prod-*")

    def test_named_lookup_only_requires_describe(self):
        client = Mock(describe_cluster=Mock(return_value={"cluster": {"name": "one"}}))
        module = FakeModule({"filters": None, "include": None, "name": "one"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_methods.assert_called_once_with(module, client, "EKS", {"describe_cluster": ("name",)})

    def test_empty_name_requires_list_clusters(self):
        client = Mock()
        module = FakeModule({"filters": None, "include": None, "name": ""}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_methods.assert_called_once_with(
            module,
            client,
            "EKS",
            {"list_clusters": ("maxResults", "nextToken")},
        )

    def test_malformed_cluster_list_is_rejected(self):
        client = Mock()
        module = FakeModule({"filters": None, "include": None, "name": None}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[None]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["msg"], "EKS returned an invalid cluster list")

    def test_malformed_describe_response_is_rejected(self):
        client = Mock(describe_cluster=Mock(return_value={"cluster": None}))
        module = FakeModule({"filters": None, "include": None, "name": "one"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "EKS returned an invalid cluster for one",
        )

    def test_nested_and_tag_filters_are_combined(self):
        client = Mock()
        client.describe_cluster.side_effect = [
            {
                "cluster": {
                    "name": "prod",
                    "resourcesVpcConfig": {"endpointPublicAccess": False},
                    "tags": {"Environment": "prod-west"},
                }
            },
            {
                "cluster": {
                    "name": "dev",
                    "resourcesVpcConfig": {"endpointPublicAccess": False},
                    "tags": {"Environment": "dev-west"},
                }
            },
        ]
        module = FakeModule(
            {
                "filters": {
                    "resources-vpc-config.endpoint-public-access": False,
                    "tag:Environment": "prod-*",
                },
                "include": ["all", "all"],
                "name": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=["prod", "dev"]) as query,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(
            [cluster["name"] for cluster in raised.exception.values["clusters"]],
            ["prod"],
        )
        self.assertEqual(query.call_args.kwargs["include"], ["all"])
