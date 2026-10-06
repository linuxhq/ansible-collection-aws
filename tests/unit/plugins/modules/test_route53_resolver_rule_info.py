from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_malformed_rule_is_rejected_before_detail_queries():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"Arn": "arn:rule"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "without a valid ID" in raised.value.values["msg"]


def test_malformed_association_is_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", side_effect=[[{"Id": "rule-1"}], [{"VPCId": "vpc-1"}]]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "without a rule ID" in raised.value.values["msg"]


def test_malformed_tag_response_and_entry_are_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    cases = [([], "invalid response"), ({"Tags": [{"Key": "Name"}]}, "invalid tag")]
    for response, message in cases:
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", side_effect=[[{"Arn": "arn:rule", "Id": "rule-1"}], []]),
            patch.object(plugin, "paginated_query_with_retries", return_value=response),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert message in raised.value.values["msg"]


def test_empty_unfiltered_rules_skip_association_query():
    module = FakeModule({"filters": None}, client=Mock())
    query = Mock(return_value=[])
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", query),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_count == 1


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["filters"]["type"] == "dict"


def test_paginated_methods_are_required():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    # With no rules, only the listing call is checked.
    require.assert_called_once()
    assert require.call_args.args[3] == {"list_resolver_rules": ("Filters", "MaxResults", "NextToken")}


def test_empty_filtered_rules_skip_association_query():
    module = FakeModule({"filters": {"name": ["missing"]}}, client=Mock())
    query = Mock(return_value=[])
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", query),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert query.call_count == 1
    assert raised.value.values["resolver_rules"] == []


def test_associations_are_grouped_by_rule_and_expose_vpc_ids():
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
                    {"ResolverRuleId": "rule-1", "Status": "COMPLETE", "VPCId": "vpc-1"},
                    {"ResolverRuleId": "rule-1", "Status": "FAILED", "VPCId": "vpc-3"},
                    {"ResolverRuleId": "rule-2", "Status": "OVERRIDDEN", "VPCId": "vpc-2"},
                    {"ResolverRuleId": "rule-2", "Status": "DELETING", "VPCId": "vpc-4"},
                ],
            ],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"Tags": [{"Key": "Name", "Value": "main"}]},
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    rules = raised.value.values["resolver_rules"]
    # Failed and deleting associations stay in associations but not in vpc_ids.
    assert len(rules[0]["associations"]) == 2
    assert rules[0]["vpc_ids"] == ["vpc-1"]
    assert rules[0]["tags"] == {"Name": "main"}
    assert rules[1]["vpc_ids"] == ["vpc-2"]


def test_detail_methods_are_checked_only_when_rules_exist():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", side_effect=[[{"Id": "rule-1"}], []]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert [sorted(call.args[3]) for call in require.call_args_list] == [
        ["list_resolver_rules"],
        ["list_resolver_rule_associations", "list_tags_for_resource"],
    ]


def test_aws_owned_rule_skips_the_tag_lookup():
    module = FakeModule({"filters": None}, client=Mock())
    rule = {
        "Arn": "arn:aws:route53resolver:us-east-1::autodefined-rule/rslvr-autodefined-rr-internet-resolver",
        "DomainName": ".",
        "Id": "rslvr-autodefined-rr-internet-resolver",
        "OwnerId": "Route 53 Resolver",
        "RuleType": "RECURSIVE",
    }
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", side_effect=[[rule], []]),
        patch.object(plugin, "paginated_query_with_retries") as list_tags,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    list_tags.assert_not_called()
    assert raised.value.values["resolver_rules"][0]["tags"] == {}


def test_invalid_tag_request_fails():
    module = FakeModule({"filters": None}, client=Mock())
    error = ClientError(
        {"Error": {"Code": "InvalidRequestException", "Message": "invalid"}},
        "ListTagsForResource",
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", side_effect=[[{"Arn": "arn:rule", "Id": "rule-1"}], []]),
        patch.object(plugin, "paginated_query_with_retries", side_effect=error),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Unable to list tags for AWS Route53 Resolver rule arn:rule"


def test_rule_with_malformed_target_ips_is_rejected():
    module = FakeModule({"filters": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"Id": "rule-1", "TargetIps": [{"Port": 53}]}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "list_resolver_rules: AWS returned a target IP without an IP address"
