#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver
version_added: '1.9.0'
short_description: Manage AWS Route53 resolver endpoints
description:
  - Manages AWS Route53 Resolver endpoints.
  - Compares the desired endpoint settings against the current endpoint fetched by name.
  - Existing endpoints are updated in place and are deleted only with O(state=absent).
  - Changes to direction, security groups, or O(resolver_endpoint_type) to or from
    V(IPV6) fail without modifying the endpoint.
  - Changing the O(protocols) of an V(INBOUND) endpoint directly from only V(Do53)
    to only V(DoH) or only V(DoH-FIPS) fails without modifying the endpoint.
author:
  - Taylor Kimball (@tkimball83)
options:
  direction:
    description:
      - The resolver endpoint direction.
      - This is required when O(state=present).
    choices:
      - INBOUND
      - INBOUND_DELEGATION
      - OUTBOUND
    type: str
  ip_addresses:
    description:
      - The resolver endpoint IP address definitions.
      - This is required when O(state=present).
      - This must contain 2 to 20 entries.
      - New addresses are added before unwanted ones are removed. On an endpoint that already has as many addresses
        as the account's per-endpoint quota allows (6 by default), AWS therefore refuses a replacement with
        C(LimitExceededException); remove the unwanted address in a separate run first.
    elements: dict
    suboptions:
      ip:
        description:
          - The IPv4 address for the endpoint.
          - Can be supplied together with O(ip_addresses[].ipv6) for O(resolver_endpoint_type=DUALSTACK).
        type: str
      ipv6:
        description:
          - The IPv6 address for the endpoint.
          - Can be supplied together with O(ip_addresses[].ip) for O(resolver_endpoint_type=DUALSTACK).
        type: str
      subnet_id:
        description:
          - The subnet ID for the endpoint IP address.
          - This must contain 1 to 32 characters.
        required: true
        type: str
    type: list
  name:
    description:
      - The resolver endpoint name.
      - This must be a nonnumeric name of at most 64 letters, numbers, spaces,
        apostrophes, hyphens, or underscores.
    required: true
    type: str
  protocols:
    description:
      - The protocols for the resolver endpoint.
      - This must contain 1 or 2 entries.
      - When omitted while creating an endpoint, AWS uses C(Do53).
      - When omitted for an existing endpoint, the current protocols are left unchanged.
    choices:
      - Do53
      - DoH
      - DoH-FIPS
    elements: str
    type: list
  resolver_endpoint_type:
    description:
      - The resolver endpoint type.
      - When omitted while creating an endpoint, AWS uses C(IPV4).
      - When omitted for an existing endpoint, the current type is left unchanged.
    choices:
      - DUALSTACK
      - IPV4
      - IPV6
    type: str
  security_group_ids:
    description:
      - The security group IDs for the resolver endpoint.
      - This is required when O(state=present).
      - Entries must contain 1 to 64 characters.
    elements: str
    type: list
  state:
    description:
      - Whether the resolver endpoint should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  wait:
    description:
      - Whether to wait for the resolver endpoint state change to complete.
      - Even when O(wait=false), when O(state=present) the module waits for a C(DELETING) endpoint to be
        deleted before creating it again, for an endpoint that is still changing to settle before
        updating it, after an update that is followed by IP address changes, and between IP address
        changes. These waits use O(wait_delay) and are bounded by O(wait_timeout).
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true) or while the module waits even when
        O(wait=false).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - Also bounds the waits that happen even when O(wait=false).
      - Sequential waits in one run share this budget.
      - This must be 1 or greater.
    default: 300
    type: int
notes:
  - O(tags) accepts at most 200 entries; keys must contain 1 to 128 characters
    and values at most 256 characters, and both may contain only letters,
    numbers, spaces, C(_), C(.), C(:), C(/), C(=), C(+), C(-), and C(@).
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Ensure a Route53 Resolver endpoint is present
  linuxhq.aws.route53_resolver:
    direction: OUTBOUND
    ip_addresses:
      - ip: 192.168.0.125
        subnet_id: subnet-0123456789abcdef0
      - ip: 192.168.0.253
        subnet_id: subnet-0123456789abcdef1
    name: molecule
    protocols:
      - Do53
      - DoH
    security_group_ids:
      - sg-0123456789abcdef0
    tags:
      Name: molecule

- name: Ensure a Route53 Resolver endpoint is absent
  linuxhq.aws.route53_resolver:
    name: molecule
    state: absent
"""

RETURN = r"""
name:
  description:
    - The requested resolver endpoint name.
  returned: always
  type: str
