# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import ipaddress
import re

from ansible_collections.amazon.aws.plugins.module_utils.transformation import boto3_resource_to_ansible_dict

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import query_list
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list

# The OwnerId of rules that Route 53 Resolver creates, such as the Internet Resolver rule.
AWS_OWNED_RULE_OWNER = "Route 53 Resolver"


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


def comparable_ips_match(current, desired):
    """Pair each desired entry with a current one whose fields match; omitted fields keep AWS values."""
    remaining = list(current)
    # Match the most specific entries first so they are not taken by broader ones.
    for desired_entry in sorted(desired, key=len, reverse=True):
        match = next(
            (
                index
                for index, current_entry in enumerate(remaining)
                if all(current_entry.get(field) == value for field, value in desired_entry.items())
            ),
            None,
        )
        if match is None:
            return False

        remaining.pop(match)

    return not remaining


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


def resolver_resource_with_tags(client, module, resource, resource_type, changed=False):
    """Add listed tags; changed reports whether the resource was already modified, for failure results."""
    if not resource or not resource.get("Arn"):
        return resource

    resource = dict(resource)

    tags = query_list(
        module,
        client,
        "list_tags_for_resource",
        "Tags",
        f"Unable to list tags for AWS Route53 Resolver {resource_type} {resource['Arn']}",
        changed=changed,
        ResourceArn=resource["Arn"],
    )
    resource["Tags"] = validate_tags(module, tags, changed=changed)

    return resource


def resolver_rule_has_details(rule):
    return isinstance(rule, dict) and all(
        field in rule for field in ("DomainName", "ResolverEndpointId", "RuleType", "TargetIps")
    )


def response_items(module, response, key, operation):
    if not isinstance(response, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid response")

    items = response.get(key, [])
    if not isinstance(items, list):
        module.fail_json(msg=f"{operation}: AWS returned an invalid {key} value")

    return items


def validate_ip_addresses(module, ip_addresses, changed=False):
    """Validate listed IP addresses; changed reports whether the endpoint was already modified, for failure results."""
    for ip_address in ip_addresses:
        if not isinstance(ip_address, dict):
            module.fail_json(
                changed=changed, msg="list_resolver_endpoint_ip_addresses: AWS returned an invalid IP address"
            )

        if not isinstance(ip_address.get("SubnetId"), str) or not ip_address["SubnetId"]:
            module.fail_json(
                changed=changed,
                msg="list_resolver_endpoint_ip_addresses: AWS returned an IP address without a subnet ID",
            )

        for field in ("Ip", "IpId", "Ipv6"):
            if field in ip_address and not isinstance(ip_address[field], str):
                module.fail_json(
                    changed=changed, msg=f"list_resolver_endpoint_ip_addresses: AWS returned an invalid {field}"
                )

    return ip_addresses


def validate_tags(module, tags, changed=False):
    """Validate listed tags; changed reports whether the resource was already modified, for failure results."""
    return require_valid_tag_list(module, tags, "list_tags_for_resource: AWS returned an invalid tag", changed=changed)


def validate_resolver_endpoint(module, endpoint, operation, expected_id=None, expected_name=None, changed=False):
    if not isinstance(endpoint, dict):
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid resolver endpoint")

    endpoint_id = endpoint.get("Id")
    if not isinstance(endpoint_id, str) or not endpoint_id:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned a resolver endpoint without a valid ID")

    if expected_id is not None and endpoint_id != expected_id:
        module.fail_json(
            changed=changed, msg=f"{operation}: AWS returned an unexpected resolver endpoint ID {endpoint_id}"
        )

    if expected_name is not None and endpoint.get("Name") != expected_name:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an unexpected resolver endpoint name")

    for field in ("Arn", "Name", "Status"):
        if field in endpoint and not isinstance(endpoint[field], str):
            module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid resolver endpoint {field}")

    return endpoint


def validate_resolver_rule(
    module,
    rule,
    operation,
    expected_id=None,
    expected_name=None,
    require_details=False,
    changed=False,
):
    if not isinstance(rule, dict):
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid resolver rule")

    rule_id = rule.get("Id")
    if not isinstance(rule_id, str) or not rule_id:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned a resolver rule without a valid ID")

    if expected_id is not None and rule_id != expected_id:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an unexpected resolver rule ID {rule_id}")

    if expected_name is not None and rule.get("Name") != expected_name:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an unexpected resolver rule name")

    for field in ("Arn", "DomainName", "Name", "ResolverEndpointId", "RuleType", "Status"):
        if field in rule and not isinstance(rule[field], str):
            module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid resolver rule {field}")

    if require_details and not resolver_rule_has_details(rule):
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an incomplete resolver rule")

    if "TargetIps" in rule:
        validate_target_ips(module, rule["TargetIps"], operation, changed=changed)

    return rule


def validate_target_ips(module, target_ips, operation, changed=False):
    if not isinstance(target_ips, list):
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid resolver rule TargetIps")

    for target_ip in target_ips:
        if not isinstance(target_ip, dict):
            module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid target IP")

        if not any(isinstance(target_ip.get(field), str) and target_ip[field] for field in ("Ip", "Ipv6")):
            module.fail_json(changed=changed, msg=f"{operation}: AWS returned a target IP without an IP address")

        for field in ("Ip", "Ipv6", "Protocol", "ServerNameIndication"):
            if field in target_ip and not isinstance(target_ip[field], str):
                module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid target IP {field}")

        if "Port" in target_ip and (not isinstance(target_ip["Port"], int) or isinstance(target_ip["Port"], bool)):
            module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid target IP Port")

    return target_ips
