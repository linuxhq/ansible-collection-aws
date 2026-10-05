# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import ipaddress
import re

from ansible_collections.amazon.aws.plugins.module_utils.transformation import boto3_resource_to_ansible_dict

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def comparable_ip_fields(item, fields):
    """Return the set fields of an AWS or module IP entry, with IP addresses in canonical form."""
    normalized = boto3_resource_to_ansible_dict(item, transform_tags=False, force_tags=False)
    for field in ("ip", "ipv6"):
        if normalized.get(field) is not None:
            try:
                normalized[field] = str(ipaddress.ip_address(normalized[field]))
            except ValueError:
                pass

    return {field: normalized[field] for field in fields if normalized.get(field) is not None}


def require_ip_versions(module, entry, option):
    for field, version in (("ip", 4), ("ipv6", 6)):
        value = entry.get(field)
        if value is None:
            continue

        try:
            valid = ipaddress.ip_address(value).version == version
        except ValueError:
            valid = False

        if not valid:
            module.fail_json(msg=f"{option}[].{field} must be a valid IPv{version} address")


def valid_resolver_name(name):
    return len(name) <= 64 and not name.isdigit() and re.fullmatch(r"[a-zA-Z0-9\-_ ']+", name) is not None


def response_items(module, response, key, operation):
    if not isinstance(response, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid response")

    items = response.get(key, [])
    if not isinstance(items, list):
        module.fail_json(msg=f"{operation}: AWS returned an invalid {key} value")

    return items


def validate_ip_addresses(module, ip_addresses):
    for ip_address in ip_addresses:
        if not isinstance(ip_address, dict):
            module.fail_json(msg="list_resolver_endpoint_ip_addresses: AWS returned an invalid IP address")

        if not isinstance(ip_address.get("SubnetId"), str) or not ip_address["SubnetId"]:
            module.fail_json(msg="list_resolver_endpoint_ip_addresses: AWS returned an IP address without a subnet ID")

        for field in ("Ip", "IpId", "Ipv6"):
            if field in ip_address and not isinstance(ip_address[field], str):
                module.fail_json(msg=f"list_resolver_endpoint_ip_addresses: AWS returned an invalid {field}")

    return ip_addresses


def validate_tags(module, tags):
    return require_valid_tag_list(module, tags, "list_tags_for_resource: AWS returned an invalid tag")