resolver_endpoint:
  description:
    - The current resolver endpoint after module execution.
  returned: when state is present
  type: dict
  contains:
    arn:
      description: The endpoint ARN.
      returned: except when check mode predicts creation
      type: str
    creation_time:
      description: The time the endpoint was created.
      returned: when returned by AWS
      type: str
    creator_request_id:
      description: The unique string that identifies the request that created the endpoint.
      returned: when returned by AWS
      type: str
    direction:
      description: The endpoint direction.
      returned: always
      type: str
      sample: OUTBOUND
    dns64_enabled:
      description: Whether DNS64 is enabled for the inbound endpoint.
      returned: when returned by AWS
      type: bool
    host_vpc_id:
      description: The VPC the endpoint is in.
      returned: except when check mode predicts creation
      type: str
    id:
      description: The endpoint ID.
      returned: except when check mode predicts creation
      type: str
    ip_address_count:
      description: The number of IP addresses.
      returned: always
      type: int
    ip_addresses:
      description: The endpoint IP addresses gathered by the module.
      returned: when gathered by the module
      type: list
      elements: dict
      contains:
        creation_time:
          description: The time the IP address was created.
          returned: >-
            when read from AWS, which is skipped after a create or IP address change without waiting
            and when check mode predicts either
          type: str
        ip:
          description: The IPv4 address.
          returned: when assigned
          type: str
        ip_id:
          description: The IP address ID.
          returned: >-
            when read from AWS, which is skipped after a create or IP address change without waiting
            and when check mode predicts either
          type: str
        ipv6:
          description: The IPv6 address.
          returned: when assigned
          type: str
        modification_time:
          description: The time the IP address was last modified.
          returned: >-
            when read from AWS, which is skipped after a create or IP address change without waiting
            and when check mode predicts either
          type: str
        status:
          description: The IP address status.
          returned: >-
            when read from AWS, which is skipped after a create or IP address change without waiting
            and when check mode predicts either
          type: str
        status_message:
          description: Details about the IP address status.
          returned: >-
            when read from AWS, which is skipped after a create or IP address change without waiting
            and when check mode predicts either
          type: str
        subnet_id:
          description: The subnet ID.
          returned: always
          type: str
    ipv6_internet_access_enabled:
      description: Whether the outbound endpoint can forward queries to public IPv6 targets.
      returned: when returned by AWS
      type: bool
    modification_time:
      description: The time the endpoint was last modified.
      returned: when returned by AWS
      type: str
    name:
      description: The endpoint name.
      returned: always
      type: str
    outpost_arn:
      description: The ARN of the Outpost the endpoint is on.
      returned: when returned by AWS
      type: str
    preferred_instance_type:
      description: The EC2 instance type of the endpoint on an Outpost.
      returned: when returned by AWS
      type: str
    protocols:
      description: The endpoint protocols.
      returned: always
      type: list
      elements: str
    resolver_endpoint_type:
      description: The endpoint type.
      returned: always
      type: str
      sample: IPV4
    rni_enhanced_metrics_enabled:
      description: Whether CloudWatch metrics are published for each endpoint IP address.
      returned: when returned by AWS
      type: bool
    security_group_ids:
      description: The endpoint security group IDs.
      returned: always
      type: list
      elements: str
    status:
      description: The endpoint status.
      returned: always
      type: str
      sample: OPERATIONAL
    status_message:
      description: Details about the endpoint status.
      returned: when returned by AWS
      type: str
    tags:
      description: The endpoint tags with key case preserved.
      returned: when gathered by the module
      type: dict
    target_name_server_metrics_enabled:
      description: Whether CloudWatch metrics are published for each target name server of the outbound endpoint.
      returned: when returned by AWS
      type: bool
