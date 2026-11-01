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
  - Gateway and VPN concentrator IDs, routing mode, tunnel address family, acceleration, outside IP address type, and
    transport attachment cannot be changed on an existing connection.
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
  enable_acceleration:
    description:
      - Whether the connection uses AWS Global Accelerator to route traffic to the nearest AWS edge location.
      - AWS defaults to false on creation. Cannot be changed on an existing connection.
    type: bool
    version_added: "2.6.0"
  filters:
    description:
      - EC2 filter names mapped to strings or lists of strings. Must uniquely identify a connection.
      - Uses native EC2 names such as C(tag:Name). A missing match cannot create a connection.
      - Boolean and numeric values, including list entries, are converted to strings.
      - Supply one of O(name), O(vpn_connection_id), or O(filters).
      - Mutually exclusive with O(name) and O(vpn_connection_id).
    type: dict
  local_ipv4_network_cidr:
    description: The IPv4 CIDR on the customer gateway side. AWS defaults to C(0.0.0.0/0).
    type: str
  local_ipv6_network_cidr:
    description: The IPv6 CIDR on the customer gateway side. AWS defaults to C(::/0). Requires an IPv6 VPN connection.
    type: str
  name:
    description:
      - The Name tag identifying the connection. Required when creating a connection.
      - The name is matched exactly; C(*) and C(?) are not wildcards.
      - Supply one of O(name), O(vpn_connection_id), or O(filters).
      - Mutually exclusive with O(vpn_connection_id) and O(filters).
    type: str
  outside_ip_address_type:
    description:
      - The type of IP address on the outside interface of the customer gateway device.
      - C(Ipv6) requires a customer gateway with an IPv6 address.
      - C(PrivateIpv4) requires O(transport_transit_gateway_attachment_id). It applies to private IP VPN
        connections over AWS Direct Connect, which this module supports with unit tests only.
      - AWS defaults to C(PublicIpv4) on creation. Cannot be changed on an existing connection.
    type: str
    choices: [PrivateIpv4, PublicIpv4, Ipv6]
    version_added: "2.6.0"
  pre_shared_key_storage:
    description:
      - Where the tunnel pre-shared keys are stored. C(Standard) stores them in the Site-to-Site VPN service.
        C(SecretsManager) stores them in an AWS Secrets Manager secret that EC2 creates and manages, returned as
        RV(vpn_connection.pre_shared_key_arn).
      - AWS defaults to C(Standard) on creation. When omitted, an existing connection is unchanged.
      - EC2 stores keys per tunnel. On an existing connection, each tunnel whose key is stored elsewhere is updated
        in turn and keeps its key, unless O(tunnel_options[].pre_shared_key) replaces it.
      - The module infers a tunnel's storage from EC2 returning its key, which EC2 omits only for a key stored in
        Secrets Manager.
      - EC2 creates the secret when a tunnel first stores its key there and deletes it with the connection. Moving
        every key back to C(Standard) leaves the empty secret and its ARN until the connection is deleted.
      - C(SecretsManager) cannot be used with O(tunnel_options[].pre_shared_key), because EC2 does not return keys
        stored in Secrets Manager for comparison.
      - Requires botocore 1.38.24 or later.
    type: str
    choices: [Standard, SecretsManager]
    version_added: "2.6.0"
  purge_routes:
    description: Remove routes not included in O(routes), when O(routes) is supplied.
    type: bool
    default: true
  remote_ipv4_network_cidr:
    description: The IPv4 CIDR on the AWS side. AWS defaults to C(0.0.0.0/0).
    type: str
  remote_ipv6_network_cidr:
    description: The IPv6 CIDR on the AWS side. AWS defaults to C(::/0). Requires an IPv6 VPN connection.
    type: str
  routes:
    description:
      - Static IPv4 route destinations. Requires static routing on a virtual private gateway connection.
      - Omitted routes are unchanged. An empty list removes routes when O(purge_routes=true).
      - Waits for requested routes to become available and removed routes to disappear, except in check mode.
    type: list
    elements: str
  skip_tunnel_replacement:
    description:
      - Whether to skip the immediate tunnel endpoint replacement that a change to
        O(tunnel_options[].enable_tunnel_lifecycle_control) starts on an existing tunnel.
      - When true, the module sends a tunnel's lifecycle control change on its own, which EC2 applies without a
        replacement or a C(modifying) state, and then sends the tunnel's other changes as usual. EC2 rejects skipping
        together with changes such as O(tunnel_options[].startup_action).
      - It is not part of the connection state, so it is never compared and never reports a change by itself. It is
        ignored during creation and when lifecycle control does not change.
      - When omitted or false, EC2 replaces the tunnel endpoint, which keeps its outside IP address.
    type: bool
    version_added: "2.6.0"
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
      - The transit gateway ID. Required for creation unless O(vpn_gateway_id) or O(vpn_concentrator_id) is supplied.
      - Mutually exclusive with O(vpn_gateway_id).
    type: str
  transport_transit_gateway_attachment_id:
    description:
      - The transit gateway attachment that carries the tunnels of a C(PrivateIpv4) connection, such as an AWS
        Direct Connect gateway attachment. EC2 requires it when O(outside_ip_address_type=PrivateIpv4).
      - Requires AWS Direct Connect, so this module supports it with unit tests only.
      - Cannot be changed on an existing connection.
    type: str
    version_added: "2.6.0"
  tunnel_bandwidth:
    description:
      - The bandwidth of each tunnel. C(standard) supports up to 1.25 Gbps per tunnel and C(large) up to 5 Gbps.
      - AWS defaults to C(standard) on creation. When omitted, an existing connection is unchanged.
      - C(large) requires a connection attached to a transit gateway or Cloud WAN. EC2 rejects it for a virtual
        private gateway.
      - A change on an existing connection is sent with the other connection options. In Regions where EC2 does
        not support changing the bandwidth, EC2 rejects the request and the connection is left unchanged.
      - Requires botocore 1.40.71 or later, and botocore 1.43.3 or later to change it on an existing connection.
    type: str
    choices: [standard, large]
    version_added: "2.6.0"
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
      dpd_timeout_action:
        description:
          - The action after a dead peer detection timeout. C(clear) ends the IKE session, C(restart) restarts the IKE
            initiation, and C(none) takes no action.
          - AWS defaults to C(clear).
        type: str
        choices: [clear, none, restart]
        version_added: "2.6.0"
      dpd_timeout_seconds:
        description:
          - The number of seconds after which a dead peer detection timeout occurs. Must be 30 or greater.
          - EC2 does not return a timeout that was never set, and the EC2 API documents both 30 and 40 as its default,
            so the first update that supplies a timeout for such a tunnel always sends it.
        type: int
        version_added: "2.6.0"
      enable_tunnel_lifecycle_control:
        description:
          - Whether tunnel endpoint lifecycle control is enabled, which lets you schedule the replacement of the tunnel
            endpoint during AWS maintenance.
          - AWS defaults to false. Changing it on an existing tunnel replaces the tunnel endpoint, which keeps its
            outside IP address, unless O(skip_tunnel_replacement=true).
        type: bool
        version_added: "2.6.0"
      ike_versions:
        description: The permitted IKE versions. Order is ignored.
        type: list
        elements: str
        choices: [ikev1, ikev2]
      log_options:
        description: Options for logging tunnel activity.
        type: dict
        version_added: "2.6.0"
        suboptions:
          cloud_watch_log_options:
            description:
              - Options for sending tunnel logs to CloudWatch Logs. Omitted fields retain their current values.
              - EC2 rejects a log group that does not exist in the connection's Region.
            type: dict
            suboptions:
              bgp_log_enabled:
                description:
                  - Whether to send BGP logs. AWS defaults to false.
                  - EC2 rejects enabling it on a tunnel without a BGP log group, which
                    O(tunnel_options[].log_options.cloud_watch_log_options.bgp_log_group_arn) sets.
                  - Requires botocore 1.41.1 or later.
                type: bool
              bgp_log_group_arn:
                description:
                  - The ARN of the CloudWatch Logs log group for BGP logs.
                  - EC2 stores the ARN as supplied, with or without a trailing C(:*), and the module compares it
                    exactly.
                  - Requires botocore 1.41.1 or later.
                type: str
              bgp_log_output_format:
                description:
                  - The format of BGP logs. AWS defaults to C(json).
                  - Requires botocore 1.41.1 or later.
                type: str
                choices: [json, text]
              log_enabled:
                description:
                  - Whether to send tunnel activity logs. AWS defaults to false.
                  - EC2 requires a log group, from O(tunnel_options[].log_options.cloud_watch_log_options.log_group_arn)
                    or already set on the tunnel, to enable it.
                type: bool
              log_group_arn:
                description:
                  - The ARN of the CloudWatch Logs log group for tunnel activity logs.
                  - EC2 stores the ARN as supplied, with or without a trailing C(:*), and the module compares it
                    exactly.
                  - EC2 keeps the log group when logging is disabled.
                type: str
              log_output_format:
                description: The format of tunnel activity logs. AWS defaults to C(json).
                type: str
                choices: [json, text]
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
      phase1_lifetime_seconds:
        description:
          - The lifetime of phase 1 of the IKE negotiation, from 900 to 28800 seconds. AWS defaults to 28800.
          - Must not be less than the tunnel's phase 2 lifetime.
          - EC2 checks the lifetimes and rekey margin of an update against the AWS defaults of those it omits, not the
            tunnel's current values. A change to one of them therefore also resends the others already set on the
            tunnel, and the module checks the resulting values before any change.
        type: int
        version_added: "2.6.0"
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
      phase2_lifetime_seconds:
        description:
          - The lifetime of phase 2 of the IKE negotiation, from 900 to 3600 seconds. AWS defaults to 3600.
          - Must not exceed the tunnel's phase 1 lifetime and must be at least twice its rekey margin time. Updated
            together with them, as O(tunnel_options[].phase1_lifetime_seconds) describes.
        type: int
        version_added: "2.6.0"
      pre_shared_key:
        description:
          - A pre-shared key of 8 to 64 alphanumeric, period, or underscore characters, not starting with zero.
          - A single shared tunnel options entry applies the same pre-shared key to both tunnels.
          - Updates require EC2 to return the current key for comparison. If it is unavailable, the module fails before mutation.
          - EC2 does not return a key stored in Secrets Manager. Omit this option to leave such a key unchanged, or set
            O(pre_shared_key_storage=Standard) to move the key out of Secrets Manager and set it in the same update.
          - Cannot be used with O(pre_shared_key_storage=SecretsManager).
        type: str
      rekey_fuzz_percentage:
        description:
          - The percentage of the rekey window, set by the rekey margin time, during which the rekey time is randomly
            selected. From 0 to 100. AWS defaults to 100.
        type: int
        version_added: "2.6.0"
      rekey_margin_time_seconds:
        description:
          - The seconds before the phase 2 lifetime expires during which AWS performs an IKE rekey. AWS defaults to 270.
          - Must be 60 or greater and at most half of the tunnel's phase 2 lifetime. Updated together with the
            lifetimes, as O(tunnel_options[].phase1_lifetime_seconds) describes.
        type: int
        version_added: "2.6.0"
      replay_window_size:
        description: The number of packets in an IKE replay window, from 64 to 2048. AWS defaults to 1024.
        type: int
        version_added: "2.6.0"
      startup_action:
        description:
          - The action when establishing the tunnel. C(add) waits for the customer gateway to initiate the IKE
            negotiation, and C(start) has AWS initiate it.
          - AWS defaults to C(add).
        type: str
        choices: [add, start]
        version_added: "2.6.0"
      tunnel_inside_cidr:
        description: An unreserved IPv4 /30 network in C(169.254.0.0/16).
        type: str
      tunnel_inside_ipv6_cidr:
        description: An IPv6 /126 network in C(fd00::/8). Requires an IPv6 VPN connection.
        type: str
  vpn_concentrator_id:
    description:
      - The ID of the VPN concentrator that attaches the connection to its transit gateway. Required for creation
        unless O(vpn_gateway_id) or O(transit_gateway_id) is supplied. EC2 rejects it together with
        O(transit_gateway_id).
      - Cannot be changed on an existing connection.
      - Requires botocore 1.40.76 or later.
    type: str
    version_added: "2.6.0"
  vpn_connection_id:
    description:
      - The ID of an existing VPN connection. A missing ID cannot be used to create a connection.
      - Supply one of O(name), O(vpn_connection_id), or O(filters).
      - Mutually exclusive with O(name) and O(filters).
    type: str
  vpn_gateway_id:
    description:
      - The virtual private gateway ID. Required for creation unless O(transit_gateway_id) or O(vpn_concentrator_id)
        is supplied.
      - Mutually exclusive with O(transit_gateway_id).
    type: str
  wait_delay:
    description:
      - Seconds between readiness checks.
      - This must be 1 or greater.
    type: int
    default: 15
    aliases: [delay]
  wait_timeout:
    description:
      - Maximum seconds to wait for each connection operation.
      - This must be 1 or greater.
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
      - Conservatively predicts supplied tunnel settings and O(pre_shared_key_storage) as changed while a pending VPN
        has unallocated endpoints.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
