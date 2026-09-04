from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ssm_association as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class SsmAssociationTests(TestCase):
    def test_absent_tolerates_association_disappearing_during_delete(self):
        client = Mock()
        client.delete_association.side_effect = plugin.ClientError(
            {"Error": {"Code": "AssociationDoesNotExist", "Message": "gone"}},
            "DeleteAssociation",
        )
        module = FakeModule({"name": "document"})
        with self.assertRaises(ModuleExit) as raised:
            plugin.ensure_absent(client, module, {"AssociationId": "association-1"})
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_if"] == [("state", "present", ["schedule_expression", "targets"])]

    def test_targets_apply_defaults_and_ignore_order(self):
        left = [
            {"key": "tag:Role", "values": ["web", "api", "web"]},
            {"key": "InstanceIds", "values": ["i-2", "i-1"]},
            {"key": "InstanceIds", "values": ["i-1", "i-2"]},
        ]
        normalized = plugin.comparable_targets(left)
        assert normalized == plugin.comparable_targets(reversed(left))
        assert normalized[1]["values"] == ["api", "web"]

    def test_check_mode_predicts_new_association_without_api_call(self):
        client = Mock()
        module = FakeModule(
            {
                "name": "document",
                "purge_tags": True,
                "schedule_expression": "rate(1 hour)",
                "tags": {"Env": "test"},
                "targets": [{"key": "InstanceIds", "values": ["i-1"]}],
            },
            check_mode=True,
        )
        with self.assertRaises(ModuleExit) as raised:
            plugin.ensure_present(client, module, None)

        client.create_association.assert_not_called()
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["association"]["schedule_expression"],
            "rate(1 hour)",
        )

    def test_create_uses_known_tags_without_eventual_lookup(self):
        client = Mock()
        client.create_association.return_value = {
            "AssociationDescription": {
                "AssociationId": "association-1",
                "Name": "document",
            }
        }
        module = FakeModule(
            {
                "name": "document",
                "purge_tags": True,
                "schedule_expression": "rate(1 hour)",
                "tags": {"Env": "test"},
                "targets": [{"key": "InstanceIds", "values": ["i-1"]}],
            }
        )

        with self.assertRaises(ModuleExit):
            plugin.ensure_present(client, module, None)

        client.list_tags_for_resource.assert_not_called()
        client.add_tags_to_resource.assert_not_called()

    def test_existing_association_updates_schedule_and_sorted_targets(self):
        client = Mock()
        updated = {
            "AssociationId": "association-1",
            "Name": "document",
            "ScheduleExpression": "rate(2 hours)",
            "Targets": [{"Key": "InstanceIds", "Values": ["i-1", "i-2"]}],
        }
        client.update_association.return_value = {"AssociationDescription": updated}
        module = FakeModule(
            {
                "name": "document",
                "purge_tags": True,
                "schedule_expression": "rate(2 hours)",
                "tags": None,
                "targets": [{"key": "InstanceIds", "values": ["i-2", "i-1"]}],
            }
        )
        current = {
            "AssociationId": "association-1",
            "DocumentVersion": "$LATEST",
            "Name": "document",
            "Parameters": {"Mode": ["safe"]},
            "ScheduleExpression": "rate(1 hour)",
            "Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
        }
        with (
            patch.object(
                plugin,
                "get_boto3_client_method_parameters",
                return_value=(
                    "AssociationId",
                    "DocumentVersion",
                    "Name",
                    "Parameters",
                    "ScheduleExpression",
                    "Targets",
                ),
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module, current)
        self.assertTrue(raised.exception.values["changed"])
        client.update_association.assert_called_once_with(
            AssociationId="association-1",
            DocumentVersion="$LATEST",
            Name="document",
            Parameters={"Mode": ["safe"]},
            ScheduleExpression="rate(2 hours)",
            Targets=[{"Key": "InstanceIds", "Values": ["i-1", "i-2"]}],
            aws_retry=True,
        )

    def test_describe_missing_association_returns_none(self):
        client = Mock()
        error = plugin.ClientError(
            {"Error": {"Code": "AssociationDoesNotExist", "Message": "gone"}},
            "DescribeAssociation",
        )
        client.describe_association.side_effect = error

        self.assertIsNone(plugin.describe_association(client, FakeModule({}), "a-1"))

    def test_describe_rejects_malformed_response(self):
        client = Mock(describe_association=Mock(return_value={"AssociationDescription": None}))
        with self.assertRaises(ModuleFail) as raised:
            plugin.describe_association(client, FakeModule({}), "a-1")
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while describing AWS Systems Manager association a-1",
        )

    def test_create_rejects_malformed_response(self):
        client = Mock(create_association=Mock(return_value={"AssociationDescription": None}))
        module = FakeModule(
            {
                "name": "document",
                "purge_tags": True,
                "schedule_expression": "rate(1 hour)",
                "tags": None,
                "targets": [{"key": "InstanceIds", "values": ["i-1"]}],
            }
        )
        with self.assertRaises(ModuleFail) as raised:
            plugin.ensure_present(client, module, None)
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager did not return the created association document",
        )

    def test_association_tags_rejects_malformed_response(self):
        client = Mock(list_tags_for_resource=Mock(return_value={"TagList": [None]}))
        with self.assertRaises(ModuleFail) as raised:
            plugin.association_with_tags(
                client,
                FakeModule({}),
                {"AssociationId": "a-1"},
            )
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while listing tags for AWS Systems Manager association a-1",
        )

    def test_update_rejects_malformed_response(self):
        client = Mock(update_association=Mock(return_value={"AssociationDescription": None}))
        module = FakeModule(
            {
                "name": "document",
                "purge_tags": True,
                "schedule_expression": "rate(2 hours)",
                "tags": None,
                "targets": [{"key": "InstanceIds", "values": ["i-1"]}],
            }
        )
        current = {
            "AssociationId": "a-1",
            "Name": "document",
            "ScheduleExpression": "rate(1 hour)",
            "Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
        }
        with (
            patch.object(
                plugin,
                "get_boto3_client_method_parameters",
                return_value=("AssociationId", "Name", "ScheduleExpression", "Targets"),
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module, current)
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager did not return the updated association document",
        )

    def test_main_rejects_malformed_association_summaries(self):
        for association in (None, {"Name": "document"}):
            with self.subTest(association=association):
                module = FakeModule(
                    {
                        "name": "document",
                        "state": "absent",
                        "tags": None,
                    },
                    client=Mock(),
                )
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    patch.object(plugin, "require_client_methods"),
                    patch.object(plugin, "query_list", return_value=[association]),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    plugin.main()
                self.assertEqual(
                    raised.exception.values["msg"],
                    "Unexpected response while listing AWS Systems Manager associations for document",
                )

    def test_provider_limits_are_rejected(self):
        base = {"name": "document", "state": "present", "tags": None}
        cases = [
            (
                dict(base, schedule_expression="", targets=[]),
                "schedule_expression must be 1 to 256 characters",
            ),
            (
                dict(
                    base,
                    schedule_expression="rate(1 hour)",
                    targets=[{"key": f"tag:Role{index}", "values": ["web"]} for index in range(6)],
                ),
                "targets must contain at most 5 targets",
            ),
            (
                dict(
                    base,
                    schedule_expression="rate(1 hour)",
                    targets=[{"key": "", "values": ["web"]}],
                ),
                "targets[].key must be 1 to 163 characters",
            ),
            (
                dict(
                    base,
                    schedule_expression="rate(1 hour)",
                    targets=[
                        {
                            "key": "tag:Role",
                            "values": [f"role-{index}" for index in range(51)],
                        }
                    ],
                ),
                "targets[].values must contain at most 50 entries",
            ),
            (
                dict(
                    base,
                    schedule_expression="rate(1 hour)",
                    targets=[{"key": "tag:Role", "values": []}],
                ),
                "targets[].values must contain at least one entry",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)
