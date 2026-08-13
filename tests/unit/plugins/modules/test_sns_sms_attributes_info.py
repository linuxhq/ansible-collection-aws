from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    sns_sms_attributes_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class SnsSmsAttributesInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["attributes"]["elements"] == "str"

    def test_requested_attributes_are_forwarded(self):
        client = Mock(get_sms_attributes=Mock(return_value={"attributes": {}}))
        module = FakeModule(
            {"attributes": ["DefaultSMSType", "DefaultSMSType"]}, client=client
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3], {"get_sms_attributes": ("attributes",)}
        )
        client.get_sms_attributes.assert_called_once_with(
            attributes=["DefaultSMSType"], aws_retry=True
        )