notes:
  - This rewritten implementation was introduced in collection release 2.4.0.
  - Results exclude customer gateway XML and pre-shared keys, including AWS-generated keys.
  - O(name) owns the Name tag even when O(tags) is omitted or empty.
  - O(tags) keys must not be blank. EC2 stores a tag value made only of spaces,
    tabs, carriage returns, and line feeds as an empty value, so such a value is
    sent, compared, and returned as empty.
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

- name: Create a large-bandwidth transit gateway VPN with keys in Secrets Manager
  linuxhq.aws.ec2_vpc_vpn:
    name: datacenter
    customer_gateway_id: cgw-0123456789abcdef0
    transit_gateway_id: tgw-0123456789abcdef0
    tunnel_bandwidth: large
    pre_shared_key_storage: SecretsManager

- name: Create an accelerated transit gateway VPN with tuned and logged tunnels
  linuxhq.aws.ec2_vpc_vpn:
    name: datacenter-accelerated
    customer_gateway_id: cgw-0123456789abcdef0
    transit_gateway_id: tgw-0123456789abcdef0
    enable_acceleration: true
    tunnel_options:
      - phase1_lifetime_seconds: 14400
        phase2_lifetime_seconds: 1800
        rekey_margin_time_seconds: 540
        dpd_timeout_seconds: 60
        dpd_timeout_action: restart
        startup_action: start
        log_options:
          cloud_watch_log_options:
            log_enabled: true
            log_group_arn: arn:aws:logs:us-east-1:123456789012:log-group:vpn-tunnels
            log_output_format: text

