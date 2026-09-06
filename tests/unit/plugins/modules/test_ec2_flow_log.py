from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_flow_log as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class Ec2FlowLogTests(TestCase):
    def test_sdk_validation_matches_flow_log_requests(self):
        params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
        params.update(
            {
                "destination_options": None,
                "log_destination_type": None,
                "purge_tags": True,
                "resource_ids": ["vpc-1"],
                "resource_type": "VPC",
                "state": "present",
                "tags": {"Name": "main"},
                "traffic_type": None,
            }
        )
        module = Mock(params=params, client=Mock(return_value=Mock()))
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "ensure_present"),
        ):
            plugin.main()

        methods = require.call_args.args[3]
        self.assertEqual(
            methods["describe_flow_logs"],
            ("Filter", "MaxResults", "NextToken", "FlowLogIds"),
        )

        params.update(state="absent", tags=None)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "ensure_absent"),
        ):
            plugin.main()

        self.assertEqual(
            require.call_args.args[3],
            {"describe_flow_logs": ("Filter", "MaxResults", "NextToken")},
        )

    def test_absent_ignores_flow_log_disappearing_during_delete(self):
        client = Mock()
        client.delete_flow_logs.return_value = {
            "Unsuccessful": [{"Error": {"Code": "InvalidFlowLogId.NotFound"}, "ResourceId": "fl-1"}]
        }
        params = dict.fromkeys(plugin.ABSENT_MATCH_FIELDS)
        params.update({"destination_options": None, "resource_ids": ["vpc-1"]})
        module = FakeModule(params)
        with (
            patch.object(
                plugin,
                "get_flow_logs",
                return_value=[{"FlowLogId": "fl-1", "ResourceId": "vpc-1"}],
            ),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["max_aggregation_interval"]["choices"] == [
            60,
            600,
        ]
        assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]

    def test_resource_ids_are_deduplicated_in_order(self):
        module = SimpleNamespace(params={"resource_ids": ["vpc-2", "vpc-1", "vpc-2"]})
        assert plugin.normalized_resource_ids(module) == ["vpc-2", "vpc-1"]

    def test_empty_destination_options_are_ignored(self):
        module = SimpleNamespace(params={"destination_options": {"file_format": "parquet", "unused": None}})
        assert plugin.comparable_destination_options(module) == {"file_format": "parquet"}

    def test_flow_log_matching_uses_only_managed_destination_options(self):
        module = SimpleNamespace(params={"resource_ids": ["vpc-1"]})
        flow_logs = [
            {
                "FlowLogId": "fl-match",
                "ResourceId": "vpc-1",
                "LogDestinationType": "s3",
                "DestinationOptions": {
                    "FileFormat": "parquet",
                    "HiveCompatiblePartitions": True,
                },
            },
            {
                "FlowLogId": "fl-other-resource",
                "ResourceId": "vpc-2",
                "LogDestinationType": "s3",
                "DestinationOptions": {"FileFormat": "parquet"},
            },
        ]

        self.assertEqual(
            plugin.matching_flow_logs(
                module,
                flow_logs,
                {
                    "log_destination_type": "s3",
                    "destination_options": {"file_format": "parquet"},
                },
            ),
            [flow_logs[0]],
        )

    def test_flow_log_matching_rejects_missing_flow_log_id(self):
        module = FakeModule({"resource_ids": ["vpc-1"]})

        with self.assertRaises(ModuleFail) as raised:
            plugin.matching_flow_logs(
                module,
                [{"LogDestinationType": "cloud-watch-logs", "ResourceId": "vpc-1"}],
                {"log_destination_type": "cloud-watch-logs"},
            )

        self.assertIn("without a flow log ID", raised.exception.values["msg"])

    def test_flow_log_matching_rejects_invalid_flow_log(self):
        module = FakeModule({"resource_ids": ["vpc-1"]})

        with self.assertRaises(ModuleFail) as raised:
            plugin.matching_flow_logs(module, [None], {})

        self.assertIn("invalid EC2 flow log", raised.exception.values["msg"])

    def test_identical_tag_changes_are_batched_across_flow_logs(self):
        client = Mock()
        params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
        params.update(
            {
                "destination_options": None,
                "log_destination_type": None,
                "purge_tags": True,
                "resource_ids": ["vpc-1", "vpc-2"],
                "resource_type": "VPC",
                "state": "present",
                "tags": {"Environment": "prod"},
                "traffic_type": None,
            }
        )
        module = FakeModule(params)
        flow_logs = [
            {
                "FlowLogId": f"fl-{index}",
                "LogDestinationType": "cloud-watch-logs",
                "ResourceId": f"vpc-{index}",
                "Tags": [
                    {"Key": "Environment", "Value": "test"},
                    {"Key": "Remove", "Value": "yes"},
                ],
                "TrafficType": "ALL",
            }
            for index in (1, 2)
        ]
        with (
            patch.object(plugin, "get_flow_logs", return_value=flow_logs),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertTrue(raised.exception.values["changed"])
        client.delete_tags.assert_called_once_with(
            Resources=["fl-1", "fl-2"],
            Tags=[{"Key": "Remove"}],
            aws_retry=True,
        )
        client.create_tags.assert_called_once_with(
            Resources=["fl-1", "fl-2"],
            Tags=[{"Key": "Environment", "Value": "prod"}],
            aws_retry=True,
        )

    def test_invalid_resource_and_destination_combinations_are_rejected(self):
        base = {
            "destination_options": None,
            "log_destination_type": None,
            "resource_ids": ["tgw-1"],
            "resource_type": "TransitGateway",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
        cases = [
            (
                dict(base, resource_ids=[]),
                "resource_ids must contain at least one item",
            ),
            (
                dict(base, traffic_type="ALL"),
                "traffic_type is not supported when resource_type is TransitGateway or TransitGatewayAttachment",
            ),
            (
                dict(
                    base,
                    destination_options={"file_format": "parquet"},
                    log_destination_type="cloud-watch-logs",
                    resource_type="VPC",
                ),
                "destination_options requires log_destination_type to be s3 when state is present",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_partial_create_failure_is_not_reported_as_success(self):
        client = Mock()
        client.create_flow_logs.return_value = {"Unsuccessful": [{"Error": {"Code": "LimitExceeded"}}]}
        params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
        params.update(
            {
                "destination_options": None,
                "log_destination_type": None,
                "purge_tags": True,
                "resource_ids": ["vpc-1"],
                "resource_type": "VPC",
                "state": "present",
                "tags": None,
                "traffic_type": None,
            }
        )
        with (
            patch.object(plugin, "get_flow_logs", return_value=[]),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, FakeModule(params))

        self.assertIn("one or more resources", raised.exception.values["msg"])
        self.assertEqual(
            raised.exception.values["unsuccessful"][0]["error"]["code"],
            "LimitExceeded",
        )

    def test_create_rejects_invalid_flow_log_ids(self):
        client = Mock()
        client.create_flow_logs.return_value = {"FlowLogIds": [7], "Unsuccessful": []}
        params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
        params.update(
            {
                "destination_options": None,
                "log_destination_type": None,
                "purge_tags": True,
                "resource_ids": ["vpc-1"],
                "resource_type": "VPC",
                "state": "present",
                "tags": None,
                "traffic_type": None,
            }
        )
        with (
            patch.object(plugin, "get_flow_logs", return_value=[]),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, FakeModule(params))

        self.assertIn("valid created EC2 flow log IDs", raised.exception.values["msg"])
        client.describe_flow_logs.assert_not_called()

    def test_create_rejects_invalid_described_flow_log(self):
        client = Mock()
        client.create_flow_logs.return_value = {"FlowLogIds": ["fl-1"], "Unsuccessful": []}
        params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
        params.update(
            {
                "destination_options": None,
                "log_destination_type": None,
                "purge_tags": True,
                "resource_ids": ["vpc-1"],
                "resource_type": "VPC",
                "state": "present",
                "tags": None,
                "traffic_type": None,
            }
        )
        with (
            patch.object(plugin, "get_flow_logs", return_value=[]),
            patch.object(plugin, "query_list", return_value=[None]),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, FakeModule(params))

        self.assertIn("invalid created EC2 flow log", raised.exception.values["msg"])

    def test_create_result_keeps_ids_missing_from_eventually_consistent_describe(self):
        client = Mock()
        client.create_flow_logs.return_value = {
            "FlowLogIds": ["fl-created"],
            "Unsuccessful": [],
        }
        params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
        params.update(
            {
                "destination_options": None,
                "log_destination_type": None,
                "purge_tags": True,
                "resource_ids": ["vpc-1"],
                "resource_type": "VPC",
                "state": "present",
                "tags": None,
                "traffic_type": None,
            }
        )
        with (
            patch.object(plugin, "get_flow_logs", return_value=[]),
            patch.object(plugin, "query_list", return_value=[]),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, FakeModule(params))

        self.assertEqual(raised.exception.values["flow_log_ids"], ["fl-created"])
        self.assertEqual(raised.exception.values["flow_logs"], [{"flow_log_id": "fl-created"}])
