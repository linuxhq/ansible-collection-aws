# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import route53_resolver as route53_resolver_utils
from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    AWS_OWNED_RULE_OWNER,
    comparable_ip_fields,
    comparable_ips_match,
    comparable_ips_matches,
    require_ip_versions,
    resolver_resource_with_tags,
    response_items,
    valid_resolver_name,
    validate_ip_addresses,
    validate_resolver_endpoint,
    validate_resolver_rule,
    validate_tags,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


def test_response_items_returns_listed_items_or_empty():
    assert response_items(FakeModule({}), {"Tags": [{"Key": "a", "Value": "b"}]}, "Tags", "list_tags") == [
        {"Key": "a", "Value": "b"}
    ]
    assert response_items(FakeModule({}), {}, "Tags", "list_tags") == []


@pytest.mark.parametrize(
    "response, message",
    [
        ([], "list_tags: AWS returned an invalid response"),
        ({"Tags": {}}, "list_tags: AWS returned an invalid Tags value"),
    ],
)
def test_response_items_rejects_malformed_responses(response, message):
    with pytest.raises(ModuleFail) as raised:
        response_items(FakeModule({}), response, "Tags", "list_tags")

    assert raised.value.values["msg"] == message


def test_validate_ip_addresses_returns_valid_addresses():
    ip_addresses = [{"Ip": "192.0.2.1", "IpId": "rni-1", "Ipv6": "2001:db8::1", "SubnetId": "subnet-1"}]

    assert validate_ip_addresses(FakeModule({}), ip_addresses) is ip_addresses


@pytest.mark.parametrize(
    "ip_address, message",
    [
        ("192.0.2.1", "list_resolver_endpoint_ip_addresses: AWS returned an invalid IP address"),
        ({"Ip": "192.0.2.1"}, "list_resolver_endpoint_ip_addresses: AWS returned an IP address without a subnet ID"),
        ({"SubnetId": ""}, "list_resolver_endpoint_ip_addresses: AWS returned an IP address without a subnet ID"),
        ({"SubnetId": "subnet-1", "IpId": 1}, "list_resolver_endpoint_ip_addresses: AWS returned an invalid IpId"),
    ],
)
def test_validate_ip_addresses_rejects_malformed_addresses(ip_address, message):
    with pytest.raises(ModuleFail) as raised:
        validate_ip_addresses(FakeModule({}), [ip_address])

    assert raised.value.values["msg"] == message


def test_validate_tags_uses_the_list_tags_message():
    tags = [{"Key": "Name", "Value": "example"}]
    assert validate_tags(FakeModule({}), tags) is tags

    with pytest.raises(ModuleFail) as raised:
        validate_tags(FakeModule({}), [{"Key": "Name"}])

    assert raised.value.values["msg"] == "list_tags_for_resource: AWS returned an invalid tag"
    assert raised.value.values["changed"] is False


@pytest.mark.parametrize("changed", [False, True])
def test_listing_validation_reports_earlier_changes(changed):
    with pytest.raises(ModuleFail) as raised:
        validate_tags(FakeModule({}), [{"Key": "Name"}], changed=changed)

    assert raised.value.values["changed"] is changed

    with pytest.raises(ModuleFail) as raised:
        validate_ip_addresses(FakeModule({}), ["192.0.2.1"], changed=changed)

    assert raised.value.values["changed"] is changed


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


def test_resolver_resource_with_tags_skips_resources_without_an_arn():
    with patch.object(route53_resolver_utils, "query_list") as query:
        assert resolver_resource_with_tags(Mock(), FakeModule({}), {"Id": "rslvr-1"}, "rule") == {"Id": "rslvr-1"}
        assert resolver_resource_with_tags(Mock(), FakeModule({}), None, "rule") is None

    query.assert_not_called()


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


@pytest.mark.parametrize(
    "endpoint, message",
    [
        ("endpoint", "list_resolver_endpoints: AWS returned an invalid resolver endpoint"),
        ({"Id": ""}, "list_resolver_endpoints: AWS returned a resolver endpoint without a valid ID"),
        ({"Arn": 1, "Id": "rslvr-1"}, "list_resolver_endpoints: AWS returned an invalid resolver endpoint Arn"),
    ],
)
def test_validate_resolver_endpoint_rejects_malformed_endpoints(endpoint, message):
    with pytest.raises(ModuleFail) as raised:
        validate_resolver_endpoint(FakeModule({}), endpoint, "list_resolver_endpoints", changed=True)

    assert raised.value.values == {"changed": True, "msg": message}


def test_comparable_ips_matches_reports_each_desired_entry_match():
    current = [{"ip": "192.0.2.1", "port": 53}, {"ip": "192.0.2.2", "port": 53}]
    desired = [{"ip": "192.0.2.2"}, {"ip": "192.0.2.9"}, {"ip": "192.0.2.1", "port": 53}]
    assert comparable_ips_matches(current, desired) == [1, None, 0]
