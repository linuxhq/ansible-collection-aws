# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import ipaddress

from ansible_collections.amazon.aws.plugins.module_utils.transformation import boto3_resource_to_ansible_dict

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import query_list

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


def resolver_resource_with_tags(client, module, resource, resource_type, changed=False):
    """Add listed tags; changed reports whether the resource was already modified, for failure results."""
    if not resource:
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
