from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_flow_log_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class Ec2FlowLogInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["resource_ids"]["elements"] == "str"

    def test_flow_log_ids_are_sent_to_aws(self):
        module = FakeModule(
            {
                "filters": None,
                "flow_log_ids": ["fl-1", "fl-1"],
                "resource_ids": None,
            },
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
            {"describe_flow_logs": ("FlowLogIds", "MaxResults", "NextToken")},
        )
        self.assertEqual(query.call_args.kwargs["FlowLogIds"], ["fl-1"])