- name: Attach a branch VPN to a VPN concentrator
  linuxhq.aws.ec2_vpc_vpn:
    name: branch-17
    customer_gateway_id: cgw-0123456789abcdef0
    vpn_concentrator_id: vcn-0123456789abcdef0

- name: Turn on tunnel endpoint lifecycle control without replacing the endpoints
  linuxhq.aws.ec2_vpc_vpn:
    vpn_connection_id: vpn-0123456789abcdef0
    skip_tunnel_replacement: true
    tunnel_options:
      - enable_tunnel_lifecycle_control: true

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
      description:
        - The ARN of the Secrets Manager secret that EC2 created for the pre-shared keys, not a key value.
        - EC2 keeps returning it after every tunnel moves its key out of Secrets Manager, so it does not show
          where the keys are stored.
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
            dpd_timeout_action:
              description: The action to take after a dead peer detection timeout.
              returned: when provided by EC2
              type: str
            dpd_timeout_seconds:
              description: The number of seconds after which a dead peer detection timeout occurs.
              returned: when provided by EC2
              type: int
            enable_tunnel_lifecycle_control:
              description: Whether tunnel endpoint lifecycle control is enabled.
              returned: when provided by EC2
              type: bool
            log_options:
              description: Options for logging VPN tunnel activity.
              returned: when provided by EC2
              type: dict
              contains:
                cloud_watch_log_options:
                  description: Options for sending VPN tunnel logs to CloudWatch.
                  returned: when provided by EC2
                  type: dict
                  contains:
                    bgp_log_enabled:
                      description: Whether BGP logging is enabled.
                      returned: when provided by EC2
                      type: bool
                    bgp_log_group_arn:
                      description: The ARN of the CloudWatch log group for BGP logs.
                      returned: when provided by EC2
                      type: str
                    bgp_log_output_format:
                      description: The output format for BGP logs.
                      returned: when provided by EC2
                      type: str
                    log_enabled:
                      description: Whether VPN tunnel logging is enabled.
                      returned: when provided by EC2
                      type: bool
                    log_group_arn:
                      description: The ARN of the CloudWatch log group for tunnel logs.
                      returned: when provided by EC2
                      type: str
                    log_output_format:
                      description: The output format for tunnel logs.
                      returned: when provided by EC2
                      type: str
            phase1_lifetime_seconds:
              description: The lifetime for phase 1 of the IKE negotiation, in seconds.
              returned: when provided by EC2
              type: int
            phase2_lifetime_seconds:
              description: The lifetime for phase 2 of the IKE negotiation, in seconds.
              returned: when provided by EC2
              type: int
            rekey_fuzz_percentage:
              description: The percentage of the rekey window set by the rekey margin time during which the rekey time is randomly selected.
              returned: when provided by EC2
              type: int
            rekey_margin_time_seconds:
              description: The margin time, in seconds, before the phase 2 lifetime expires during which AWS performs an IKE rekey.
              returned: when provided by EC2
              type: int
            replay_window_size:
              description: The number of packets in an IKE replay window.
              returned: when provided by EC2
              type: int
            startup_action:
              description: The action to take when establishing the VPN tunnel.
              returned: when provided by EC2
              type: str
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
from ansible_collections.amazon.aws.plugins.module_utils.transformation import scrub_none_parameters

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import ansible_dict_to_string_filter_list
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    ec2_tag_methods,
    reconcile_ec2_tags,
    require_resulting_tag_limit,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.validation import require_non_blank
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    custom_waiter,
    require_positive_wait_bounds,
    run_waiter,
)

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
    "phase1_lifetime_seconds": "Phase1LifetimeSeconds",
    "phase2_lifetime_seconds": "Phase2LifetimeSeconds",
    "rekey_margin_time_seconds": "RekeyMarginTimeSeconds",
    "rekey_fuzz_percentage": "RekeyFuzzPercentage",
    "replay_window_size": "ReplayWindowSize",
    "dpd_timeout_seconds": "DPDTimeoutSeconds",
    "dpd_timeout_action": "DPDTimeoutAction",
    "startup_action": "StartupAction",
    "enable_tunnel_lifecycle_control": "EnableTunnelLifecycleControl",
    "log_options": "LogOptions",
}

# EC2 uses different key casing in requests and responses.
TUNNEL_RESPONSE_FIELDS = {
    "IKEVersions": "IkeVersions",
    "DPDTimeoutSeconds": "DpdTimeoutSeconds",
    "DPDTimeoutAction": "DpdTimeoutAction",
}

# Live: EC2 rejects phase 2 lifetimes above phase 1 and rekey margins above half of phase 2.
TIMER_FIELDS = ("Phase1LifetimeSeconds", "Phase2LifetimeSeconds", "RekeyMarginTimeSeconds")

# Live: EC2 rejects values outside these ranges with InvalidParameterValue.
TUNNEL_RANGES = {
    "phase1_lifetime_seconds": (900, 28800),
    "phase2_lifetime_seconds": (900, 3600),
    "rekey_margin_time_seconds": (60, None),
    "rekey_fuzz_percentage": (0, 100),
    "replay_window_size": (64, 2048),
    "dpd_timeout_seconds": (30, None),
}

LOG_FIELDS = {
    "log_enabled": "LogEnabled",
    "log_group_arn": "LogGroupArn",
    "log_output_format": "LogOutputFormat",
    "bgp_log_enabled": "BgpLogEnabled",
    "bgp_log_group_arn": "BgpLogGroupArn",
    "bgp_log_output_format": "BgpLogOutputFormat",
}

# EC2 omits a log option that was never set; these are its AWS defaults.
LOG_DEFAULTS = {"LogEnabled": False, "LogOutputFormat": "json", "BgpLogEnabled": False, "BgpLogOutputFormat": "json"}

