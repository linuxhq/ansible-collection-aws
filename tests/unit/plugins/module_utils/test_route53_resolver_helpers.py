# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    response_items,
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
