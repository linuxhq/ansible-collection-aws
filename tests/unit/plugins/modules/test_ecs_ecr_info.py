from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ecs_ecr_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
    assert_module_rejects,
)


class EcsEcrInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["repository_names"]["elements"] == "str"

    def test_repository_filters_are_sent_to_ecr(self):
        module = FakeModule(
            {"registry_id": None, "repository_names": ["app", "app"]},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"repositories": []},
            ) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3],
            {
                "describe_repositories": (
                    "repositoryNames",
                    "maxResults",
                    "nextToken",
                )
            },
        )
        self.assertEqual(query.call_args.kwargs["repositoryNames"], ["app"])

    def test_repository_name_limit_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "registry_id": None,
                "repository_names": [f"repository-{index}" for index in range(101)],
            },
            "repository_names must contain at most 100 unique entries",
        )
