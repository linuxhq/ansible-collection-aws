from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class Route53ResolverRuleInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["filters"]["type"] == "dict"

    def test_paginated_methods_are_required(self):
        module = FakeModule({"filters": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3],
            {
                "list_resolver_rules": ("Filters", "MaxResults", "NextToken"),
                "list_resolver_rule_associations": (
                    "Filters",
                    "MaxResults",
                    "NextToken",
                ),
                "list_tags_for_resource": (
                    "MaxResults",
                    "NextToken",
                    "ResourceArn",
                ),
            },
        )

    def test_empty_filtered_rules_skip_association_query(self):
        module = FakeModule({"filters": {"name": ["missing"]}}, client=Mock())
        query = Mock(return_value=[])
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", query),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(query.call_count, 1)
        self.assertEqual(raised.exception.values["resolver_rules"], [])

    def test_associations_are_grouped_by_rule_and_expose_vpc_ids(self):
        module = FakeModule({"filters": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                side_effect=[
                    [
                        {"Arn": "arn:rule-1", "Id": "rule-1"},
                        {"Id": "rule-2"},
                    ],
                    [
                        {"ResolverRuleId": "rule-1", "VPCId": "vpc-1"},
                        {"ResolverRuleId": "rule-2", "VPCId": "vpc-2"},
                    ],
                ],
            ),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"Tags": [{"Key": "Name", "Value": "main"}]},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        rules = raised.exception.values["resolver_rules"]
        self.assertEqual(rules[0]["vpc_ids"], ["vpc-1"])
        self.assertEqual(rules[0]["tags"], {"Name": "main"})
        self.assertEqual(rules[1]["vpc_ids"], ["vpc-2"])
