from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    ec2_instance_type_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
    assert_module_rejects,
)


class Ec2InstanceTypeInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["instance_types"]["elements"] == "str"

    def test_instance_type_filter_is_forwarded(self):
        module = FakeModule(
            {"filters": None, "instance_types": ["t3.micro", "t3.micro"]},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3],
            {
                "describe_instance_types": (
                    "InstanceTypes",
                    "MaxResults",
                    "NextToken",
                )
            },
        )
        self.assertEqual(query.call_args.kwargs["InstanceTypes"], ["t3.micro"])

    def test_instance_type_limit_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "filters": None,
                "instance_types": [f"type-{index}" for index in range(101)],
            },
            "instance_types must contain at most 100 unique entries",
        )
