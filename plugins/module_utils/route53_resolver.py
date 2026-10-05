# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


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
