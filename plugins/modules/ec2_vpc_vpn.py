#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_vpn
version_added: "2.3.0"
short_description: Manage EC2 Site-to-Site VPN connections and tunnel options
description:
  - Creates, updates, and deletes a VPN connection selected by name, ID, or filters.
  - Updates only supplied attributes, including tunnel encryption and connection CIDRs.
  - Tunnel changes are applied sequentially and can temporarily interrupt connectivity.
  - Gateway IDs, routing mode, and tunnel address family cannot be changed on an existing connection.
author:
  - Taylor Kimball (@tkimball83)
options:
  connection_type:
    description: The VPN connection type.
    type: str
    choices: [ipsec.1]
    default: ipsec.1
  customer_gateway_id:
    description: The customer gateway ID. Required to create a connection.
    type: str
  filters:
    description:
      - EC2 filter names mapped to strings or lists of strings. Must uniquely identify a connection.
      - Uses native EC2 names such as C(tag:Name). A missing match cannot create a connection.
      - Supply one of O(name), O(vpn_connection_id), or O(filters).
      - Mutually exclusive with O(name) and O(vpn_connection_id).
    type: dict
  local_ipv4_network_cidr:
    description: The IPv4 CIDR on the customer gateway side. AWS defaults to C(0.0.0.0/0).
    type: str
  local_ipv6_network_cidr:
    description: The IPv6 CIDR on the customer gateway side. AWS defaults to C(::/0).
    type: str
  name:
    description:
      - The Name tag identifying the connection. Required when creating a connection.
      - Supply one of O(name), O(vpn_connection_id), or O(filters).
      - Mutually exclusive with O(vpn_connection_id) and O(filters).
    type: str
  purge_routes:
    description: Remove routes not included in O(routes), when O(routes) is supplied.
    type: bool
    default: true
  remote_ipv4_network_cidr:
    description: The IPv4 CIDR on the AWS side. AWS defaults to C(0.0.0.0/0).
    type: str
  remote_ipv6_network_cidr:
    description: The IPv6 CIDR on the AWS side. AWS defaults to C(::/0).
    type: str
  routes:
    description:
      - Static IPv4 route destinations. Requires static routing on a virtual private gateway connection.
      - Omitted routes are unchanged. An empty list removes routes when O(purge_routes=true).
      - Waits for requested routes to become available and removed routes to disappear, except in check mode.
    type: list
    elements: str
  state:
    description: The desired connection state.
    type: str
    choices: [present, absent]
    default: present
  static_only:
    description:
      - Whether to use static routing. Defaults to false on creation and is preserved when omitted during updates.
    type: bool
  transit_gateway_id:
    description:
      - The transit gateway ID. Required for creation unless O(vpn_gateway_id) is supplied.
      - Mutually exclusive with O(vpn_gateway_id).
    type: str
  tunnel_inside_ip_version:
    description:
      - The tunnel address family. AWS defaults to IPv4 on creation.
      - IPv6 requires O(transit_gateway_id) when creating a connection.
    type: str
    choices: [ipv4, ipv6]
  tunnel_options:
    description:
      - Up to two tunnel configurations. Omitted fields retain their current values or AWS defaults.
      - A single entry without O(tunnel_options[].outside_ip_address) applies shared settings to both tunnels.
      - Two entries use list order during creation and numeric outside IP order during updates unless explicitly selected.
      - Do not mix entries with and without O(tunnel_options[].outside_ip_address) in the same update.
      - Inside CIDRs must be distinct; provide two entries at creation or select a specific tunnel for CIDR updates.
      - An empty list leaves tunnels unchanged.
    type: list
    elements: dict
    suboptions:
      ike_versions:
        description: The permitted IKE versions. Order is ignored.
        type: list
        elements: str
        choices: [ikev1, ikev2]
      outside_ip_address:
        description: Optional outside IP selecting one existing tunnel. Cannot be supplied during creation.
        type: str
      phase1_dh_group_numbers:
        description: The permitted phase 1 Diffie-Hellman groups. Order is ignored.
        type: list
        elements: int
        choices: [2, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
      phase1_encryption_algorithms:
        description: The permitted phase 1 encryption algorithms. Order is ignored.
        type: list
        elements: str
        choices: [AES128, AES256, AES128-GCM-16, AES256-GCM-16]
      phase1_integrity_algorithms:
        description: The permitted phase 1 integrity algorithms. Order is ignored.
        type: list
        elements: str
        choices: [SHA1, SHA2-256, SHA2-384, SHA2-512]
      phase2_dh_group_numbers:
        description: The permitted phase 2 Diffie-Hellman groups. Order is ignored.
        type: list
        elements: int
        choices: [2, 5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
      phase2_encryption_algorithms:
        description: The permitted phase 2 encryption algorithms. Order is ignored.
        type: list
        elements: str
        choices: [AES128, AES256, AES128-GCM-16, AES256-GCM-16]
      phase2_integrity_algorithms:
        description: The permitted phase 2 integrity algorithms. Order is ignored.
        type: list
        elements: str
        choices: [SHA1, SHA2-256, SHA2-384, SHA2-512]
      pre_shared_key:
        description:
          - A pre-shared key of 8 to 64 alphanumeric, period, or underscore characters, not starting with zero.
          - A single shared tunnel options entry applies the same pre-shared key to both tunnels.
          - Updates require EC2 to return the current key for comparison. If it is unavailable, the module fails before mutation.
          - Omit this option to leave the key unchanged, including when it is stored in Secrets Manager.
        type: str
      tunnel_inside_cidr:
        description: An unreserved IPv4 /30 network in C(169.254.0.0/16).
        type: str
      tunnel_inside_ipv6_cidr:
        description: An IPv6 /126 network in C(fd00::/8). Requires an IPv6 VPN connection.
        type: str
  vpn_connection_id:
    description:
      - The ID of an existing VPN connection. A missing ID cannot be used to create a connection.
      - Supply one of O(name), O(vpn_connection_id), or O(filters).
      - Mutually exclusive with O(name) and O(filters).
    type: str
  vpn_gateway_id:
    description:
      - The virtual private gateway ID. Required for creation unless O(transit_gateway_id) is supplied.
      - Mutually exclusive with O(transit_gateway_id).
    type: str
  wait_delay:
    description: Seconds between readiness checks.
    type: int
    default: 15
    aliases: [delay]
  wait_timeout:
    description: Maximum seconds to wait for each connection operation.
    type: int
    default: 600
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description:
      - Predicts changes without mutating AWS. Returns current state for updates and an empty dictionary for creation or deletion.
      - Conservatively predicts supplied tunnel settings as changed while a pending VPN has unallocated endpoints.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
notes:
  - This rewritten implementation was introduced in collection release 2.3.1.
  - Results exclude customer gateway XML and pre-shared keys, including AWS-generated keys.
  - O(name) owns the Name tag even when O(tags) is omitted or empty.
  - All CIDRs must be canonical network addresses without host bits set.
"""

EXAMPLES = r"""
- name: Create a statically routed VPN
  linuxhq.aws.ec2_vpc_vpn:
    name: branch-office
    customer_gateway_id: cgw-0123456789abcdef0
    vpn_gateway_id: vgw-0123456789abcdef0
    static_only: true
    routes: [10.20.0.0/16]
    tunnel_options:
      - ike_versions: [ikev2]
        phase1_encryption_algorithms: [AES256]
        phase2_encryption_algorithms: [AES256]
      - ike_versions: [ikev2]
        phase1_encryption_algorithms: [AES256]
        phase2_encryption_algorithms: [AES256]

- name: Update encryption on an existing tunnel
  linuxhq.aws.ec2_vpc_vpn:
    vpn_connection_id: vpn-0123456789abcdef0
    tunnel_options:
      - outside_ip_address: 203.0.113.10
        phase1_encryption_algorithms: [AES256-GCM-16]
        phase2_encryption_algorithms: [AES256-GCM-16]

- name: Delete the branch VPN
  linuxhq.aws.ec2_vpc_vpn:
    name: branch-office
    state: absent
"""

RETURN = r"""
vpn_connection:
  description: The current connection with snake_case keys and without secrets. Empty when absent or creation is predicted.
  returned: always
  type: dict
  contains:
    vpn_connection_id:
      description: The connection ID.
      returned: when a connection exists
      type: str
    state:
      description: The connection lifecycle state.
      returned: when a connection exists
      type: str
    customer_gateway_id:
      description: The customer gateway ID.
      returned: when a connection exists
      type: str
    vpn_gateway_id:
      description: The virtual private gateway ID.
      returned: when attached to a virtual private gateway
      type: str
    transit_gateway_id:
      description: The transit gateway ID.
      returned: when attached to a transit gateway
      type: str
    type:
      description: The VPN connection type.
      returned: when provided by EC2
      type: str
    category:
      description: The VPN connection category.
      returned: when provided by EC2
      type: str
    core_network_arn:
      description: The Cloud WAN core network ARN.
      returned: when provided by EC2
      type: str
    core_network_attachment_arn:
      description: The Cloud WAN attachment ARN.
      returned: when provided by EC2
      type: str
    gateway_association_state:
      description: The gateway association state.
      returned: when provided by EC2
      type: str
    vpn_concentrator_id:
      description: The VPN concentrator ID.
      returned: when provided by EC2
      type: str
    pre_shared_key_arn:
      description: The ARN referencing the stored pre-shared key, not the key value.
      returned: when provided by EC2
      type: str
    vgw_telemetry:
      description: Status information for each VPN tunnel.
      returned: when provided by EC2
      type: list
      elements: dict
      contains:
        accepted_route_count:
          description: The number of accepted routes.
          returned: when provided by EC2
          type: int
        last_status_change:
          description: The timestamp of the last status change.
          returned: when provided by EC2
          type: str
        outside_ip_address:
          description: The tunnel outside IP address.
          returned: when provided by EC2
          type: str
        status:
          description: The tunnel status.
          returned: when provided by EC2
          type: str
        status_message:
          description: Details about the tunnel status.
          returned: when provided by EC2
          type: str
        certificate_arn:
          description: The certificate ARN.
          returned: when provided by EC2
          type: str
    options:
      description: Connection and tunnel options with pre-shared keys removed.
      returned: when a connection exists
      type: dict
      contains:
        enable_acceleration:
          description: Whether accelerated VPN is enabled.
          returned: when provided by EC2
          type: bool
        outside_ip_address_type:
          description: The outside IP address type.
          returned: when provided by EC2
          type: str
        transport_transit_gateway_attachment_id:
          description: The transit gateway attachment carrying private-IP VPN traffic.
          returned: when provided by EC2
          type: str
        tunnel_bandwidth:
          description: The configured tunnel bandwidth tier.
          returned: when provided by EC2
          type: str
        static_routes_only:
          description: Whether the connection uses static routing.
          returned: when provided by EC2
          type: bool
        tunnel_inside_ip_version:
          description: The tunnel address family.
          returned: when provided by EC2
          type: str
        local_ipv4_network_cidr:
          description: The local IPv4 network CIDR.
          returned: when provided by EC2
          type: str
        local_ipv6_network_cidr:
          description: The local IPv6 network CIDR.
          returned: when provided by EC2
          type: str
        remote_ipv4_network_cidr:
          description: The remote IPv4 network CIDR.
          returned: when provided by EC2
          type: str
        remote_ipv6_network_cidr:
          description: The remote IPv6 network CIDR.
          returned: when provided by EC2
          type: str
        tunnel_options:
          description: Tunnel configuration with pre-shared keys removed.
          returned: when provided by EC2
          type: list
          elements: dict
          contains:
            outside_ip_address:
              description: The tunnel outside IP address.
              returned: when provided by EC2
              type: str
            tunnel_inside_cidr:
              description: The tunnel inside IPv4 CIDR.
              returned: when provided by EC2
              type: str
            tunnel_inside_ipv6_cidr:
              description: The tunnel inside IPv6 CIDR.
              returned: when provided by EC2
              type: str
            ike_versions:
              description: IKE versions.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: str
            phase1_encryption_algorithms:
              description: Phase 1 encryption algorithms.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: str
            phase2_encryption_algorithms:
              description: Phase 2 encryption algorithms.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: str
            phase1_integrity_algorithms:
              description: Phase 1 integrity algorithms.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: str
            phase2_integrity_algorithms:
              description: Phase 2 integrity algorithms.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: str
            phase1_dh_group_numbers:
              description: Phase 1 DH groups.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: int
            phase2_dh_group_numbers:
              description: Phase 2 DH groups.
              returned: when provided by EC2
              type: list
              elements: dict
              contains:
                value:
                  description: The configured value.
                  returned: always
                  type: int
    routes:
      description: Static routes with destination_cidr_block and state fields.
      returned: when a connection exists
      type: list
      elements: dict
      contains:
        destination_cidr_block:
          description: The destination network CIDR.
          returned: always
          type: str
        source:
          description: The route source.
          returned: when provided by EC2
          type: str
        state:
          description: The route lifecycle state.
          returned: when provided by EC2
          type: str
    tags:
      description: Tags with original key casing preserved.
      returned: when a connection exists
      type: dict
"""

import ipaddress
import re
import secrets
from copy import deepcopy

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import custom_waiter_config

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import require_positive_wait_bounds, run_waiter

CONNECTION_FIELDS = {
    "local_ipv4_network_cidr": "LocalIpv4NetworkCidr",
    "remote_ipv4_network_cidr": "RemoteIpv4NetworkCidr",
    "local_ipv6_network_cidr": "LocalIpv6NetworkCidr",
    "remote_ipv6_network_cidr": "RemoteIpv6NetworkCidr",
}

TUNNEL_FIELDS = {
    "tunnel_inside_cidr": "TunnelInsideCidr",
    "tunnel_inside_ipv6_cidr": "TunnelInsideIpv6Cidr",
    "pre_shared_key": "PreSharedKey",
    "ike_versions": "IKEVersions",
    "phase1_encryption_algorithms": "Phase1EncryptionAlgorithms",
    "phase2_encryption_algorithms": "Phase2EncryptionAlgorithms",
    "phase1_integrity_algorithms": "Phase1IntegrityAlgorithms",
    "phase2_integrity_algorithms": "Phase2IntegrityAlgorithms",
    "phase1_dh_group_numbers": "Phase1DHGroupNumbers",
    "phase2_dh_group_numbers": "Phase2DHGroupNumbers",
}

TUNNEL_CHOICES = {
    "ike_versions": ["ikev1", "ikev2"],
    "phase1_encryption_algorithms": ["AES128", "AES256", "AES128-GCM-16", "AES256-GCM-16"],
    "phase2_encryption_algorithms": ["AES128", "AES256", "AES128-GCM-16", "AES256-GCM-16"],
    "phase1_integrity_algorithms": ["SHA1", "SHA2-256", "SHA2-384", "SHA2-512"],
    "phase2_integrity_algorithms": ["SHA1", "SHA2-256", "SHA2-384", "SHA2-512"],
    "phase1_dh_group_numbers": [2, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
    "phase2_dh_group_numbers": [2, 5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
}


RESERVED_TUNNEL_IPV4_NETWORKS = {f"169.254.{index}.0/30" for index in range(6)} | {"169.254.169.252/30"}


def normalize_connection(connection):
    if not connection:
        return {}

    result = deepcopy(connection)
    result.pop("CustomerGatewayConfiguration", None)

    for tunnel in result.get("Options", {}).get("TunnelOptions") or []:
        tunnel.pop("PreSharedKey", None)

    tags = boto3_tag_list_to_ansible_dict(result.pop("Tags", None) or [])
    result = camel_dict_to_snake_dict(result)
    result["tags"] = tags

    return result


def validate_connection(module, connection):
    if (
        not isinstance(connection, dict)
        or not connection.get("VpnConnectionId")
        or not connection.get("State")
        or not isinstance(connection.get("Options"), dict)
    ):
        module.fail_json(msg="EC2 returned an invalid VPN connection")

    routes = connection.get("Routes", [])
    if not isinstance(routes, list) or any(
        not isinstance(route, dict) or not route.get("DestinationCidrBlock") for route in routes
    ):
        module.fail_json(msg="EC2 returned invalid VPN connection routes")

    tunnels = connection["Options"].get("TunnelOptions")
    if tunnels is not None and (
        not isinstance(tunnels, list) or any(not isinstance(tunnel, dict) for tunnel in tunnels)
    ):
        module.fail_json(msg="EC2 returned invalid VPN connection tunnel options")

    return connection


def find_connection(client, module, connection_id=None):
    connection_id = connection_id or module.params["vpn_connection_id"]
    filters = module.params["filters"]

    if module.params["name"]:
        filters = {"tag:Name": module.params["name"]}

    request = (
        {"VpnConnectionIds": [connection_id]}
        if connection_id
        else {"Filters": ansible_dict_to_boto3_filter_list(filters)}
    )

    try:
        # DescribeVpnConnections has no pagination in the EC2 API.
        response = client.describe_vpn_connections(**request, aws_retry=True)
    except is_boto3_error_code("InvalidVpnConnectionID.NotFound"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e, msg=f"Unable to describe VPN connection {connection_id or module.params['name'] or filters}"
        )

    connections = response.get("VpnConnections")
    if not isinstance(connections, list):
        module.fail_json(msg="EC2 returned an invalid VPN connection list")

    matches = []
    for item in connections:
        if isinstance(item, dict) and item.get("State") == "deleted":
            continue

        matches.append(validate_connection(module, item))

    if len(matches) > 1:
        module.fail_json(msg="Multiple VPN connections matched; select a unique name, ID, or filters")

    return matches[0] if matches else None


def wait_for_connection(client, module, connection_id, state="available"):
    try:
        client.get_waiter(f"vpn_connection_{state}").wait(
            VpnConnectionIds=[connection_id],
            WaiterConfig=custom_waiter_config(module.params["wait_timeout"], default_pause=module.params["wait_delay"]),
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to wait for VPN connection {connection_id} to become {state}")


def tunnel_request(options):
    result = {}

    for name, field in TUNNEL_FIELDS.items():
        value = options.get(name)
        if value is not None:
            if name in TUNNEL_CHOICES:
                value = [{"Value": item} for item in sorted(set(value))]

            result[field] = value

    return result


def valid_pre_shared_key(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9._]{8,64}", value)) and not value.startswith("0")


def tunnel_deltas(module, connection):
    current = connection["Options"].get("TunnelOptions") or []
    desired_tunnels = module.params["tunnel_options"] or []
    explicit = [bool(tunnel.get("outside_ip_address")) for tunnel in desired_tunnels]
    if any(explicit) and not all(explicit):
        module.fail_json(msg="Do not mix tunnel entries with and without outside_ip_address")

    outside_ips = [tunnel["outside_ip_address"] for tunnel in desired_tunnels if tunnel.get("outside_ip_address")]
    if len(outside_ips) != len(set(outside_ips)):
        module.fail_json(msg="Tunnel selections must identify distinct existing outside IP addresses")

    if (
        len(desired_tunnels) == 1
        and not any(explicit)
        and (len(current) > 1 or connection["State"] == "pending")
        and any(desired_tunnels[0].get(name) is not None for name in ("tunnel_inside_cidr", "tunnel_inside_ipv6_cidr"))
    ):
        module.fail_json(msg="Select a specific tunnel when updating a tunnel inside CIDR")

    if (
        module.check_mode
        and connection["State"] == "pending"
        and (len(current) < 2 or any(not tunnel.get("OutsideIpAddress") for tunnel in current))
    ):
        # Predict supplied changes until EC2 assigns the endpoints. These unresolved
        # targets are check-mode only and must never reach a modifying SDK call.
        return [
            (tunnel.get("outside_ip_address"), tunnel_request(tunnel))
            for tunnel in desired_tunnels
            if tunnel_request(tunnel)
        ]

    requests = []
    for index, desired in enumerate(desired_tunnels):
        if desired.get("outside_ip_address"):
            requests.append(desired)
            continue

        if not current:
            module.fail_json(msg="EC2 did not return the requested tunnels")

        targets = current
        if len(desired_tunnels) > 1:
            try:
                targets = sorted(current, key=lambda tunnel: int(ipaddress.ip_address(tunnel["OutsideIpAddress"])))
            except (KeyError, ValueError):
                module.fail_json(msg="EC2 returned an invalid tunnel outside IP address")

            if index >= len(targets):
                module.fail_json(msg="EC2 did not return the requested tunnel")

            targets = [targets[index]]

        for tunnel in targets:
            requests.append(dict(desired, outside_ip_address=tunnel.get("OutsideIpAddress")))

    changes = []
    selected = set()

    for desired in requests:
        outside_ip = desired.get("outside_ip_address")
        if not outside_ip:
            module.fail_json(msg="EC2 did not return a tunnel outside IP address")

        matches = [tunnel for tunnel in current if tunnel.get("OutsideIpAddress") == outside_ip]
        if len(matches) != 1:
            module.fail_json(msg=f"No unique tunnel with outside IP {outside_ip} on {connection['VpnConnectionId']}")

        tunnel = matches[0]
        outside_ip = tunnel.get("OutsideIpAddress")
        if not outside_ip or outside_ip in selected:
            module.fail_json(msg="Tunnel selections must identify distinct existing outside IP addresses")

        selected.add(outside_ip)

        delta = {}
        for field, value in tunnel_request(desired).items():
            # EC2 uses different IKE key casing in requests and responses.
            actual = tunnel.get("IkeVersions" if field == "IKEVersions" else field)
            if field == "PreSharedKey" and (
                not isinstance(actual, str)
                or not actual.strip()
                or set(actual) <= {"*"}
                or actual.lower() in {"<redacted>", "redacted", "<hidden>", "hidden"}
            ):
                module.fail_json(
                    msg=f"Cannot compare pre_shared_key for VPN connection {connection['VpnConnectionId']} "
                    f"tunnel {outside_ip}; EC2 did not return a usable current key. "
                    "Omit pre_shared_key to leave it unchanged."
                )

            if field == "PreSharedKey":
                equal = secrets.compare_digest(value.encode("utf-8"), actual.encode("utf-8"))
            elif isinstance(value, list):
                value_type = int if field.endswith("DHGroupNumbers") else str
                if actual is not None and (
                    not isinstance(actual, list)
                    or any(
                        not isinstance(item, dict)
                        or not isinstance(item.get("Value"), value_type)
                        or isinstance(item.get("Value"), bool)
                        for item in actual
                    )
                ):
                    module.fail_json(
                        msg=f"EC2 returned invalid {field} for VPN connection {connection['VpnConnectionId']} "
                        f"tunnel {outside_ip}"
                    )

                equal = {item["Value"] for item in value} == {item["Value"] for item in actual or []}
            else:
                equal = value == actual

            if not equal:
                if field in ("TunnelInsideCidr", "TunnelInsideIpv6Cidr") and any(
                    other is not tunnel and other.get(field) == value for other in current
                ):
                    module.fail_json(
                        msg=f"Cannot set {field} to {value} on VPN connection {connection['VpnConnectionId']} "
                        f"tunnel {outside_ip}; the CIDR is already assigned to another tunnel. "
                        "Select tunnels by outside_ip_address and use distinct, unused CIDRs."
                    )

                delta[field] = value

        if delta:
            changes.append((outside_ip, delta))

    return changes


def validate_network(module, value, name, version):
    try:
        network = ipaddress.ip_network(value, strict=True)
        if network.version != version:
            raise ValueError
    except ValueError:
        module.fail_json(msg=f"{name} must be a canonical IPv{version} CIDR")

    return network


def validate_inputs(module):
    require_positive_wait_bounds(module, always=True)

    if module.params["name"] is not None and not module.params["name"].strip():
        module.fail_json(msg="name must not be empty")

    if module.params["filters"] is not None and not module.params["filters"]:
        module.fail_json(msg="filters must not be empty")

    if module.params["vpn_connection_id"] is not None and not module.params["vpn_connection_id"]:
        module.fail_json(msg="vpn_connection_id must not be empty")

    if module.params["state"] == "absent":
        return

    if (
        module.params["name"]
        and module.params["tags"] is not None
        and module.params["tags"].get("Name", module.params["name"]) != module.params["name"]
    ):
        module.fail_json(msg="tags.Name must match name")

    for name in CONNECTION_FIELDS:
        value = module.params[name]
        if value is not None:
            module.params[name] = str(validate_network(module, value, name, 4 if "ipv4" in name else 6))

    if module.params["routes"] is not None:
        module.params["routes"] = sorted(
            {str(validate_network(module, route, "routes", 4)) for route in module.params["routes"]}
        )

    tunnels = module.params["tunnel_options"] or []
    if len(tunnels) > 2:
        module.fail_json(msg="tunnel_options must contain at most two entries")

    inside_networks = set()
    for tunnel in tunnels:
        for name in TUNNEL_CHOICES:
            if tunnel.get(name) == []:
                module.fail_json(msg=f"tunnel_options[].{name} must not be empty")

        key = tunnel.get("pre_shared_key")
        if key is not None and not valid_pre_shared_key(key):
            module.fail_json(msg="Invalid tunnel pre_shared_key format")

        for name, version, prefix, block in (
            ("tunnel_inside_cidr", 4, 30, "169.254.0.0/16"),
            ("tunnel_inside_ipv6_cidr", 6, 126, "fd00::/8"),
        ):
            value = tunnel.get(name)
            if value is None:
                continue

            network = validate_network(module, value, name, version)
            if (
                network.prefixlen != prefix
                or not network.subnet_of(ipaddress.ip_network(block))
                or (version == 4 and str(network) in RESERVED_TUNNEL_IPV4_NETWORKS)
            ):
                module.fail_json(msg=f"{name} must be an unreserved /{prefix} CIDR within {block}")

            if str(network) in inside_networks:
                module.fail_json(msg="Tunnel inside CIDRs must be distinct")

            inside_networks.add(str(network))
            tunnel[name] = str(network)


def desired_tags(module, current):
    tags = dict(module.params["tags"]) if module.params["tags"] is not None else None
    purge = module.params["purge_tags"]

    if module.params["name"]:
        purge = purge if tags is not None else False
        tags = dict(tags or {}, Name=module.params["name"])

    if tags is None:
        return {}, []

    require_valid_tags(module, tags, 50, key_max=127)
    return compare_aws_tags(boto3_tag_list_to_ansible_dict(current.get("Tags") or []), tags, purge)


def validate_configuration(module, connection=None):
    options = connection["Options"] if connection is not None else {}
    static_only = (
        (options.get("StaticRoutesOnly") or False)
        if connection is not None
        else (module.params["static_only"] or False)
    )
    transit_gateway = (
        connection.get("TransitGatewayId") if connection is not None else module.params["transit_gateway_id"]
    )
    family = (
        (options.get("TunnelInsideIpVersion") or "ipv4")
        if connection is not None
        else (module.params["tunnel_inside_ip_version"] or "ipv4")
    )

    if module.params["routes"] and (not static_only or transit_gateway):
        module.fail_json(msg="Static routes require static_only=true and a virtual private gateway connection")

    if family == "ipv6" and not transit_gateway:
        module.fail_json(msg="IPv6 VPN connections require a transit gateway")

    for tunnel in module.params["tunnel_options"] or []:
        if tunnel.get("tunnel_inside_cidr") is not None and family != "ipv4":
            module.fail_json(msg="tunnel_inside_cidr requires tunnel_inside_ip_version=ipv4")

        if tunnel.get("tunnel_inside_ipv6_cidr") is not None and family != "ipv6":
            module.fail_json(msg="tunnel_inside_ipv6_cidr requires tunnel_inside_ip_version=ipv6")

    if connection is not None:
        immutable = {
            "customer_gateway_id": connection.get("CustomerGatewayId"),
            "vpn_gateway_id": connection.get("VpnGatewayId"),
            "transit_gateway_id": connection.get("TransitGatewayId"),
            "static_only": static_only,
            "tunnel_inside_ip_version": family,
        }

        for name, actual in immutable.items():
            if module.params[name] is not None and module.params[name] != actual:
                module.fail_json(msg=f"Cannot change {name} on an existing VPN connection with this module")


def create_connection(client, module):
    if module.params["vpn_connection_id"] is not None or module.params["filters"] is not None:
        selector = "vpn_connection_id" if module.params["vpn_connection_id"] is not None else "filters"
        module.fail_json(
            msg=f"No VPN connection matched {selector}. This selector cannot create a connection; "
            "use name instead of the selector to create a VPN connection."
        )

    if (
        not module.params["name"]
        or not module.params["customer_gateway_id"]
        or not (module.params["vpn_gateway_id"] or module.params["transit_gateway_id"])
    ):
        module.fail_json(
            msg="Creation requires name, customer_gateway_id, and either vpn_gateway_id or transit_gateway_id"
        )

    if any(tunnel.get("outside_ip_address") for tunnel in module.params["tunnel_options"] or []):
        module.fail_json(msg="outside_ip_address cannot be specified during creation")

    validate_configuration(module)
    tags = desired_tags(module, {})[0]

    options = {field: module.params[name] for name, field in CONNECTION_FIELDS.items()}
    options.update(
        StaticRoutesOnly=module.params["static_only"], TunnelInsideIpVersion=module.params["tunnel_inside_ip_version"]
    )
    if module.params["tunnel_options"]:
        options["TunnelOptions"] = [tunnel_request(tunnel) for tunnel in module.params["tunnel_options"]]
        if len(options["TunnelOptions"]) == 1:
            if any(name in options["TunnelOptions"][0] for name in ("TunnelInsideCidr", "TunnelInsideIpv6Cidr")):
                module.fail_json(msg="Provide two distinct tunnel CIDRs instead of one shared tunnel CIDR")

            options["TunnelOptions"].append(deepcopy(options["TunnelOptions"][0]))

    request = scrub_none_parameters(
        {
            "Type": module.params["connection_type"],
            "CustomerGatewayId": module.params["customer_gateway_id"],
            "VpnGatewayId": module.params["vpn_gateway_id"],
            "TransitGatewayId": module.params["transit_gateway_id"],
            "Options": options,
            "TagSpecifications": [{"ResourceType": "vpn-connection", "Tags": ansible_dict_to_boto3_tag_list(tags)}],
        }
    )

    if module.check_mode:
        module.exit_json(changed=True, vpn_connection={})

    try:
        response = client.create_vpn_connection(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to create VPN connection {module.params['name']}")

    connection = validate_connection(module, response.get("VpnConnection"))
    wait_for_connection(client, module, connection["VpnConnectionId"])

    return read_connection(client, module, connection["VpnConnectionId"])


def read_connection(client, module, connection_id):
    connection = find_connection(client, module, connection_id)
    if connection is None:
        module.fail_json(msg=f"VPN connection {connection_id} disappeared while being managed")

    return connection


def ensure_present(client, module, connection):
    changed = connection is None
    if connection is None:
        connection = create_connection(client, module)

    connection_id = connection["VpnConnectionId"]
    if connection["State"] == "deleting":
        module.fail_json(
            msg=f"VPN connection {connection_id} is deleting; wait for deletion before creating a replacement"
        )

    if connection["State"] != "available" and not module.check_mode:
        wait_for_connection(client, module, connection_id)
        connection = read_connection(client, module, connection_id)

    validate_configuration(module, connection)

    # Creation already submitted tunnel options before EC2 allocated their outside IPs.
    tunnels = [] if changed else tunnel_deltas(module, connection)
    options = {
        field: module.params[name]
        for name, field in CONNECTION_FIELDS.items()
        if module.params[name] is not None and module.params[name] != connection["Options"].get(field)
    }
    tags_to_set, tags_to_remove = desired_tags(module, connection)

    current_routes = {
        route["DestinationCidrBlock"]
        for route in connection.get("Routes", [])
        if route.get("State") not in ("deleting", "deleted")
    }
    deleting_routes = {
        route["DestinationCidrBlock"] for route in connection.get("Routes", []) if route.get("State") == "deleting"
    }
    routes = module.params["routes"]
    add_routes = set(routes or []) - current_routes if routes is not None else set()
    remove_routes = current_routes - set(routes) if routes is not None and module.params["purge_routes"] else set()

    for route in add_routes | remove_routes:
        validate_network(module, route, "Route destination", 4)

    updated = bool(tunnels or options or tags_to_set or tags_to_remove or add_routes or remove_routes)
    changed |= updated
    if module.check_mode:
        module.exit_json(changed=changed, vpn_connection=normalize_connection(connection))

    pending_routes = {
        route["DestinationCidrBlock"]
        for route in connection.get("Routes", [])
        if route.get("State") == "pending" and route["DestinationCidrBlock"] in (routes or [])
    }
    for route in sorted(pending_routes):
        wait_for_route_available(client, module, connection_id, route)

    for route in sorted(add_routes & deleting_routes):
        wait_for_route_deleted(client, module, connection_id, route)

    if options:
        try:
            client.modify_vpn_connection_options(VpnConnectionId=connection_id, **options, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to modify options for VPN connection {connection_id}")

        wait_for_connection(client, module, connection_id)

    for outside_ip, delta in tunnels:
        try:
            client.modify_vpn_tunnel_options(
                VpnConnectionId=connection_id,
                VpnTunnelOutsideIpAddress=outside_ip,
                TunnelOptions=delta,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to modify VPN connection {connection_id} tunnel {outside_ip}")

        wait_for_connection(client, module, connection_id)

    reconcile_routes(client, module, connection_id, add_routes, remove_routes)
    reconcile_tags(client, module, connection_id, tags_to_set, tags_to_remove)

    if updated or pending_routes:
        connection = read_connection(client, module, connection_id)

    module.exit_json(changed=changed, vpn_connection=normalize_connection(connection))


def wait_for_route_deleted(client, module, connection_id, route):
    wait_for_route_state(client, module, connection_id, route, "deleted")


def wait_for_route_available(client, module, connection_id, route):
    wait_for_route_state(client, module, connection_id, route, "available")


def wait_for_route_state(client, module, connection_id, route, state):
    route = str(validate_network(module, route, "EC2 route destination", 4))
    if state == "deleted":
        argument = f"length(VpnConnections[].Routes[?DestinationCidrBlock == '{route}' && State != 'deleted'][])"
        expected = 0
    else:
        argument = f"length(VpnConnections[].Routes[?DestinationCidrBlock == '{route}' && State == 'available'][])"
        expected = 1

    waiter_name = "VPNRouteState"
    model = {
        waiter_name: {
            "operation": "DescribeVpnConnections",
            # Required model defaults; run_waiter applies the user's wait bounds.
            "delay": 15,
            "maxAttempts": 40,
            "acceptors": [
                {
                    "state": "failure",
                    "matcher": "pathAny",
                    "argument": "VpnConnections[].State",
                    "expected": "deleting",
                },
                {
                    "state": "failure",
                    "matcher": "pathAny",
                    "argument": "VpnConnections[].State",
                    "expected": "deleted",
                },
                {
                    "state": "failure",
                    "matcher": "path",
                    "argument": "length(VpnConnections)",
                    "expected": 0,
                },
                {
                    "state": "success",
                    "matcher": "path",
                    "argument": argument,
                    "expected": expected,
                },
            ],
        },
    }
    # A deleted route entry may linger after recreation; keep polling until
    # the new route is available or the VPN itself disappears.
    run_waiter(
        module,
        client,
        model,
        waiter_name,
        f"Unable to wait for route {route} to become {state} on VPN connection {connection_id}",
        VpnConnectionIds=[connection_id],
    )


def reconcile_routes(client, module, connection_id, additions, removals):
    for route in additions | removals:
        validate_network(module, route, "Route destination", 4)

    for route in sorted(removals):
        try:
            client.delete_vpn_connection_route(
                VpnConnectionId=connection_id, DestinationCidrBlock=route, aws_retry=True
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to delete route {route} from VPN connection {connection_id}")

        wait_for_route_deleted(client, module, connection_id, route)

    for route in sorted(additions):
        try:
            client.create_vpn_connection_route(
                VpnConnectionId=connection_id, DestinationCidrBlock=route, aws_retry=True
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to create route {route} on VPN connection {connection_id}")

        wait_for_route_available(client, module, connection_id, route)


def reconcile_tags(client, module, connection_id, additions, removals):
    if removals:
        try:
            client.delete_tags(Resources=[connection_id], Tags=[{"Key": key} for key in removals], aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to remove tags from VPN connection {connection_id}")

    if additions:
        try:
            client.create_tags(
                Resources=[connection_id], Tags=ansible_dict_to_boto3_tag_list(additions), aws_retry=True
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to tag VPN connection {connection_id}")


def ensure_absent(client, module, connection):
    if connection is None:
        module.exit_json(changed=False, vpn_connection={})

    changed = connection["State"] != "deleting"
    if module.check_mode:
        module.exit_json(changed=changed, vpn_connection={})

    connection_id = connection["VpnConnectionId"]
    if changed:
        try:
            client.delete_vpn_connection(VpnConnectionId=connection_id, aws_retry=True)
        except is_boto3_error_code("InvalidVpnConnectionID.NotFound"):
            module.exit_json(changed=False, vpn_connection={})
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to delete VPN connection {connection_id}")

    wait_for_connection(client, module, connection_id, "deleted")
    module.exit_json(changed=changed, vpn_connection={})


def main():
    tunnel_spec = {
        "outside_ip_address": {"type": "str"},
        "tunnel_inside_cidr": {"type": "str"},
        "tunnel_inside_ipv6_cidr": {"type": "str"},
        "pre_shared_key": {"type": "str", "no_log": True},
    }

    for name, choices in TUNNEL_CHOICES.items():
        tunnel_spec[name] = {
            "type": "list",
            "elements": "int" if name.endswith("numbers") else "str",
            "choices": choices,
        }

    argument_spec = {
        "name": {"type": "str"},
        "vpn_connection_id": {"type": "str"},
        "filters": {"type": "dict"},
        "state": {
            "type": "str",
            "choices": ["present", "absent"],
            "default": "present",
        },
        "customer_gateway_id": {"type": "str"},
        "vpn_gateway_id": {"type": "str"},
        "transit_gateway_id": {"type": "str"},
        "connection_type": {
            "type": "str",
            "choices": ["ipsec.1"],
            "default": "ipsec.1",
        },
        "static_only": {"type": "bool"},
        "tunnel_inside_ip_version": {
            "type": "str",
            "choices": ["ipv4", "ipv6"],
        },
        "tunnel_options": {
            "type": "list",
            "elements": "dict",
            "options": tunnel_spec,
        },
        "routes": {"type": "list", "elements": "str"},
        "purge_routes": {"type": "bool", "default": True},
        "tags": {"type": "dict", "aliases": ["resource_tags"]},
        "purge_tags": {"type": "bool", "default": True},
        "wait_delay": {
            "type": "int",
            "default": 15,
            "aliases": ["delay"],
        },
        "wait_timeout": {"type": "int", "default": 600},
    }
    argument_spec.update({name: {"type": "str"} for name in CONNECTION_FIELDS})

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_one_of=[["name", "vpn_connection_id", "filters"]],
        mutually_exclusive=[["name", "vpn_connection_id", "filters"], ["vpn_gateway_id", "transit_gateway_id"]],
        supports_check_mode=True,
    )
    validate_inputs(module)

    # A previous modification can still be settling when the connection waiter succeeds.
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["IncorrectState"]))
    connection = find_connection(client, module)

    if module.params["state"] == "present":
        ensure_present(client, module, connection)
    else:
        ensure_absent(client, module, connection)


if __name__ == "__main__":
    main()
