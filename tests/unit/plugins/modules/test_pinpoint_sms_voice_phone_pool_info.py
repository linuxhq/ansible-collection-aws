from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    pinpoint_sms_voice_phone_pool_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class PinpointSmsVoicePhonePoolInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["mutually_exclusive"] == [["owner", "pool_ids"]]
        assert "default" not in options["argument_spec"]["owner"]

    def test_ids_do_not_send_the_implicit_owner(self):
        module = FakeModule(
            {
                "filters": None,
                "max_results": None,
                "owner": None,
                "pool_ids": ["pool-1"],
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(query.call_args.kwargs, {"PoolIds": ["pool-1"]})

    def test_rejects_nonpositive_max_results(self):
        module = FakeModule(
            {"filters": None, "max_results": 0, "owner": "SELF", "pool_ids": None}
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
                    "pool_ids": None,
                },
                "filters must contain at most 20 entries",
            ),
            (
                {
                    "filters": None,
                    "max_results": None,
                    "owner": None,
                    "pool_ids": [f"pool-{index}" for index in range(6)],
                },
                "pool_ids must contain at most 5 entries",
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

    def test_pools_are_enriched_with_identities_and_tags(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {
            "Tags": [{"Key": "Name", "Value": "primary"}]
        }
        module = FakeModule(
            {
                "filters": None,
                "max_results": None,
                "owner": "SELF",
                "pool_ids": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "query_list",
                return_value=[{"PoolArn": "arn:pool", "PoolId": "pool-1"}],
            ),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={
                    "OriginationIdentities": [{"OriginationIdentity": "phone-1"}]
                },
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        pool = raised.exception.values["pools"][0]
        self.assertEqual(
            pool["origination_identities"][0]["origination_identity"], "phone-1"
        )
        self.assertEqual(pool["tags"], {"Name": "primary"})
        self.assertEqual(
            require.call_args.args[3],
            {
                "describe_pools": ("Owner", "MaxResults", "NextToken"),
                "list_pool_origination_identities": (
                    "PoolId",
                    "MaxResults",
                    "NextToken",
                ),
                "list_tags_for_resource": ("ResourceArn",),
            },
        )