resolver_endpoint_id:
  description:
    - The resolver endpoint ID.
  returned: when a resolver endpoint exists after module execution
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import json
import uuid

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    comparable_ip_entry_matches,
    comparable_ip_fields,
    comparable_ips_match,
    reconcile_resolver_arn_tags,
    require_ip_versions,
    resolver_resource_with_tags,
    valid_resolver_name,
    validate_ip_addresses,
    validate_resolver_endpoint,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    require_resulting_tag_limit,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    custom_waiter,
    require_positive_wait_bounds,
    run_waiter,
    wait_deadline,
)

ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA = {
    "resolver_endpoint_operational": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverEndpoint",
        "acceptors": [
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "OPERATIONAL",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "failure",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "CREATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "UPDATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "AUTO_RECOVERING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "ACTION_NEEDED",
                "matcher": "path",
                "state": "failure",
            },
        ],
    },
    # Settled states between IP address changes; ACTION_NEEDED is repaired by replacing failed addresses.
    "resolver_endpoint_settled": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverEndpoint",
        "acceptors": [
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "OPERATIONAL",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "ACTION_NEEDED",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "failure",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "CREATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "UPDATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "AUTO_RECOVERING",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
    "resolver_endpoint_deleted": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverEndpoint",
        "acceptors": [
            {
                "expected": "ResourceNotFoundException",
                "matcher": "error",
                "state": "success",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}

IP_ADDRESS_COMPARISON_FIELDS = ("ip", "ipv6", "subnet_id")
OPTIONAL_ENDPOINT_FIELDS = ("protocols", "resolver_endpoint_type")
# AWS creation defaults for OPTIONAL_ENDPOINT_FIELDS, used only to predict check-mode results.
ENDPOINT_CREATION_DEFAULTS = {"protocols": ["Do53"], "resolver_endpoint_type": "IPV4"}
# Settings the module does not manage, which AWS returns disabled for a new endpoint of each direction.
UNMANAGED_ENDPOINT_CREATION_DEFAULTS = {
    "INBOUND": {"Dns64Enabled": False, "RniEnhancedMetricsEnabled": False},
    "INBOUND_DELEGATION": {"Dns64Enabled": False, "RniEnhancedMetricsEnabled": False},
    "OUTBOUND": {
        "Ipv6InternetAccessEnabled": False,
        "RniEnhancedMetricsEnabled": False,
        "TargetNameServerMetricsEnabled": False,
    },
}
IP_ADDRESS_REQUEST_FIELDS = ("ip", "ip_id", "ipv6", "subnet_id")
# Addresses that never became usable or lost their network interface; they are replaced.
FAILED_IP_ADDRESS_STATUSES = {
    "FAILED_CREATION",
    "FAILED_CREATION_INSUFFICIENT_EC2_CAPACITY_IN_OUTPOST",
    "FAILED_RESOURCE_GONE",
}
# Addresses already being removed; they neither satisfy nor count toward the desired addresses.
DEPARTING_IP_ADDRESS_STATUSES = {"DELETING", "DETACHING"}
# Every other status keeps the address. CREATING, ATTACHING, REMAP_ATTACHING, REMAP_DETACHING, and UPDATING
# are in progress while the endpoint is CREATING, UPDATING, or AUTO_RECOVERING, which the endpoint waiters
# wait out. UPDATE_FAILED, DELETE_FAILED_FAS_EXPIRED, and ISOLATED are not documented as unusable, so the
# address is compared as is and only disassociated again when it is no longer wanted.


def create_resolver_endpoint(client, module, desired, deadline=None):
    try:
        response = client.create_resolver_endpoint(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "creator_request_id": str(uuid.uuid4()),
                        "direction": desired["direction"],
                        "ip_addresses": desired["ip_addresses"],
                        "name": desired["name"],
                        "protocols": desired["protocols"],
                        "resolver_endpoint_type": desired["resolver_endpoint_type"],
                        "security_group_ids": desired["security_group_ids"],
                        "tags": (
                            ansible_dict_to_boto3_tag_list(module.params["tags"])
                            if module.params["tags"] is not None
                            else None
                        ),
                    },
                    capitalize_first=True,
                )
            ),
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to create AWS Route53 Resolver endpoint {desired['name']}",
        )

    endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
    if not isinstance(endpoint, dict) or not endpoint.get("Id"):
        endpoint = get_resolver_endpoint_by_name(client, module, changed=True)

    if endpoint is None:
        module.fail_json(
            changed=True,
            msg=f"AWS Route53 Resolver did not return the created endpoint {desired['name']}",
        )

    endpoint = validate_resolver_endpoint(module, endpoint, "create_resolver_endpoint", changed=True)

    if module.params["wait"]:
        resolver_endpoint_id = endpoint.get("Id")
        endpoint = wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            "operational",
            changed=True,
            deadline=deadline,
        )
    else:
        endpoint = dict(endpoint)
        endpoint["IpAddresses"] = [
            snake_dict_to_camel_dict(ip_address, capitalize_first=True) for ip_address in desired["ip_addresses"]
        ]
        if module.params["tags"] is not None:
            endpoint["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])

    return endpoint


def delete_resolver_endpoint(client, module, endpoint, deadline=None):
    resolver_endpoint_id = endpoint.get("Id")

    try:
        client.delete_resolver_endpoint(
            ResolverEndpointId=resolver_endpoint_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return False
    except is_boto3_error_code("InvalidRequestException") as e:
        # DeleteResolverEndpoint rejects endpoints that resolver rules still use with InvalidRequestException.
        module.fail_json_aws(
            e,
            msg=(
                f"Unable to delete AWS Route53 Resolver endpoint {module.params['name']}; "
                "if resolver rules still use it, delete or update those rules first"
            ),
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete AWS Route53 Resolver endpoint {module.params['name']}",
        )

    if module.params["wait"]:
        wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            "deleted",
            changed=True,
            deadline=deadline,
        )

    return True


def ensure_absent(client, module):
    deadline = wait_deadline(module)
    endpoint = get_resolver_endpoint_by_name(client, module)
    deleting = (endpoint or {}).get("Status") == "DELETING"
    changed = endpoint is not None and not deleting

    if deleting and module.params["wait"] and not module.check_mode:
        wait_for_resolver_endpoint_status(client, module, endpoint.get("Id"), "deleted", deadline=deadline)
    elif changed and not module.check_mode:
        changed = delete_resolver_endpoint(client, module, endpoint, deadline=deadline)

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module, deadline=None):
    # Re-runs after a wait pass the deadline on, so every wait in one run shares wait_timeout.
    if deadline is None:
        deadline = wait_deadline(module)

    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    desired = {
        "direction": module.params["direction"],
        "ip_addresses": module.params["ip_addresses"],
        "name": module.params["name"],
        "protocols": module.params["protocols"],
        "resolver_endpoint_type": module.params["resolver_endpoint_type"],
        "security_group_ids": module.params["security_group_ids"],
    }
    endpoint = get_resolver_endpoint_by_name(client, module)

    if endpoint is not None:
        if endpoint.get("Status") == "DELETING":
            if module.check_mode:
                endpoint = None
            else:
                wait_for_resolver_endpoint_status(client, module, endpoint.get("Id"), "deleted", deadline=deadline)
                return ensure_present(client, module, deadline=deadline)
        else:
            endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint)
            endpoint = resolver_resource_with_tags(client, module, endpoint, "endpoint")

    # Updates and IP address changes do not change tags, so later reads reuse these.
    current_tags = (endpoint or {}).get("Tags", [])

    comparable_fields = (
        "direction",
        "ip_addresses",
        "protocols",
        "resolver_endpoint_type",
        "security_group_ids",
    )
    current = comparable_endpoint(endpoint)
    created = current is None
    desired_comparable = comparable_endpoint({field: desired[field] for field in comparable_fields})
    # Omitted optional settings keep the AWS default on creation and the current value on update.
    for field in OPTIONAL_ENDPOINT_FIELDS:
        if desired[field] is None:
            desired_comparable[field] = None

    desired.update(desired_comparable)
    # Failed addresses are not compared, but the endpoint stays ACTION_NEEDED until they are replaced.
    has_failed_ip_addresses = any(
        ip_address_status(ip_address) in FAILED_IP_ADDRESS_STATUSES
        for ip_address in (endpoint or {}).get("IpAddresses") or []
    )
    changed = has_failed_ip_addresses or not comparable_endpoints_match(current, desired_comparable)
    resource_changed = changed
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        current_tag_dict = boto3_tag_list_to_ansible_dict(current_tags)
        tags_to_set, tag_keys_to_unset = compare_aws_tags(current_tag_dict, tags, purge_tags=purge_tags)
        require_resulting_tag_limit(
            module, current_tag_dict, tags_to_set, tag_keys_to_unset, 200, "AWS Route53 Resolver endpoint"
        )

    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if (
        (changed or module.params["wait"])
        and endpoint is not None
        and endpoint.get("Status")
        and endpoint.get("Status") not in ("OPERATIONAL", "ACTION_NEEDED")
    ):
        if not module.check_mode:
            wait_for_resolver_endpoint_status(client, module, endpoint.get("Id"), "settled", deadline=deadline)
            return ensure_present(client, module, deadline=deadline)

        # A real run first waits for the endpoint to settle and lists it again. By then departing addresses are
        # gone, and a conversion to IPV4 has released the IPv6 addresses.
        ip_addresses = endpoint.get("IpAddresses") or []
        settled_ip_addresses = [
            ip_address_without_ipv6(ip_address) if endpoint.get("ResolverEndpointType") == "IPV4" else ip_address
            for ip_address in ip_addresses
            if ip_address_status(ip_address) not in DEPARTING_IP_ADDRESS_STATUSES
        ]
        endpoint = dict(endpoint, IpAddresses=settled_ip_addresses, Status="OPERATIONAL")
        if isinstance(endpoint.get("IpAddressCount"), int):
            # The count includes departing addresses until they are removed.
            endpoint["IpAddressCount"] -= len(ip_addresses) - len(settled_ip_addresses)

    if current is not None:
        immutable_changes = [
            field for field in ("direction", "security_group_ids") if current[field] != desired_comparable[field]
        ]
        desired_type = desired_comparable["resolver_endpoint_type"]
        if (
            desired_type is not None
            and desired_type != current["resolver_endpoint_type"]
            and "IPV6"
            in (
                desired_type,
                current["resolver_endpoint_type"],
            )
        ):
            # UpdateResolverEndpoint only converts between IPV4 and DUALSTACK.
            immutable_changes.append("resolver_endpoint_type to or from IPV6")

        if immutable_changes:
            module.fail_json(
                msg=(
                    "Cannot update AWS Route53 Resolver endpoint "
                    f"{module.params['name']} in place: {', '.join(immutable_changes)} cannot be changed. "
                    "The existing endpoint has not been modified."
                ),
            )

        if (
            current["direction"] == "INBOUND"
            and current["protocols"] == ["Do53"]
            and desired_comparable["protocols"] in (["DoH"], ["DoH-FIPS"])
        ):
            # UpdateResolverEndpoint rejects this switch to avoid disrupting inbound Do53 traffic.
            module.fail_json(
                msg=(
                    "Cannot update AWS Route53 Resolver endpoint "
                    f"{module.params['name']} protocols directly from Do53 to "
                    f"{desired_comparable['protocols'][0]} on an INBOUND endpoint. "
                    "Add the new protocol alongside Do53 first, then remove Do53. "
                    "The existing endpoint has not been modified."
                ),
            )

    if changed and module.check_mode:
        # Removing failed addresses is an address change too; without a wait it returns the requested addresses.
        keep_ip_addresses = (
            current is not None
            and comparable_ips_match(current["ip_addresses"], desired_comparable["ip_addresses"])
            and (module.params["wait"] or not has_failed_ip_addresses)
        )
        if current is None:
            projected_desired = dict(desired)
            for field in OPTIONAL_ENDPOINT_FIELDS:
                if projected_desired[field] is None:
                    projected_desired[field] = ENDPOINT_CREATION_DEFAULTS[field]

            # CreateResolverEndpoint returns a CREATING endpoint that counts every requested address; a waited
            # create returns it once OPERATIONAL.
            projected_desired["ip_address_count"] = len(desired["ip_addresses"])
            projected_desired["status"] = "OPERATIONAL" if module.params["wait"] else "CREATING"
        else:
            # Only fields an update changes replace the AWS values; direction and security groups already match.
            projected_desired = {
                field: desired[field]
                for field in OPTIONAL_ENDPOINT_FIELDS
                if desired[field] is not None and current[field] != desired[field]
            }
            if not keep_ip_addresses:
                projected_desired["ip_addresses"] = desired["ip_addresses"]

            # A waited run re-reads the endpoint after replacing its addresses.
            if module.params["wait"] and (has_failed_ip_addresses or not keep_ip_addresses):
                projected_desired["ip_address_count"] = len(desired["ip_addresses"])

            # Without a wait, an update that no address change follows returns the UpdateResolverEndpoint response.
            if (
                not module.params["wait"]
                and keep_ip_addresses
                and any(field in projected_desired for field in OPTIONAL_ENDPOINT_FIELDS)
            ):
                projected_desired["status"] = "UPDATING"

            # Without a wait, address changes return the last change's response: UPDATING, counting an added address
            # at once and a removed one until it is gone. The response after removing a failed address is unproven.
            if not module.params["wait"] and not keep_ip_addresses:
                listed_ip_addresses = endpoint.get("IpAddresses") or []
                if projected_desired.get("resolver_endpoint_type") == "DUALSTACK":
                    listed_ip_addresses = ip_addresses_with_requested_ipv6(endpoint, desired["ip_addresses"])

                changes = ip_address_changes(listed_ip_addresses, desired["ip_addresses"])
                last_operation, last_ip_address = changes[-1] if changes else (None, None)
                if last_operation == "add" or (
                    last_operation == "remove" and ip_address_status(last_ip_address) not in FAILED_IP_ADDRESS_STATUSES
                ):
                    projected_desired["ip_address_count"] = len(desired["ip_addresses"]) + (
                        1 if last_operation == "remove" else 0
                    )
                    projected_desired["status"] = "UPDATING"

        endpoint = dict(endpoint or {})
        if current is None:
            # botocore drops response members its model lacks, so predict only those a real run returns.
            modeled_fields = client.meta.service_model.shape_for("ResolverEndpoint").members
            endpoint.update(
                {
                    field: value
                    for field, value in UNMANAGED_ENDPOINT_CREATION_DEFAULTS.get(desired["direction"], {}).items()
                    if field in modeled_fields
                }
            )

        endpoint.update(snake_dict_to_camel_dict(projected_desired, capitalize_first=True))
        if keep_ip_addresses:
            # Failed addresses would be removed; a waited conversion to IPV4 lists them without IPv6 addresses.
            release_ipv6 = module.params["wait"] and projected_desired.get("resolver_endpoint_type") == "IPV4"
            endpoint["IpAddresses"] = [
                ip_address_without_ipv6(ip_address) if release_ipv6 else ip_address
                for ip_address in endpoint.get("IpAddresses") or []
                if ip_address_status(ip_address) not in FAILED_IP_ADDRESS_STATUSES
            ]

        # A waited create lists the new endpoint's tags.
        if tags is not None or (current is None and module.params["wait"]):
            endpoint = apply_tag_deltas(endpoint, tags_to_set, tag_keys_to_unset)
    elif current is None:
        endpoint = create_resolver_endpoint(client, module, desired, deadline=deadline)
        if module.params["wait"]:
            endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint, changed=True)
            endpoint = resolver_resource_with_tags(client, module, endpoint, "endpoint", changed=True)
    elif changed:
        if resource_changed:
            changed_optional_fields = [
                field
                for field in OPTIONAL_ENDPOINT_FIELDS
                if desired_comparable[field] is not None and current[field] != desired_comparable[field]
            ]
            if changed_optional_fields:
                update_params = {"resolver_endpoint_id": endpoint.get("Id")}
                for field in changed_optional_fields:
                    update_params[field] = desired[field]

                request = snake_dict_to_camel_dict(update_params, capitalize_first=True)
                if (
                    "resolver_endpoint_type" in changed_optional_fields
                    and desired["resolver_endpoint_type"] == "DUALSTACK"
                ):
                    update_ip_addresses = dual_stack_ip_addresses(endpoint, desired["ip_addresses"])
                    if update_ip_addresses:
                        request["UpdateIpAddresses"] = update_ip_addresses

                try:
                    response = client.update_resolver_endpoint(**request, aws_retry=True)
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=f"Unable to update AWS Route53 Resolver endpoint {module.params['name']}",
                    )

                endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
                if not isinstance(endpoint, dict) or not endpoint.get("Id"):
                    endpoint = get_resolver_endpoint(
                        client, module, update_params["resolver_endpoint_id"], changed=True
                    )

                if endpoint is None:
                    module.fail_json(
                        changed=True,
                        msg=f"AWS Route53 Resolver did not return the updated endpoint {module.params['name']}",
                    )

                endpoint = validate_resolver_endpoint(
                    module,
                    endpoint,
                    "update_resolver_endpoint",
                    expected_id=update_params["resolver_endpoint_id"],
                    changed=True,
                )

                ip_addresses_changed = has_failed_ip_addresses or not comparable_ips_match(
                    current["ip_addresses"], desired_comparable["ip_addresses"]
                )
                if module.params["wait"] or ip_addresses_changed:
                    # Address changes follow, and they repair an endpoint that needs action.
                    endpoint = wait_for_resolver_endpoint_status(
                        client,
                        module,
                        endpoint.get("Id"),
                        "settled" if ip_addresses_changed else "operational",
                        changed=True,
                        deadline=deadline,
                    )

                # The endpoint can be deleted elsewhere while waiting; the comparison below then fails.
                if endpoint is not None:
                    endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint, changed=True)
                    endpoint = reconcile_resolver_endpoint_ip_addresses(
                        client,
                        module,
                        endpoint,
                        desired,
                        changed=True,
                        deadline=deadline,
                    )
            else:
                endpoint = reconcile_resolver_endpoint_ip_addresses(
                    client,
                    module,
                    endpoint,
                    desired,
                    deadline=deadline,
                )

            current = comparable_endpoint(endpoint)

            if not comparable_endpoints_match(current, desired_comparable):
                module.fail_json(
                    msg=(
                        "AWS Route53 Resolver endpoint "
                        f"{module.params['name']} does not match the requested configuration after updating. "
                        "The endpoint has not been deleted; inspect the current configuration before retrying."
                    ),
                    changed=True,
                    current=current,
                    desired=desired_comparable,
                )

        if tags is not None:
            if "Tags" not in endpoint:
                endpoint = dict(endpoint, Tags=current_tags)

            reconcile_resolver_arn_tags(
                module,
                client,
                endpoint,
                "endpoint",
                module.params["name"],
                tags_to_set,
                tag_keys_to_unset,
                changed=resource_changed,
            )

            endpoint = apply_tag_deltas(endpoint, tags_to_set, tag_keys_to_unset)

    if (
        module.params["wait"]
        and not module.check_mode
        and endpoint is not None
        and endpoint.get("Status") == "ACTION_NEEDED"
    ):
        module.fail_json(
            changed=changed,
            msg=(
                f"AWS Route53 Resolver endpoint {module.params['name']} needs action: "
                f"{endpoint.get('StatusMessage') or 'no status message was returned'}"
            ),
            resolver_endpoint=boto3_resource_to_ansible_dict(endpoint, transform_tags=True, force_tags=False),
        )

    if endpoint is not None and "Tags" not in endpoint and tags is None and not created:
        endpoint = dict(endpoint, Tags=current_tags)

    result_endpoint = boto3_resource_to_ansible_dict(endpoint, transform_tags=True, force_tags=False)
    result = {
        "changed": changed,
        "name": desired["name"],
        "resolver_endpoint": result_endpoint,
        "state": "present",
    }
    resolver_endpoint_id = result_endpoint.get("id")

    if resolver_endpoint_id is not None:
        result["resolver_endpoint_id"] = resolver_endpoint_id

    module.exit_json(**result)


