from unittest import TestCase
from unittest.mock import Mock, call, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    pinpoint_sms_voice_phone_number_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class PinpointSmsVoicePhoneNumberInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["mutually_exclusive"] == [["owner", "phone_number_ids"]]
        assert "default" not in options["argument_spec"]["owner"]

    def test_ids_do_not_send_the_implicit_owner(self):
        module = FakeModule(
            {
                "filters": None,
                "max_results": None,
                "owner": None,
                "phone_number_ids": ["phone-1"],
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(query.call_args.kwargs, {"PhoneNumberIds": ["phone-1"]})

    def test_empty_result_does_not_require_tag_operations(self):
        module = FakeModule(
            {
                "filters": None,
                "max_results": None,
                "owner": "SELF",
                "phone_number_ids": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(
            require.call_args.args[3],
            {"describe_phone_numbers": ("Owner", "MaxResults", "NextToken")},
        )

    def test_rejects_max_results_above_provider_limit(self):
        module = FakeModule(
            {
                "filters": None,
                "max_results": 101,
                "owner": "SELF",
                "phone_number_ids": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"], "max_results must be between 1 and 100"
        )

    def test_rejects_provider_list_limits(self):
        cases = [
            (
                {
                    "filters": {str(index): "x" for index in range(21)},
                    "max_results": None,
                    "owner": None,
                    "phone_number_ids": None,
                },
                "filters must contain at most 20 entries",
            ),
            (
                {
                    "filters": None,
                    "max_results": None,
                    "owner": None,
                    "phone_number_ids": [f"phone-{index}" for index in range(6)],
                },
                "phone_number_ids must contain at most 5 entries",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                module = FakeModule(params)
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    plugin.main()
                self.assertEqual(raised.exception.values["msg"], message)

    def test_phone_numbers_are_enriched_with_tags(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {
            "Tags": [{"Key": "Name", "Value": "primary"}]
        }
        module = FakeModule(
            {
                "filters": None,
                "max_results": None,
                "owner": "SELF",
                "phone_number_ids": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "query_list",
                return_value=[
                    {"PhoneNumberArn": "arn:phone", "PhoneNumberId": "phone-1"}
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["phone_number_ids"], ["phone-1"])
        self.assertEqual(
            raised.exception.values["phone_numbers"][0]["tags"],
            {"Name": "primary"},
        )
        self.assertEqual(
            require.call_args_list,
            [
                call(
                    module,
                    client,
                    "Pinpoint SMS Voice V2",
                    {
                        "describe_phone_numbers": (
                            "Owner",
                            "MaxResults",
                            "NextToken",
                        )
                    },
                ),
                call(
                    module,
                    client,
                    "Pinpoint SMS Voice V2",
                    {"list_tags_for_resource": ("ResourceArn",)},
                ),
            ],
        )
