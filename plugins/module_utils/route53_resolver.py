# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import ipaddress
import re

from ansible_collections.amazon.aws.plugins.module_utils.transformation import boto3_resource_to_ansible_dict

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import query_list
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import reconcile_arn_tags

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


def comparable_ip_entry_matches(current, desired):
    """Return whether a comparable current entry has every field a comparable desired entry sets.

    AWS omits empty strings, so an empty desired value matches an absent current one.
    """
    return all(
        current.get(field) == value or (value == "" and field not in current) for field, value in desired.items()
    )


def comparable_ips_match(current, desired):
    """Pair each desired entry with a current one whose fields match; omitted fields keep AWS values."""
    return len(current) == len(desired) and None not in comparable_ips_matches(current, desired)


def comparable_ips_matches(current, desired):
    """Return, for each desired entry, the index of the current entry it matches, or None.

    Pairs entries with a maximum bipartite matching (Kuhn's algorithm), so a broad desired entry
    cannot take the only current entry a more specific one could match while another was free.
    """
    compatible = [
        [
            current_index
            for current_index in range(len(current))
            if comparable_ip_entry_matches(current[current_index], entry)
        ]
        for entry in desired
    ]
    owners = [None] * len(current)

    def augment(desired_index, visited):
        for current_index in compatible[desired_index]:
            if current_index in visited:
                continue

            visited.add(current_index)
            if owners[current_index] is None or augment(owners[current_index], visited):
                owners[current_index] = desired_index
                return True

        return False

    # Try the most specific entries first; a matched entry stays matched as later ones augment.
    for desired_index in sorted(range(len(desired)), key=lambda index: len(desired[index]), reverse=True):
        augment(desired_index, set())

    matches = [None] * len(desired)
    for current_index, desired_index in enumerate(owners):
        if desired_index is not None:
            matches[desired_index] = current_index

    return matches


def reconcile_resolver_arn_tags(module, client, resource, label, tags_to_set, tag_keys_to_unset, changed=False):
    """Reconcile a resolver resource's tags by ARN; changed reports whether it was already modified."""
    if not tags_to_set and not tag_keys_to_unset:
        return

    reconcile_arn_tags(
        module,
        client,
        resource["Arn"],
        tags_to_set,
        tag_keys_to_unset,
        f"AWS Route53 Resolver {label}",
        changed=changed,
    )


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
    resource["Tags"] = query_list(
        module,
        client,
        "list_tags_for_resource",
        "Tags",
        f"Unable to list tags for AWS Route53 Resolver {resource_type} {resource['Arn']}",
        changed=changed,
        ResourceArn=resource["Arn"],
    )

    return resource


def validate_resolver_endpoint(module, endpoint, operation, expected_id=None, expected_name=None, changed=False):
    """Fail when AWS returns a different resolver endpoint than the one requested."""
    if expected_id is not None and endpoint["Id"] != expected_id:
        module.fail_json(
            changed=changed, msg=f"{operation}: AWS returned an unexpected resolver endpoint ID {endpoint['Id']}"
        )

    if expected_name is not None and endpoint.get("Name") != expected_name:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an unexpected resolver endpoint name")

    return endpoint


def validate_resolver_rule(module, rule, operation, expected_id=None, expected_name=None, changed=False):
    """Fail when AWS returns a different resolver rule than the one requested."""
    if expected_id is not None and rule["Id"] != expected_id:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an unexpected resolver rule ID {rule['Id']}")

    if expected_name is not None and rule.get("Name") != expected_name:
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an unexpected resolver rule name")

    return rule