def ip_address_changes(listed_ip_addresses, desired_ip_addresses):
    """Return the ordered ("add" | "remove", address) changes that turn the listed addresses into the desired ones."""
    failed_ip_addresses = [
        ip_address for ip_address in listed_ip_addresses if ip_address_status(ip_address) in FAILED_IP_ADDRESS_STATUSES
    ]
    current_ip_addresses = usable_ip_addresses(listed_ip_addresses)

    remaining = list(current_ip_addresses)
    ip_addresses_to_add = []
    # Reserve explicit addresses before matching subnet-only requests.
    for ip_address in sorted(desired_ip_addresses, key=lambda item: len(comparable_ip_address(item)), reverse=True):
        desired_comparable = comparable_ip_address(ip_address)
        match = next(
            (
                index
                for index, current_ip_address in enumerate(remaining)
                if comparable_ip_entry_matches(comparable_ip_address(current_ip_address), desired_comparable)
            ),
            None,
        )
        if match is None:
            ip_addresses_to_add.append(ip_address)
        else:
            remaining.pop(match)

    # Replace failed addresses as well as unwanted ones; additions run first so the endpoint keeps capacity.
    ip_addresses_to_remove = failed_ip_addresses + remaining

    changes = []
    address_count = len(current_ip_addresses) + len(failed_ip_addresses)
    while ip_addresses_to_add or ip_addresses_to_remove:
        if ip_addresses_to_add and (address_count < 20 or not ip_addresses_to_remove):
            changes.append(("add", ip_addresses_to_add.pop(0)))
            address_count += 1
        else:
            changes.append(("remove", ip_addresses_to_remove.pop(0)))
            address_count -= 1

    return changes


def reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired, changed=False, deadline=None):
    """Replace endpoint IP addresses; changed reports whether the endpoint was already modified."""
    resolver_endpoint_id = endpoint.get("Id")
    desired_ip_addresses = desired["ip_addresses"]
    changes = ip_address_changes(endpoint.get("IpAddresses") or [], desired_ip_addresses)
    if not changes:
        return endpoint

    for index, (operation, ip_address) in enumerate(changes):
        if operation == "remove":
            normalized_ip_address = boto3_resource_to_ansible_dict(ip_address, transform_tags=False, force_tags=False)
            ip_address = {
                field: normalized_ip_address.get(field)
                for field in IP_ADDRESS_REQUEST_FIELDS
                if normalized_ip_address.get(field) is not None
            }

        try:
            request_ip_address = snake_dict_to_camel_dict(ip_address, capitalize_first=True)
            if operation == "add":
                operation_name = "associate_resolver_endpoint_ip_address"
                response = client.associate_resolver_endpoint_ip_address(
                    IpAddress=request_ip_address,
                    ResolverEndpointId=resolver_endpoint_id,
                    aws_retry=True,
                )
            else:
                operation_name = "disassociate_resolver_endpoint_ip_address"
                response = client.disassociate_resolver_endpoint_ip_address(
                    IpAddress=request_ip_address,
                    ResolverEndpointId=resolver_endpoint_id,
                    aws_retry=True,
                )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                changed=changed or index > 0,
                msg=f"Unable to reconcile AWS Route53 Resolver endpoint IP addresses for {desired['name']}",
            )

        if index < len(changes) - 1:
            # An endpoint that still has a failed address stays ACTION_NEEDED until it is removed.
            wait_for_resolver_endpoint_status(
                client, module, resolver_endpoint_id, "settled", changed=True, deadline=deadline
            )
        elif module.params["wait"]:
            endpoint = wait_for_resolver_endpoint_status(
                client, module, resolver_endpoint_id, "operational", changed=True, deadline=deadline
            )
        else:
            # Without a wait, the last change's response is the current endpoint, which is UPDATING and still counts
            # an address it removes.
            changed_endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
            if isinstance(changed_endpoint, dict) and changed_endpoint.get("Id"):
                endpoint = validate_resolver_endpoint(
                    module, changed_endpoint, operation_name, expected_id=resolver_endpoint_id, changed=True
                )

    if not module.params["wait"]:
        endpoint = dict(endpoint)
        endpoint["IpAddresses"] = [
            snake_dict_to_camel_dict(ip_address, capitalize_first=True) for ip_address in desired_ip_addresses
        ]
        return endpoint

    return resolver_endpoint_with_ip_addresses(client, module, endpoint, changed=True)


