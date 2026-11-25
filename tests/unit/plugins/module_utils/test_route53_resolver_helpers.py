# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import route53_resolver as route53_resolver_utils
from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    comparable_ip_entry_matches,
    comparable_ip_fields,
    comparable_ips_match,
    comparable_ips_matches,
    resolver_resource_with_tags,
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
    with patch.object(route53_resolver_utils, "query_list", return_value=[{"Key": "Name", "Value": "main"}]) as query:
        tagged = resolver_resource_with_tags(Mock(), FakeModule({}), resource, resource_type)

    assert tagged == dict(resource, Tags=[{"Key": "Name", "Value": "main"}])
    assert query.call_args.kwargs["ResourceArn"] == "arn:resource"
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
