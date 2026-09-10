from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_instance_metadata as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Ec2InstanceMetadataTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_one_of"] == [
            [
                "http_endpoint",
                "http_put_response_hop_limit",
                "http_tokens",
                "instance_metadata_tags",
            ]
        ]

    def test_rejects_hop_limit_outside_ec2_range(self):
        module = FakeModule(
            {
                "http_endpoint": None,
                "http_put_response_hop_limit": 65,
                "http_tokens": None,
                "instance_metadata_tags": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("between 1 and 64", raised.exception.values["msg"])

    def test_check_mode_projects_clearing_an_account_default(self):
        client = Mock()
        module = FakeModule(
            {
                "http_endpoint": None,
                "http_put_response_hop_limit": -1,
                "http_tokens": None,
                "instance_metadata_tags": None,
            },
            check_mode=True,
            client=client,
        )
        current = {
            "http_put_response_hop_limit": 2,
            "http_tokens": "required",
        }
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "get_instance_metadata_defaults", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["account_level"], {"http_tokens": "required"})
        client.modify_instance_metadata_defaults.assert_not_called()
        self.assertEqual(require.call_count, 1)
        self.assertEqual(require.call_args.args[3], {"get_instance_metadata_defaults": ()})

    def test_update_projects_new_defaults_without_a_stale_refresh(self):
        client = Mock()
        module = FakeModule(
            {
                "http_endpoint": None,
                "http_put_response_hop_limit": None,
                "http_tokens": "required",
                "instance_metadata_tags": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "get_instance_metadata_defaults",
                return_value={"http_tokens": "optional"},
            ) as get_defaults,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["account_level"]["http_tokens"], "required")
        self.assertEqual(get_defaults.call_count, 1)
        self.assertEqual(require.call_count, 2)
        self.assertEqual(
            require.call_args.args[3],
            {"modify_instance_metadata_defaults": ("HttpTokens",)},
        )