def wait_for_resolver_endpoint_status(client, module, resolver_endpoint_id, state, changed=False, deadline=None):
    """Wait for an endpoint status; changed reports whether the endpoint was already modified.

    deadline limits the wait to what is left of the run's shared wait_timeout budget.
    """
    # The waiter fails on terminal states as well as on timeouts, so the message names neither.
    error_msg = f"Unable to wait for AWS Route53 Resolver endpoint {module.params['name']} to become {state}"

    run_waiter(
        module,
        custom_waiter(client, ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA, f"resolver_endpoint_{state}"),
        error_msg,
        changed=changed,
        deadline=deadline,
        ResolverEndpointId=resolver_endpoint_id,
    )

    if state == "deleted":
        return None

    return get_resolver_endpoint(client, module, resolver_endpoint_id, changed=changed)


def comparable_endpoint(endpoint):
    if not endpoint:
        return None

    normalized = boto3_resource_to_ansible_dict(endpoint, transform_tags=False, force_tags=False)
    return {
        "direction": normalized.get("direction"),
        "ip_addresses": comparable_ip_addresses(usable_ip_addresses(normalized.get("ip_addresses"))),
        "protocols": sorted(set(normalized.get("protocols") or [])),
        "resolver_endpoint_type": normalized.get("resolver_endpoint_type"),
        "security_group_ids": sorted(set(normalized.get("security_group_ids") or [])),
    }


