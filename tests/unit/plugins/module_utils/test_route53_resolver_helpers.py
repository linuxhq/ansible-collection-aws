# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import route53_resolver as route53_resolver_utils
from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    AWS_OWNED_RULE_OWNER,
    comparable_ip_entry_matches,
    comparable_ip_fields,
    comparable_ips_match,
    comparable_ips_matches,
    reconcile_resolver_arn_tags,
    require_ip_versions,
    resolver_resource_with_tags,
    valid_resolver_name,
    validate_resolver_endpoint,
    validate_resolver_rule,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


@pytest.mark.parametrize(
    "item, fields, expected",
    [
        (
            {"Ip": "192.0.2.1", "IpId": "rni-1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            ("ip", "ipv6", "subnet_id"),
            {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
        ),
        (
            {"ipv6": "2001:0DB8:0000:0000:0000:0000:0000:0010", "subnet_id": "subnet-1"},
            ("ip", "ipv6", "subnet_id"),
            {"ipv6": "2001:db8::10", "subnet_id": "subnet-1"},
        ),
        (
            {"Ip": "not-an-ip", "Port": 53, "Protocol": None},
            ("ip", "ipv6", "port", "protocol"),
            {"ip": "not-an-ip", "port": 53},
        ),
    ],
)
def test_comparable_ip_fields_normalizes_addresses_and_drops_unset_fields(item, fields, expected):
    assert comparable_ip_fields(item, fields) == expected


@pytest.mark.parametrize(
    "entry",
    [
        {"ip": "192.0.2.1"},
        {"ipv6": "2001:db8::1"},
        {"ip": "192.0.2.1", "ipv6": "2001:db8::1"},
        {"ip": None, "ipv6": None},
    ],
)
def test_require_ip_versions_accepts_matching_versions(entry):
    require_ip_versions(FakeModule({}), entry, "target_ips")


@pytest.mark.parametrize(
    "entry, message",
    [
        ({"ip": "2001:db8::1"}, "target_ips[].ip must be a valid IPv4 address"),
        ({"ipv6": "192.0.2.1"}, "target_ips[].ipv6 must be a valid IPv6 address"),
        ({"ip": "not-an-ip"}, "target_ips[].ip must be a valid IPv4 address"),
    ],
)
def test_require_ip_versions_rejects_wrong_versions(entry, message):
    with pytest.raises(ModuleFail) as raised:
        require_ip_versions(FakeModule({}), entry, "target_ips")

    assert raised.value.values["msg"] == message


@pytest.mark.parametrize(
    "name, valid",
    [
        ("main", True),
        ("it's a-name_1", True),
        ("a" * 64, True),
        ("a" * 65, False),
        ("12345", False),
        ("bad.name", False),
        ("", False),
    ],
)
def test_valid_resolver_name(name, valid):
    assert valid_resolver_name(name) is valid


@pytest.mark.parametrize(
    "current, desired, expected",
    [
        ([{"subnet_id": "a"}, {"subnet_id": "a"}], [{"subnet_id": "a"}, {"subnet_id": "a"}], True),
        ([{"ip": "192.0.2.1", "subnet_id": "a"}], [{"subnet_id": "a"}], True),
        ([{"ip": "192.0.2.1", "subnet_id": "a"}, {"ip": "192.0.2.2", "subnet_id": "a"}], [{"subnet_id": "a"}], False),
        ([{"ip": "192.0.2.1", "port": 53}], [{"ip": "192.0.2.1", "port": 5353}], False),
        # The explicit entry is matched first so the broader one takes the remaining address.
        (
            [{"ip": "192.0.2.1", "subnet_id": "a"}, {"ip": "192.0.2.2", "subnet_id": "a"}],
            [{"subnet_id": "a"}, {"ip": "192.0.2.1", "subnet_id": "a"}],
            True,
        ),
    ],
)
def test_comparable_ips_match_pairs_each_entry_once(current, desired, expected):
    assert comparable_ips_match(current, desired) is expected


def test_comparable_ips_matches_finds_a_pairing_greedy_matching_misses():
    current = [
        {"ip": "1.1.1.1", "port": 443, "protocol": "DoH", "server_name_indication": "a"},
        {"ip": "1.1.1.1", "port": 443, "protocol": "DoH", "server_name_indication": "b"},
    ]
    desired = [{"ip": "1.1.1.1", "protocol": "DoH"}, {"ip": "1.1.1.1", "server_name_indication": "a"}]
    assert comparable_ips_matches(current, desired) == [1, 0]
    assert comparable_ips_match(current, desired) is True


def test_comparable_ips_matches_moves_an_earlier_entry_to_free_a_target():
    current = [{"ip": "192.0.2.1", "subnet_id": "a"}, {"ip": "192.0.2.2", "subnet_id": "a"}]
    desired = [{"subnet_id": "a"}, {"ip": "192.0.2.1"}]
    assert comparable_ips_matches(current, desired) == [1, 0]
    assert comparable_ips_match(current, desired) is True


def test_comparable_ips_matches_keeps_endpoint_subnet_pairing():
    current = [{"ip": "10.0.0.5", "subnet_id": "a"}, {"ip": "10.0.1.5", "subnet_id": "b"}]
    desired = [{"subnet_id": "b"}, {"subnet_id": "a"}]
    assert comparable_ips_matches(current, desired) == [1, 0]
    assert comparable_ips_match(current, desired) is True
    assert comparable_ips_match(current, [{"subnet_id": "a"}, {"subnet_id": "a"}]) is False


@pytest.mark.parametrize("resource_type", ["endpoint", "rule"])
def test_resolver_resource_with_tags_adds_tags_and_keeps_the_message(resource_type):
    def failing_query(module, client, method_name, result_key, error_msg, changed=False, **kwargs):
        module.fail_json(changed=changed, msg=error_msg)

    resource = {"Arn": "arn:resource", "Id": "rslvr-1"}
    with patch.object(route53_resolver_utils, "query_list", return_value=[{"Key": "Name", "Value": "main"}]):
        tagged = resolver_resource_with_tags(Mock(), FakeModule({}), resource, resource_type)

    assert tagged == dict(resource, Tags=[{"Key": "Name", "Value": "main"}])
    assert "Tags" not in resource

    with (
        patch.object(route53_resolver_utils, "query_list", side_effect=failing_query),
        pytest.raises(ModuleFail) as raised,
    ):
        resolver_resource_with_tags(Mock(), FakeModule({}), resource, resource_type, changed=True)

    assert raised.value.values == {
        "changed": True,
        "msg": f"Unable to list tags for AWS Route53 Resolver {resource_type} arn:resource",
    }


def test_resolver_resource_with_tags_skips_a_missing_resource():
    with patch.object(route53_resolver_utils, "query_list") as query:
        assert resolver_resource_with_tags(Mock(), FakeModule({}), None, "rule") is None

    query.assert_not_called()


def test_resolver_resource_with_tags_lists_tags_by_arn():
    with patch.object(route53_resolver_utils, "query_list", return_value=[{"Key": "a", "Value": "b"}]) as query:
        resource = resolver_resource_with_tags(Mock(), FakeModule({}), {"Arn": "arn:rule", "Id": "rslvr-1"}, "rule")

    assert resource == {"Arn": "arn:rule", "Id": "rslvr-1", "Tags": [{"Key": "a", "Value": "b"}]}
    assert query.call_args.kwargs["ResourceArn"] == "arn:rule"


def test_validate_resolver_rule_accepts_the_aws_owned_rule():
    rule = {
        "Arn": "arn:aws:route53resolver:us-east-1::autodefined-rule/rslvr-autodefined-rr-internet-resolver",
        "DomainName": ".",
        "Id": "rslvr-autodefined-rr-internet-resolver",
        "Name": "Internet Resolver",
        "OwnerId": AWS_OWNED_RULE_OWNER,
        "RuleType": "RECURSIVE",
        "Status": "COMPLETE",
    }

    assert validate_resolver_rule(FakeModule({}), rule, "list_resolver_rules") is rule


def test_comparable_ips_matches_reports_each_desired_entry_match():
    current = [{"ip": "192.0.2.1", "port": 53}, {"ip": "192.0.2.2", "port": 53}]
    desired = [{"ip": "192.0.2.2"}, {"ip": "192.0.2.9"}, {"ip": "192.0.2.1", "port": 53}]
    assert comparable_ips_matches(current, desired) == [1, None, 0]


def test_comparable_ip_entry_matches_requires_every_desired_field():
    current = {"ip": "192.0.2.1", "port": 53, "subnet_id": "subnet-1"}
    assert comparable_ip_entry_matches(current, {"subnet_id": "subnet-1"})
    assert comparable_ip_entry_matches(current, {})
    assert not comparable_ip_entry_matches(current, {"ip": "192.0.2.1", "port": 54})
    assert not comparable_ip_entry_matches(current, {"ipv6": "2001:db8::1"})


def test_comparable_ip_entry_matches_treats_an_empty_desired_value_as_absent():
    current = {"ip": "192.0.2.1", "port": 53}
    assert comparable_ip_entry_matches(current, {"ip": "192.0.2.1", "server_name_indication": ""})
    assert comparable_ip_entry_matches(dict(current, server_name_indication=""), {"server_name_indication": ""})
    assert not comparable_ip_entry_matches(
        dict(current, server_name_indication="dns.example.com"), {"server_name_indication": ""}
    )


def test_reconcile_resolver_arn_tags_skips_empty_deltas():
    with patch.object(route53_resolver_utils, "reconcile_arn_tags") as reconcile:
        reconcile_resolver_arn_tags(FakeModule({}), Mock(), {}, "rule", {}, [])

    reconcile.assert_not_called()


def test_reconcile_resolver_arn_tags_reconciles_by_arn():
    module = FakeModule({})
    client = Mock()
    with patch.object(route53_resolver_utils, "reconcile_arn_tags") as reconcile:
        reconcile_resolver_arn_tags(
            module, client, {"Arn": "arn:rule"}, "rule", {"new": "value"}, ["old"], changed=True
        )

    reconcile.assert_called_once_with(
        module, client, "arn:rule", {"new": "value"}, ["old"], "AWS Route53 Resolver rule", changed=True
    )


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (
            {"expected_id": "rslvr-in-2"},
            "get_resolver_endpoint: AWS returned an unexpected resolver endpoint ID rslvr-in-1",
        ),
        ({"expected_name": "other"}, "get_resolver_endpoint: AWS returned an unexpected resolver endpoint name"),
    ],
)
def test_validate_resolver_endpoint_rejects_another_endpoint(kwargs, message):
    endpoint = {"Id": "rslvr-in-1", "Name": "main"}
    assert (
        validate_resolver_endpoint(FakeModule({}), endpoint, "get_resolver_endpoint", expected_id="rslvr-in-1")
        is endpoint
    )

    with pytest.raises(ModuleFail) as raised:
        validate_resolver_endpoint(FakeModule({}), endpoint, "get_resolver_endpoint", changed=True, **kwargs)

    assert raised.value.values == {"changed": True, "msg": message}


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"expected_id": "rslvr-rr-2"}, "get_resolver_rule: AWS returned an unexpected resolver rule ID rslvr-rr-1"),
        ({"expected_name": "other"}, "get_resolver_rule: AWS returned an unexpected resolver rule name"),
    ],
)
def test_validate_resolver_rule_rejects_another_rule(kwargs, message):
    with pytest.raises(ModuleFail) as raised:
        validate_resolver_rule(FakeModule({}), {"Id": "rslvr-rr-1", "Name": "main"}, "get_resolver_rule", **kwargs)

    assert raised.value.values == {"changed": False, "msg": message}
