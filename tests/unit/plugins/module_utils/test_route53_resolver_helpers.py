# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    comparable_ip_fields,
    require_ip_versions,
    response_items,
    valid_resolver_name,
    validate_ip_addresses,
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