def dual_stack_ip_addresses(endpoint, desired_ip_addresses):
    # Pair each existing address with the requested IPv6 address in the same entry.
    requests = []
    for ip_address in usable_ip_addresses(endpoint.get("IpAddresses")):
        current = comparable_ip_address(ip_address)
        for desired in desired_ip_addresses:
            if (
                ip_address.get("IpId")
                and desired.get("ipv6")
                and desired.get("ip")
                and desired["ip"] == current.get("ip")
            ):
                requests.append({"IpId": ip_address["IpId"], "Ipv6": desired["ipv6"]})
                break

    return requests


def ip_addresses_with_requested_ipv6(endpoint, desired_ip_addresses):
    """Return the listed addresses with the IPv6 addresses that a conversion to DUALSTACK requests for them."""
    requested_ipv6 = {
        request["IpId"]: request["Ipv6"] for request in dual_stack_ip_addresses(endpoint, desired_ip_addresses)
    }
    return [
        (
            dict(ip_address, Ipv6=requested_ipv6[ip_address["IpId"]])
            if ip_address.get("IpId") in requested_ipv6
            else ip_address
        )
        for ip_address in endpoint.get("IpAddresses") or []
    ]


def ip_address_status(ip_address):
    return ip_address.get("Status") or ip_address.get("status")


def ip_address_without_ipv6(ip_address):
    return {field: value for field, value in ip_address.items() if field != "Ipv6"}


def usable_ip_addresses(ip_addresses):
    excluded = FAILED_IP_ADDRESS_STATUSES | DEPARTING_IP_ADDRESS_STATUSES
    return [ip_address for ip_address in ip_addresses or [] if ip_address_status(ip_address) not in excluded]


def comparable_ip_address(ip_address):
    return comparable_ip_fields(ip_address, IP_ADDRESS_COMPARISON_FIELDS)


def comparable_ip_addresses(ip_addresses):
    return sorted(
        [comparable_ip_address(ip_address) for ip_address in ip_addresses or []],
        key=lambda item: json.dumps(item, sort_keys=True),
    )


def comparable_endpoints_match(current, desired):
    if current is None:
        return False

    if any(
        desired[field] is not None and current[field] != desired[field]
        for field in (
            "direction",
            "protocols",
            "resolver_endpoint_type",
            "security_group_ids",
        )
    ):
        return False

    return comparable_ips_match(current["ip_addresses"], desired["ip_addresses"])


def get_resolver_endpoint(client, module, resolver_endpoint_id, changed=False):
    try:
        response = client.get_resolver_endpoint(
            ResolverEndpointId=resolver_endpoint_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            changed=changed,
            msg=f"Unable to get AWS Route53 Resolver endpoint {resolver_endpoint_id}",
        )

    endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
    return validate_resolver_endpoint(
        module,
        endpoint,
        "get_resolver_endpoint",
        expected_id=resolver_endpoint_id,
        changed=changed,
    )


def get_resolver_endpoint_by_name(client, module, changed=False):
    """Find the endpoint by name; changed reports whether the endpoint was already modified, for failure results."""
    name = module.params["name"]

    endpoints = query_list(
        module,
        client,
        "list_resolver_endpoints",
        "ResolverEndpoints",
        "Unable to list AWS Route53 Resolver endpoints",
        changed=changed,
        Filters=ansible_dict_to_boto3_filter_list({"Name": name}),
    )

    endpoints = [
        validate_resolver_endpoint(module, endpoint, "list_resolver_endpoints", expected_name=name, changed=changed)
        for endpoint in endpoints
    ]

    if len(endpoints) > 1:
        endpoint_ids = sorted(endpoint["Id"] for endpoint in endpoints)
        module.fail_json(
            changed=changed, msg=f"Multiple AWS Route53 Resolver endpoints are named {name}: {', '.join(endpoint_ids)}"
        )

    return endpoints[0] if endpoints else None