TUNNEL_CHOICES = {
    "ike_versions": ["ikev1", "ikev2"],
    "phase1_encryption_algorithms": ["AES128", "AES256", "AES128-GCM-16", "AES256-GCM-16"],
    "phase2_encryption_algorithms": ["AES128", "AES256", "AES128-GCM-16", "AES256-GCM-16"],
    "phase1_integrity_algorithms": ["SHA1", "SHA2-256", "SHA2-384", "SHA2-512"],
    "phase2_integrity_algorithms": ["SHA1", "SHA2-256", "SHA2-384", "SHA2-512"],
    "phase1_dh_group_numbers": [2, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
    "phase2_dh_group_numbers": [2, 5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
}

# EC2 omits a tunnel option that was never set; a list option's AWS default permits every choice. Live, EC2 returns
# every value once set, even one equal to its default. DPDTimeoutSeconds has no entry: the EC2 API documents both 30
# and 40 as its default, so a supplied value is sent once to a tunnel where it was never set.
TUNNEL_DEFAULTS = {
    **{TUNNEL_FIELDS[name]: set(choices) for name, choices in TUNNEL_CHOICES.items()},
    "Phase1LifetimeSeconds": 28800,
    "Phase2LifetimeSeconds": 3600,
    "RekeyMarginTimeSeconds": 270,
    "RekeyFuzzPercentage": 100,
    "ReplayWindowSize": 1024,
    "DPDTimeoutAction": "clear",
    "StartupAction": "add",
    "EnableTunnelLifecycleControl": False,
}


RESERVED_TUNNEL_IPV4_NETWORKS = {f"169.254.{index}.0/30" for index in range(6)} | {"169.254.169.252/30"}


def normalize_connection(connection):
    result = deepcopy(connection)
    result.pop("CustomerGatewayConfiguration", None)

    for tunnel in result.get("Options", {}).get("TunnelOptions") or []:
        tunnel.pop("PreSharedKey", None)

    tags = boto3_tag_list_to_ansible_dict(result.pop("Tags", None) or [])
    result = camel_dict_to_snake_dict(result)
    result["tags"] = tags

    return result


def validate_connection(module, connection, changed=False):
    if (
        not isinstance(connection, dict)
        or not connection.get("VpnConnectionId")
        or not connection.get("State")
        or not isinstance(connection.get("Options"), dict)
    ):
        module.fail_json(changed=changed, msg="EC2 returned an invalid VPN connection")

    routes = connection.get("Routes", [])
    if not isinstance(routes, list) or any(
        not isinstance(route, dict) or not route.get("DestinationCidrBlock") for route in routes
    ):
        module.fail_json(changed=changed, msg="EC2 returned invalid VPN connection routes")

    tunnels = connection["Options"].get("TunnelOptions")
    if tunnels is not None and (
        not isinstance(tunnels, list) or any(not isinstance(tunnel, dict) for tunnel in tunnels)
    ):
        module.fail_json(changed=changed, msg="EC2 returned invalid VPN connection tunnel options")

    return connection


def find_connection(client, module, connection_id=None, changed=False):
    """Describe the connection; changed reports whether it was already modified, for failure results."""
    connection_id = connection_id or module.params["vpn_connection_id"]
    filters = module.params["filters"]

    if module.params["name"]:
        filters = {"tag:Name": module.params["name"]}

    request = (
        {"VpnConnectionIds": [connection_id]}
        if connection_id
        else {"Filters": ansible_dict_to_string_filter_list(filters)}
    )

    require_client_methods(module, client, "EC2", {"describe_vpn_connections": tuple(request)}, changed=changed)
    try:
        # DescribeVpnConnections has no pagination in the EC2 API.
        response = client.describe_vpn_connections(**request, aws_retry=True)
    except is_boto3_error_code("InvalidVpnConnectionID.NotFound"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            changed=changed,
            msg=f"Unable to describe VPN connection {connection_id or module.params['name'] or filters}",
        )

    connections = response.get("VpnConnections")
    if not isinstance(connections, list):
        module.fail_json(changed=changed, msg="EC2 returned an invalid VPN connection list")

    matches = []
    for item in connections:
        if isinstance(item, dict) and item.get("State") == "deleted":
            continue

        matches.append(validate_connection(module, item, changed=changed))

    if not connection_id and module.params["name"]:
        # The tag filter treats * and ? as wildcards, so keep only the exact name.
        matches = [
            match
            for match in matches
            if boto3_tag_list_to_ansible_dict(match.get("Tags") or []).get("Name") == module.params["name"]
        ]

    if len(matches) > 1:
        module.fail_json(changed=changed, msg="Multiple VPN connections matched; select a unique name, ID, or filters")

    return matches[0] if matches else None


def wait_for_connection(client, module, connection_id, changed=False):
    """Wait for the connection; changed reports whether it was already modified, for failure results."""
    run_waiter(
        module,
        client.get_waiter("vpn_connection_available"),
        f"Unable to wait for VPN connection {connection_id} to become available",
        changed=changed,
        VpnConnectionIds=[connection_id],
    )


def wait_for_connection_deleted(client, module, connection_id, changed=False):
    """Wait for deletion; changed reports whether the connection was already modified, for failure results."""
    waiter_name = "VPNConnectionDeleted"
    # The botocore vpn_connection_deleted acceptors, plus success once EC2 no longer reports the connection.
    model = {
        waiter_name: {
            "operation": "DescribeVpnConnections",
            # Required model defaults; run_waiter applies the user's wait bounds.
            "delay": 15,
            "maxAttempts": 40,
            "acceptors": [
                {
                    "state": "success",
                    "matcher": "pathAll",
                    "argument": "VpnConnections[].State",
                    "expected": "deleted",
                },
                {
                    "state": "failure",
                    "matcher": "pathAny",
                    "argument": "VpnConnections[].State",
                    "expected": "pending",
                },
                {
                    "state": "success",
                    "matcher": "error",
                    "expected": "InvalidVpnConnectionID.NotFound",
                },
            ],
        },
    }
    run_waiter(
        module,
        custom_waiter(client, model, waiter_name),
        f"Unable to wait for VPN connection {connection_id} to become deleted",
        changed=changed,
        VpnConnectionIds=[connection_id],
    )


def tunnel_request(options):
    result = {}

    for name, field in TUNNEL_FIELDS.items():
        value = options.get(name)
        if name == "log_options" and value is not None:
            cloud_watch = scrub_none_parameters(
                {LOG_FIELDS[key]: item for key, item in (value.get("cloud_watch_log_options") or {}).items()}
            )
            value = {"CloudWatchLogOptions": cloud_watch} if cloud_watch else None

        if value is not None:
            if name in TUNNEL_CHOICES:
                value = [{"Value": item} for item in sorted(set(value))]

            result[field] = value

    return result


def valid_pre_shared_key(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9._]{8,64}", value)) and not value.startswith("0")


def endpoints_unassigned(connection):
    current = connection["Options"].get("TunnelOptions") or []
    return connection["State"] == "pending" and (
        len(current) < 2 or any(not tunnel.get("OutsideIpAddress") for tunnel in current)
    )


def storage_targets(module, connection):
    """Return the outside IPs of tunnels whose keys are not stored as pre_shared_key_storage requests."""
    storage = module.params["pre_shared_key_storage"]
    if storage is None:
        return []

    if module.check_mode and endpoints_unassigned(connection):
        # As in tunnel_deltas, an unresolved target that must never reach a modifying SDK call.
        return [None]

    current = connection["Options"].get("TunnelOptions") or []
    if not current:
        module.fail_json(msg="EC2 did not return the requested tunnels")

    targets = []
    for tunnel in current:
        # Live: EC2 returns a tunnel's key only while the VPN service stores it, never from Secrets Manager.
        key = tunnel.get("PreSharedKey")
        if ("Standard" if isinstance(key, str) and key else "SecretsManager") == storage:
            continue

        if not tunnel.get("OutsideIpAddress"):
            module.fail_json(msg="EC2 did not return a tunnel outside IP address")

        targets.append(tunnel["OutsideIpAddress"])

    return targets


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

    if module.check_mode and endpoints_unassigned(connection):
        # Predict supplied changes until EC2 assigns the endpoints. These unresolved
        # targets are check-mode only and must never reach a modifying SDK call.
        requests = [(tunnel.get("outside_ip_address"), tunnel_request(tunnel)) for tunnel in desired_tunnels]
        return [(outside_ip, request) for outside_ip, request in requests if request]

    sorted_current = []
    if len(desired_tunnels) > 1 and not any(explicit) and current:
        try:
            sorted_current = sorted(current, key=lambda tunnel: int(ipaddress.ip_address(tunnel["OutsideIpAddress"])))
        except (KeyError, ValueError):
            module.fail_json(msg="EC2 returned an invalid tunnel outside IP address")

    requests = []
    for index, desired in enumerate(desired_tunnels):
        if desired.get("outside_ip_address"):
            requests.append(desired)
            continue

        if not current:
            module.fail_json(msg="EC2 did not return the requested tunnels")

        targets = current
        if len(desired_tunnels) > 1:
            if index >= len(sorted_current):
                module.fail_json(msg="EC2 did not return the requested tunnel")

            targets = [sorted_current[index]]

        for tunnel in targets:
            requests.append(dict(desired, outside_ip_address=tunnel.get("OutsideIpAddress")))

    changes = []
    for desired in requests:
        outside_ip = desired.get("outside_ip_address")
        if not outside_ip:
            module.fail_json(msg="EC2 did not return a tunnel outside IP address")

        matches = [tunnel for tunnel in current if tunnel.get("OutsideIpAddress") == outside_ip]
        if len(matches) != 1:
            module.fail_json(msg=f"No unique tunnel with outside IP {outside_ip} on {connection['VpnConnectionId']}")

        tunnel = matches[0]
        delta = {}
        for field, value in tunnel_request(desired).items():
            actual = tunnel.get(TUNNEL_RESPONSE_FIELDS.get(field, field))
            if field == "PreSharedKey":
                usable = isinstance(actual, str) and bool(actual)
                if not usable and module.params["pre_shared_key_storage"] != "Standard":
                    module.fail_json(
                        msg=f"Cannot compare pre_shared_key for VPN connection {connection['VpnConnectionId']} "
                        f"tunnel {outside_ip}; EC2 did not return a usable current key. "
                        "Omit pre_shared_key to leave it unchanged, or set pre_shared_key_storage=Standard "
                        "to replace it."
                    )

                # Live: the update that moves a key out of Secrets Manager also sets the supplied key.
                equal = usable and secrets.compare_digest(value.encode("utf-8"), actual.encode("utf-8"))
            elif field == "LogOptions":
                cloud_watch = actual.get("CloudWatchLogOptions") if isinstance(actual, dict) else actual
                if cloud_watch is not None and not isinstance(cloud_watch, dict):
                    module.fail_json(
                        msg=f"EC2 returned invalid LogOptions for VPN connection {connection['VpnConnectionId']} "
                        f"tunnel {outside_ip}"
                    )

                # Live: EC2 keeps the log fields an update omits, so only the supplied ones are compared and sent.
                cloud_watch = cloud_watch or {}
                equal = all(
                    item == (LOG_DEFAULTS.get(key) if cloud_watch.get(key) is None else cloud_watch[key])
                    for key, item in value["CloudWatchLogOptions"].items()
                )
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

                current_values = TUNNEL_DEFAULTS[field] if actual is None else {item["Value"] for item in actual}
                equal = {item["Value"] for item in value} == current_values
            else:
                equal = value == (TUNNEL_DEFAULTS.get(field) if actual is None else actual)

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

        if any(field in delta for field in TIMER_FIELDS):
            require_valid_timers(module, connection, tunnel, delta)
            # Live: EC2 checks the timers in a request against the AWS defaults of those it omits, not the tunnel's
            # current values, so a timer change also resends the timers already set on the tunnel.
            delta.update(
                {field: tunnel[field] for field in TIMER_FIELDS if field not in delta and tunnel.get(field) is not None}
            )

        if delta:
            changes.append((outside_ip, delta))

    return changes


def require_valid_timers(module, connection, tunnel, delta):
    """Fail before any write when a tunnel's resulting lifetimes and rekey margin break the rules EC2 enforces."""
    timers = []
    for field in TIMER_FIELDS:
        value = delta[field] if field in delta else tunnel.get(field)
        if value is None:
            value = TUNNEL_DEFAULTS[field]

        if not isinstance(value, int) or isinstance(value, bool):
            module.fail_json(
                msg=f"EC2 returned invalid {field} for VPN connection {connection['VpnConnectionId']} "
                f"tunnel {tunnel['OutsideIpAddress']}"
            )

        timers.append(value)

    # Live: EC2 accepts equal lifetimes and a rekey margin of exactly half the phase 2 lifetime.
    phase1, phase2, margin = timers
    problems = []
    if phase2 > phase1:
        problems.append(f"phase2_lifetime_seconds ({phase2}) must not exceed phase1_lifetime_seconds ({phase1})")

    if margin * 2 > phase2:
        problems.append(
            f"rekey_margin_time_seconds ({margin}) must not exceed half of phase2_lifetime_seconds ({phase2})"
        )

    if problems:
        module.fail_json(
            msg=f"Cannot update VPN connection {connection['VpnConnectionId']} tunnel {tunnel['OutsideIpAddress']}: "
            + "; ".join(problems)
        )


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

    require_non_blank(module, module.params["name"], "name")

    if module.params["filters"] is not None and not module.params["filters"]:
        module.fail_json(msg="filters must not be empty")

    if module.params["vpn_connection_id"] is not None and not module.params["vpn_connection_id"]:
        module.fail_json(msg="vpn_connection_id must not be empty")

    if module.params["state"] == "absent":
        return

    # Older botocore cannot send these options, and before 1.40.71 it drops the returned TunnelBandwidth.
    if module.params["pre_shared_key_storage"] is not None:
        module.require_botocore_at_least("1.38.24", reason="for pre_shared_key_storage")

    if module.params["tunnel_bandwidth"] is not None:
        module.require_botocore_at_least("1.40.71", reason="for tunnel_bandwidth")

    if module.params["vpn_concentrator_id"] is not None:
        module.require_botocore_at_least("1.40.76", reason="for vpn_concentrator_id")

    tunnels = module.params["tunnel_options"] or []
    bgp_options = sorted(
        {
            name
            for tunnel in tunnels
            for name, value in ((tunnel.get("log_options") or {}).get("cloud_watch_log_options") or {}).items()
            if name.startswith("bgp_") and value is not None
        }
    )
    if bgp_options:
        module.require_botocore_at_least("1.41.1", reason=f"for {bgp_options[0]}")

    # Live: EC2 treats a whitespace-only concentrator or attachment ID as omitted, so a rerun could never match it.
    for name in ("transport_transit_gateway_attachment_id", "vpn_concentrator_id"):
        require_non_blank(module, module.params[name], name)

    if (
        module.params["name"]
        and module.params["tags"] is not None
        and module.params["tags"].get("Name", module.params["name"]) != module.params["name"]
    ):
        module.fail_json(msg="tags.Name must match name")

    # Validate the tags, including the Name tag, before any AWS call.
    desired_tags(module, {})

    for name in CONNECTION_FIELDS:
        value = module.params[name]
        if value is not None:
            module.params[name] = str(validate_network(module, value, name, 4 if "ipv4" in name else 6))

    if module.params["routes"] is not None:
        module.params["routes"] = sorted(
            {str(validate_network(module, route, "routes", 4)) for route in module.params["routes"]}
        )

    if len(tunnels) > 2:
        module.fail_json(msg="tunnel_options must contain at most two entries")

    inside_networks = set()
    for tunnel in tunnels:
        for name in TUNNEL_CHOICES:
            if tunnel.get(name) == []:
                module.fail_json(msg=f"tunnel_options[].{name} must not be empty")

        # A later tunnel update can follow other writes, so out-of-range values fail before any of them.
        for name, (low, high) in TUNNEL_RANGES.items():
            value = tunnel.get(name)
            if value is not None and (value < low or (high is not None and value > high)):
                limit = f"{low} or greater" if high is None else f"between {low} and {high}"
                module.fail_json(msg=f"tunnel_options[].{name} must be {limit}")

        key = tunnel.get("pre_shared_key")
        if key is not None and not valid_pre_shared_key(key):
            module.fail_json(msg="Invalid tunnel pre_shared_key format")

        # Live: EC2 never returns a key stored in Secrets Manager, so a rerun could not compare it.
        if key is not None and module.params["pre_shared_key_storage"] == "SecretsManager":
            module.fail_json(
                msg="tunnel_options[].pre_shared_key cannot be used with pre_shared_key_storage=SecretsManager "
                "because EC2 does not return keys stored in Secrets Manager for comparison"
            )

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

    require_valid_tags(module, tags, 50, ec2=True)
    current_tags = boto3_tag_list_to_ansible_dict(current.get("Tags") or [])
    tags_to_set, tag_keys_to_unset = compare_aws_tags(current_tags, tags, purge)
    require_resulting_tag_limit(module, current_tags, tags_to_set, tag_keys_to_unset, 50, "VPN connection")
    return tags_to_set, tag_keys_to_unset


def validate_configuration(module, connection=None, changed=False):
    # A VPN concentrator attaches the connection to its transit gateway; live, EC2 then omits TransitGatewayId.
    if connection is not None:
        options = connection["Options"]
        static_only = options.get("StaticRoutesOnly") or False
        transit_gateway = connection.get("TransitGatewayId") or connection.get("VpnConcentratorId")
        family = options.get("TunnelInsideIpVersion") or "ipv4"
    else:
        static_only = module.params["static_only"] or False
        transit_gateway = module.params["transit_gateway_id"] or module.params["vpn_concentrator_id"]
        family = module.params["tunnel_inside_ip_version"] or "ipv4"

    if module.params["routes"] and (not static_only or transit_gateway):
        module.fail_json(
            changed=changed,
            msg="Static routes require static_only=true and a virtual private gateway connection",
        )

    if family == "ipv6" and not transit_gateway:
        module.fail_json(changed=changed, msg="IPv6 VPN connections require a transit gateway")

    for tunnel in module.params["tunnel_options"] or []:
        if tunnel.get("tunnel_inside_cidr") is not None and family != "ipv4":
            module.fail_json(changed=changed, msg="tunnel_inside_cidr requires tunnel_inside_ip_version=ipv4")

        if tunnel.get("tunnel_inside_ipv6_cidr") is not None and family != "ipv6":
            module.fail_json(changed=changed, msg="tunnel_inside_ipv6_cidr requires tunnel_inside_ip_version=ipv6")

    # EC2 rejects IPv6 network CIDRs on an IPv4 connection, and omits them from it.
    for name in ("local_ipv6_network_cidr", "remote_ipv6_network_cidr"):
        if module.params[name] is not None and family != "ipv6":
            module.fail_json(changed=changed, msg=f"{name} requires tunnel_inside_ip_version=ipv6")

    if connection is not None:
        # No EC2 modify operation takes the last four. A missing acceleration or address type is the AWS default.
        immutable = {
            "customer_gateway_id": connection.get("CustomerGatewayId"),
            "vpn_gateway_id": connection.get("VpnGatewayId"),
            "transit_gateway_id": connection.get("TransitGatewayId"),
            "static_only": static_only,
            "tunnel_inside_ip_version": family,
            "enable_acceleration": options.get("EnableAcceleration") or False,
            "outside_ip_address_type": options.get("OutsideIpAddressType") or "PublicIpv4",
            "transport_transit_gateway_attachment_id": options.get("TransportTransitGatewayAttachmentId"),
            "vpn_concentrator_id": connection.get("VpnConcentratorId"),
        }

        for name, actual in immutable.items():
            if module.params[name] is not None and module.params[name] != actual:
                module.fail_json(
                    changed=changed, msg=f"Cannot change {name} on an existing VPN connection with this module"
                )


def create_connection(client, module):
    if module.params["vpn_connection_id"] is not None or module.params["filters"] is not None:
        selector = "vpn_connection_id" if module.params["vpn_connection_id"] is not None else "filters"
        module.fail_json(
            msg=f"No VPN connection matched {selector}. This selector cannot create a connection; "
            "use name instead of the selector to create a VPN connection."
        )

    # EC2 treats a whitespace-only gateway ID as omitted, so it counts as missing here too.
    gateways = ("vpn_gateway_id", "transit_gateway_id", "vpn_concentrator_id")
    if (
        not module.params["name"]
        or not (module.params["customer_gateway_id"] or "").strip()
        or not any((module.params[name] or "").strip() for name in gateways)
    ):
        module.fail_json(
            msg="Creation requires name, customer_gateway_id, and one of vpn_gateway_id, transit_gateway_id, "
            "or vpn_concentrator_id"
        )

    if any(tunnel.get("outside_ip_address") for tunnel in module.params["tunnel_options"] or []):
        module.fail_json(msg="outside_ip_address cannot be specified during creation")

    validate_configuration(module)
    tags = desired_tags(module, {})[0]

    options = {field: module.params[name] for name, field in CONNECTION_FIELDS.items()}
    options.update(
        EnableAcceleration=module.params["enable_acceleration"],
        OutsideIpAddressType=module.params["outside_ip_address_type"],
        StaticRoutesOnly=module.params["static_only"],
        TransportTransitGatewayAttachmentId=module.params["transport_transit_gateway_attachment_id"],
        TunnelBandwidth=module.params["tunnel_bandwidth"],
        TunnelInsideIpVersion=module.params["tunnel_inside_ip_version"],
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
            "VpnConcentratorId": module.params["vpn_concentrator_id"],
            "PreSharedKeyStorage": module.params["pre_shared_key_storage"],
            "Options": options,
            "TagSpecifications": [{"ResourceType": "vpn-connection", "Tags": ansible_dict_to_boto3_tag_list(tags)}],
        }
    )

    if module.check_mode:
        module.exit_json(changed=True, vpn_connection={})

    methods = {"create_vpn_connection": tuple(request)}
    if module.params["routes"]:
        # Routes are added after creation, so their support is checked before creating anything.
        methods["create_vpn_connection_route"] = ("DestinationCidrBlock", "VpnConnectionId")

    require_client_methods(module, client, "EC2", methods)
    try:
        response = client.create_vpn_connection(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to create VPN connection {module.params['name']}")

    connection = validate_connection(module, response.get("VpnConnection"), changed=True)
    wait_for_connection(client, module, connection["VpnConnectionId"], changed=True)

    return read_connection(client, module, connection["VpnConnectionId"], changed=True)


def read_connection(client, module, connection_id, changed=False):
    connection = find_connection(client, module, connection_id, changed=changed)
    if connection is None:
        module.fail_json(changed=changed, msg=f"VPN connection {connection_id} disappeared while being managed")

    return connection


def ensure_present(client, module, connection):
    changed = connection is None
    if connection is None:
        connection = create_connection(client, module)

    # Failures after the first modification report changed=True.
    mutated = changed and not module.check_mode
    connection_id = connection["VpnConnectionId"]
    if connection["State"] == "deleting":
        module.fail_json(
            changed=mutated,
            msg=f"VPN connection {connection_id} is deleting; wait for deletion before creating a replacement",
        )

    if connection["State"] != "available" and not module.check_mode:
        wait_for_connection(client, module, connection_id, changed=mutated)
        connection = read_connection(client, module, connection_id, changed=mutated)

    validate_configuration(module, connection, changed=mutated)

    # Creation already submitted tunnel options and key storage before EC2 allocated their outside IPs.
    tunnels = [] if changed else tunnel_deltas(module, connection)
    stored = [] if changed else storage_targets(module, connection)
    # EC2 changes key storage per tunnel, so each tunnel is modified once with its other changes.
    tunnels += [(outside_ip, {}) for outside_ip in stored if outside_ip not in dict(tunnels)]
    options = {
        field: module.params[name]
        for name, field in CONNECTION_FIELDS.items()
        if module.params[name] is not None and module.params[name] != connection["Options"].get(field)
    }
    # EC2 documents standard for a connection without a tunnel bandwidth setting.
    bandwidth = module.params["tunnel_bandwidth"]
    if bandwidth is not None and bandwidth != (connection["Options"].get("TunnelBandwidth") or "standard"):
        options["TunnelBandwidth"] = bandwidth

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
    add_routes = set()
    remove_routes = set()
    pending_removals = set()
    if routes is not None:
        add_routes = set(routes) - current_routes
        if module.params["purge_routes"]:
            remove_routes = current_routes - set(routes)
            pending_removals = deleting_routes - set(routes)

    # Requested routes were normalized by validate_inputs; validate the routes EC2 returned.
    for route in remove_routes | pending_removals:
        validate_network(module, route, "Route destination", 4)

    updated = bool(tunnels or options or tags_to_set or tags_to_remove or add_routes or remove_routes)
    changed |= updated
    if module.check_mode:
        module.exit_json(changed=changed, vpn_connection=normalize_connection(connection))

    # Every write is checked before the first one, so an older botocore fails without modifying anything.
    methods = {}
    if options:
        methods["modify_vpn_connection_options"] = ("VpnConnectionId",) + tuple(options)

    # Skipping applies only to a lifecycle control change and never counts as a change; live, false replaces the
    # endpoint just as omitting it does, so only true is sent.
    skipped = {
        outside_ip
        for outside_ip, delta in tunnels
        if module.params["skip_tunnel_replacement"] and "EnableTunnelLifecycleControl" in delta
    }
    if tunnels:
        methods["modify_vpn_tunnel_options"] = ("TunnelOptions", "VpnConnectionId", "VpnTunnelOutsideIpAddress")
        if stored:
            methods["modify_vpn_tunnel_options"] += ("PreSharedKeyStorage",)

        if skipped:
            methods["modify_vpn_tunnel_options"] += ("SkipTunnelReplacement",)

    if remove_routes:
        methods["delete_vpn_connection_route"] = ("DestinationCidrBlock", "VpnConnectionId")

    if add_routes:
        methods["create_vpn_connection_route"] = ("DestinationCidrBlock", "VpnConnectionId")

    methods.update(ec2_tag_methods(tags_to_set, tags_to_remove))
    require_client_methods(module, client, "EC2", methods, changed=mutated)

    pending_routes = {
        route["DestinationCidrBlock"]
        for route in connection.get("Routes", [])
        if route.get("State") == "pending" and route["DestinationCidrBlock"] in (routes or [])
    }
    for route in sorted(pending_routes):
        wait_for_route_available(client, module, connection_id, route, changed=mutated)

    for route in sorted((add_routes & deleting_routes) | pending_removals):
        wait_for_route_deleted(client, module, connection_id, route, changed=mutated)

    if options:
        try:
            client.modify_vpn_connection_options(VpnConnectionId=connection_id, **options, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=mutated, msg=f"Unable to modify options for VPN connection {connection_id}")

        mutated = True
        wait_for_connection(client, module, connection_id, changed=True)

    for outside_ip, delta in tunnels:
        storage = {"PreSharedKeyStorage": module.params["pre_shared_key_storage"]} if outside_ip in stored else {}
        requests = [(delta, storage)]
        if outside_ip in skipped:
            # Live: EC2 rejects SkipTunnelReplacement with other changes such as StartupAction, so lifecycle control
            # changes first on its own, which EC2 applies without entering modifying.
            rest = {field: value for field, value in delta.items() if field != "EnableTunnelLifecycleControl"}
            lifecycle = {"EnableTunnelLifecycleControl": delta["EnableTunnelLifecycleControl"]}
            requests = [(lifecycle, {"SkipTunnelReplacement": True})] + ([(rest, storage)] if rest or storage else [])

        for options, parameters in requests:
            try:
                client.modify_vpn_tunnel_options(
                    VpnConnectionId=connection_id,
                    VpnTunnelOutsideIpAddress=outside_ip,
                    TunnelOptions=options,
                    **parameters,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e, changed=mutated, msg=f"Unable to modify VPN connection {connection_id} tunnel {outside_ip}"
                )

            mutated = True
            wait_for_connection(client, module, connection_id, changed=True)

    reconcile_routes(client, module, connection_id, add_routes, remove_routes, changed=mutated)
    mutated = mutated or bool(add_routes or remove_routes)
    reconcile_ec2_tags(module, client, [connection_id], tags_to_set, tags_to_remove, "VPN connection", changed=mutated)
    mutated = mutated or bool(tags_to_set or tags_to_remove)

    if updated or pending_routes or pending_removals:
        connection = read_connection(client, module, connection_id, changed=mutated)

    module.exit_json(changed=changed, vpn_connection=normalize_connection(connection))


def wait_for_route_deleted(client, module, connection_id, route, changed=False):
    wait_for_route_state(client, module, connection_id, route, "deleted", changed=changed)


def wait_for_route_available(client, module, connection_id, route, changed=False):
    wait_for_route_state(client, module, connection_id, route, "available", changed=changed)


def wait_for_route_state(client, module, connection_id, route, state, changed=False):
    """Wait for a route state; changed reports whether the connection was already modified, for failure results."""
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
        custom_waiter(client, model, waiter_name),
        f"Unable to wait for route {route} to become {state} on VPN connection {connection_id}",
        changed=changed,
        VpnConnectionIds=[connection_id],
    )


def reconcile_routes(client, module, connection_id, additions, removals, changed=False):
    """Apply route changes; changed reports whether the connection was already modified, for failure results."""
    for route in sorted(removals):
        try:
            client.delete_vpn_connection_route(
                VpnConnectionId=connection_id, DestinationCidrBlock=route, aws_retry=True
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e, changed=changed, msg=f"Unable to delete route {route} from VPN connection {connection_id}"
            )

        changed = True
        wait_for_route_deleted(client, module, connection_id, route, changed=True)

    for route in sorted(additions):
        try:
            client.create_vpn_connection_route(
                VpnConnectionId=connection_id, DestinationCidrBlock=route, aws_retry=True
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e, changed=changed, msg=f"Unable to create route {route} on VPN connection {connection_id}"
            )

        changed = True
        wait_for_route_available(client, module, connection_id, route, changed=True)


def ensure_absent(client, module, connection):
    if connection is None:
        module.exit_json(changed=False, vpn_connection={})

    changed = connection["State"] != "deleting"
    if module.check_mode:
        module.exit_json(changed=changed, vpn_connection={})

    connection_id = connection["VpnConnectionId"]
    if changed:
        # The VpnConnectionDeleted waiter fails while a connection is pending, so let creation finish first.
        if connection["State"] == "pending":
            wait_for_connection(client, module, connection_id)

        require_client_methods(module, client, "EC2", {"delete_vpn_connection": ("VpnConnectionId",)})
        try:
            client.delete_vpn_connection(VpnConnectionId=connection_id, aws_retry=True)
        except is_boto3_error_code("InvalidVpnConnectionID.NotFound"):
            module.exit_json(changed=False, vpn_connection={})
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to delete VPN connection {connection_id}")

    wait_for_connection_deleted(client, module, connection_id, changed=changed)
    module.exit_json(changed=changed, vpn_connection={})


def main():
    log_spec = {
        "log_enabled": {"type": "bool"},
        "log_group_arn": {"type": "str"},
        "log_output_format": {"type": "str", "choices": ["json", "text"]},
        "bgp_log_enabled": {"type": "bool"},
        "bgp_log_group_arn": {"type": "str"},
        "bgp_log_output_format": {"type": "str", "choices": ["json", "text"]},
    }
    tunnel_spec = {
        "outside_ip_address": {"type": "str"},
        "tunnel_inside_cidr": {"type": "str"},
        "tunnel_inside_ipv6_cidr": {"type": "str"},
        "pre_shared_key": {"type": "str", "no_log": True},
        "phase1_lifetime_seconds": {"type": "int"},
        "phase2_lifetime_seconds": {"type": "int"},
        # Rekey timers are not secrets.
        "rekey_margin_time_seconds": {"type": "int", "no_log": False},
        "rekey_fuzz_percentage": {"type": "int", "no_log": False},
        "replay_window_size": {"type": "int"},
        "dpd_timeout_seconds": {"type": "int"},
        "dpd_timeout_action": {"type": "str", "choices": ["clear", "none", "restart"]},
        "startup_action": {"type": "str", "choices": ["add", "start"]},
        "enable_tunnel_lifecycle_control": {"type": "bool"},
        "log_options": {
            "type": "dict",
            "options": {"cloud_watch_log_options": {"type": "dict", "options": log_spec}},
        },
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
        "vpn_concentrator_id": {"type": "str"},
        "connection_type": {
            "type": "str",
            "choices": ["ipsec.1"],
            "default": "ipsec.1",
        },
        "enable_acceleration": {"type": "bool"},
        "outside_ip_address_type": {"type": "str", "choices": ["PrivateIpv4", "PublicIpv4", "Ipv6"]},
        "transport_transit_gateway_attachment_id": {"type": "str"},
        "skip_tunnel_replacement": {"type": "bool"},
        "static_only": {"type": "bool"},
        "pre_shared_key_storage": {"type": "str", "choices": ["Standard", "SecretsManager"]},
        "tunnel_bandwidth": {"type": "str", "choices": ["standard", "large"]},
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

    # required_one_of counts only supplied keys, so an explicit null passes it.
    if all(module.params[option] is None for option in ("name", "vpn_connection_id", "filters")):
        module.fail_json(msg="one of the following is required: name, vpn_connection_id, filters")

    # A previous modification can still be settling when the connection waiter succeeds.
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["IncorrectState"]))
    connection = find_connection(client, module)

    if module.params["state"] == "present":
        ensure_present(client, module, connection)
    else:
        ensure_absent(client, module, connection)


if __name__ == "__main__":
    main()
