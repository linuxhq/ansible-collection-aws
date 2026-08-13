from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    ec2_instance_metadata_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class Ec2InstanceMetadataInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"] == {}

    def test_returns_account_defaults_and_region(self):
        module = FakeModule({}, client=Mock(), region="us-west-2")
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "get_instance_metadata_defaults",
                return_value={"http_tokens": "required"},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["region"], "us-west-2")
        self.assertEqual(
            raised.exception.values["account_level"], {"http_tokens": "required"}
        )