def resolver_endpoint_with_ip_addresses(client, module, endpoint, changed=False):
    """Add listed IP addresses; changed reports whether the endpoint was already modified, for failure results."""
    if not endpoint:
        return endpoint

    endpoint = dict(endpoint)

    ip_addresses = query_list(
        module,
        client,
        "list_resolver_endpoint_ip_addresses",
        "IpAddresses",
        f"Unable to list AWS Route53 Resolver endpoint IP addresses for {endpoint['Id']}",
        changed=changed,
        ResolverEndpointId=endpoint["Id"],
    )
    endpoint["IpAddresses"] = validate_ip_addresses(module, ip_addresses, changed=changed)

    return endpoint


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "direction": {
                "choices": ["INBOUND", "INBOUND_DELEGATION", "OUTBOUND"],
                "type": "str",
            },
            "ip_addresses": {
                "elements": "dict",
                "options": {
                    "ip": {"type": "str"},
                    "ipv6": {"type": "str"},
                    "subnet_id": {"required": True, "type": "str"},
                },
                "type": "list",
            },
            "name": {"required": True, "type": "str"},
            "protocols": {
                "choices": ["Do53", "DoH", "DoH-FIPS"],
                "elements": "str",
                "type": "list",
            },
            "purge_tags": {"default": True, "type": "bool"},
            "resolver_endpoint_type": {
                "choices": ["DUALSTACK", "IPV4", "IPV6"],
                "type": "str",
            },
            "security_group_ids": {
                "elements": "str",
                "type": "list",
            },
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "tags": {"aliases": ["resource_tags"], "type": "dict"},
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 5, "type": "int"},
            "wait_timeout": {"default": 300, "type": "int"},
        },
        required_if=[
            ("state", "present", ["direction", "ip_addresses", "security_group_ids"]),
        ],
        supports_check_mode=True,
    )
    state = module.params["state"]
    tags = module.params["tags"]

    name = module.params["name"]
    if not valid_resolver_name(name):
        module.fail_json(msg="name must be a valid resolver endpoint name of at most 64 characters")

    if state == "present":
        if not 2 <= len(module.params["ip_addresses"] or []) <= 20:
            module.fail_json(msg="ip_addresses must contain 2 to 20 entries")

        # Several subnet-only entries may request addresses in the same subnet.
        comparable_ip_address_values = comparable_ip_addresses(
            entry for entry in module.params["ip_addresses"] if entry.get("ip") or entry.get("ipv6")
        )
        if len({json.dumps(item, sort_keys=True) for item in comparable_ip_address_values}) != len(
            comparable_ip_address_values
        ):
            module.fail_json(msg="ip_addresses entries must be unique")

        if module.params["protocols"] is not None and not 1 <= len(set(module.params["protocols"])) <= 2:
            module.fail_json(msg="protocols must contain 1 or 2 entries")

        if not module.params["security_group_ids"]:
            module.fail_json(msg="security_group_ids must contain at least one entry")

        if any(not 1 <= len(group_id) <= 64 for group_id in module.params["security_group_ids"]):
            module.fail_json(msg="security_group_ids entries must contain 1 to 64 characters")

        for entry in module.params["ip_addresses"]:
            if (
                entry.get("ip") is not None
                and entry.get("ipv6") is not None
                and module.params["resolver_endpoint_type"] not in (None, "DUALSTACK")
            ):
                module.fail_json(
                    msg="ip_addresses entries with both ip and ipv6 require resolver_endpoint_type=DUALSTACK"
                )

            if not 1 <= len(entry["subnet_id"]) <= 32:
                module.fail_json(msg="ip_addresses[].subnet_id must contain 1 to 32 characters")

            require_ip_versions(module, entry, "ip_addresses")

        require_valid_tags(module, tags, 200, restricted_characters=True)

    require_positive_wait_bounds(module, always=state == "present")

    client = module.client("route53resolver", retry_decorator=AWSRetry.jittered_backoff())
    method_names = {"list_resolver_endpoints"}
    if state == "present":
        method_names.update(
            {
                "associate_resolver_endpoint_ip_address",
                "create_resolver_endpoint",
                "disassociate_resolver_endpoint_ip_address",
                "get_resolver_endpoint",
                "list_resolver_endpoint_ip_addresses",
                "list_tags_for_resource",
                "update_resolver_endpoint",
            }
        )
        if tags:
            method_names.add("tag_resource")

        if tags is not None and module.params["purge_tags"]:
            method_names.add("untag_resource")

    if state == "absent":
        method_names.add("delete_resolver_endpoint")
        if module.params["wait"]:
            method_names.add("get_resolver_endpoint")

    required_method_parameters = {
        "associate_resolver_endpoint_ip_address": {
            "IpAddress",
            "ResolverEndpointId",
        },
        "create_resolver_endpoint": {
            "CreatorRequestId",
            "Direction",
            "IpAddresses",
            "Name",
            "Protocols",
            "ResolverEndpointType",
            "SecurityGroupIds",
            "Tags",
        },
        "delete_resolver_endpoint": {"ResolverEndpointId"},
        "disassociate_resolver_endpoint_ip_address": {
            "IpAddress",
            "ResolverEndpointId",
        },
        "get_resolver_endpoint": {"ResolverEndpointId"},
        "list_resolver_endpoint_ip_addresses": {
            "MaxResults",
            "NextToken",
            "ResolverEndpointId",
        },
        "list_resolver_endpoints": {"Filters", "MaxResults", "NextToken"},
        "list_tags_for_resource": {"MaxResults", "NextToken", "ResourceArn"},
        "tag_resource": {"ResourceArn", "Tags"},
        "untag_resource": {"ResourceArn", "TagKeys"},
        "update_resolver_endpoint": {
            "Protocols",
            "ResolverEndpointId",
            "ResolverEndpointType",
        },
    }
    if tags is None:
        required_method_parameters["create_resolver_endpoint"].discard("Tags")

    if module.params["resolver_endpoint_type"] == "DUALSTACK":
        required_method_parameters["update_resolver_endpoint"].add("UpdateIpAddresses")

    require_client_methods(
        module,
        client,
        "Route53 Resolver",
        {name: required_method_parameters[name] for name in method_names},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
