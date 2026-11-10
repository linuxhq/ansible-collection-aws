#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_type_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 instance types
description:
  - Gathers information about EC2 instance types.
  - This module maps to the EC2 C(DescribeInstanceTypes) API, the API behind
    C(aws ec2 describe-instance-types).
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 instance types.
      - Filter names and values are passed to the EC2
        C(DescribeInstanceTypes) API.
      - Boolean and numeric values, including list entries, are converted to strings.
    type: dict
  include_unsupported_in_region:
    description:
      - Whether to also return instance types that are not supported in the current region.
      - Requires botocore 1.43.6 or later.
    default: false
    type: bool
    version_added: "2.6.0"
  instance_types:
    description:
      - EC2 instance type names used to limit the result set.
      - This is sent as the C(instance-type) filter and takes precedence over an
        C(instance-type) key in O(filters), so wildcards such as C(t3.*) are supported.
      - An instance type that is not offered in the region results in no entry unless
        O(include_unsupported_in_region=true); no error is raised.
      - EC2 accepts at most 200 filter values in each call, so the unique entries in this list
        and the values in O(filters) must total at most 200.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only retrieves information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about all EC2 instance types
  linuxhq.aws.ec2_instance_type_info:

- name: Gather information about selected EC2 instance types
  linuxhq.aws.ec2_instance_type_info:
    instance_types:
      - t3.micro
      - m7i.large

- name: Gather information about current generation x86_64 instance types
  linuxhq.aws.ec2_instance_type_info:
    filters:
      current-generation: true
      processor-info.supported-architecture:
        - x86_64

- name: Gather information about instance types with 2 or 4 default vCPUs
  linuxhq.aws.ec2_instance_type_info:
    filters:
      vcpu-info.default-vcpus:
        - 2
        - 4

- name: Gather information about an instance type outside the current region
  linuxhq.aws.ec2_instance_type_info:
    include_unsupported_in_region: true
    instance_types:
      - m1.small

- name: Gather information about burstable instance types
  linuxhq.aws.ec2_instance_type_info:
    filters:
      burstable-performance-supported: true
      instance-type:
        - t3.*
        - t4g.*
"""

RETURN = r"""
instance_types:
  description:
    - A list of EC2 instance type information.
  returned: always
  type: list
  elements: dict
  contains:
    auto_recovery_supported:
      description: Whether Amazon CloudWatch action based recovery is supported.
      returned: when available
      type: bool
    bare_metal:
      description: Whether the instance type is a bare metal instance type.
      returned: when available
      type: bool
    burstable_performance_supported:
      description: Whether the instance type is a burstable performance T instance type.
      returned: when available
      type: bool
    current_generation:
      description: Whether the instance type is current generation.
      returned: when available
      type: bool
    dedicated_hosts_supported:
      description: Whether Dedicated Hosts are supported on the instance type.
      returned: when available
      type: bool
    ebs_info:
      description: Amazon EBS settings for the instance type.
      returned: when available
      type: dict
      contains:
        attachment_limit_type:
          description: Indicates whether the instance type features a shared or dedicated Amazon EBS volume attachment limit.
          returned: when available
          type: str
        ebs_cards:
          description: Describes the EBS cards available for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            baseline_bandwidth_in_mbps:
              description: The baseline bandwidth performance for the EBS card, in Mbps.
              returned: when available
              type: int
            baseline_iops:
              description: The baseline IOPS performance for the EBS card.
              returned: when available
              type: int
            baseline_throughput_in_m_bps:
              description: The baseline throughput performance for the EBS card, in MBps.
              returned: when available
              type: float
            ebs_card_index:
              description: The index of the EBS card.
              returned: when available
              type: int
            maximum_bandwidth_in_mbps:
              description: The maximum bandwidth performance for the EBS card, in Mbps.
              returned: when available
              type: int
            maximum_iops:
              description: The maximum IOPS performance for the EBS card.
              returned: when available
              type: int
            maximum_throughput_in_m_bps:
              description: The maximum throughput performance for the EBS card, in MBps.
              returned: when available
              type: float
        ebs_optimized_info:
          description: Describes the optimized EBS performance for the instance type.
          returned: when available
          type: dict
          contains:
            baseline_bandwidth_in_mbps:
              description: The baseline bandwidth performance for an EBS-optimized instance type, in Mbps.
              returned: when available
              type: int
            baseline_iops:
              description: The baseline input/output storage operations per seconds for an EBS-optimized instance type.
              returned: when available
              type: int
            baseline_throughput_in_m_bps:
              description: The baseline throughput performance for an EBS-optimized instance type, in MB/s.
              returned: when available
              type: float
            maximum_bandwidth_in_mbps:
              description: The maximum bandwidth performance for an EBS-optimized instance type, in Mbps.
              returned: when available
              type: int
            maximum_iops:
              description: The maximum input/output storage operations per second for an EBS-optimized instance type.
              returned: when available
              type: int
            maximum_throughput_in_m_bps:
              description: The maximum throughput performance for an EBS-optimized instance type, in MB/s.
              returned: when available
              type: float
        ebs_optimized_support:
          description: Indicates whether the instance type is Amazon EBS-optimized.
          returned: when available
          type: str
        encryption_support:
          description: Indicates whether Amazon EBS encryption is supported.
          returned: when available
          type: str
        maximum_ebs_attachments:
          description: Indicates the maximum number of Amazon EBS volumes that can be attached to the instance type.
          returned: when available
          type: int
        maximum_ebs_cards:
          description: Indicates the number of EBS cards supported by the instance type.
          returned: when available
          type: int
        nvme_support:
          description: Indicates whether non-volatile memory express (NVMe) is supported.
          returned: when available
          type: str
    fpga_info:
      description: FPGA accelerator settings for the instance type.
      returned: when available
      type: dict
      contains:
        fpgas:
          description: Describes the FPGAs for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            count:
              description: The count of FPGA accelerators for the instance type.
              returned: when available
              type: int
            manufacturer:
              description: The manufacturer of the FPGA accelerator.
              returned: when available
              type: str
            memory_info:
              description: Describes the memory for the FPGA accelerator for the instance type.
              returned: when available
              type: dict
              contains:
                size_in_mi_b:
                  description: The size of the memory available to the FPGA accelerator, in MiB.
                  returned: when available
                  type: int
            name:
              description: The name of the FPGA accelerator.
              returned: when available
              type: str
        total_fpga_memory_in_mi_b:
          description: The total memory of all FPGA accelerators for the instance type.
          returned: when available
          type: int
    free_tier_eligible:
      description: Whether the instance type is eligible for the free tier.
      returned: when available
      type: bool
    gpu_info:
      description: GPU accelerator settings for the instance type.
      returned: when available
      type: dict
      contains:
        gpus:
          description: Describes the GPU accelerators for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            count:
              description: The number of GPUs for the instance type.
              returned: when available
              type: int
            gpu_partition_size:
              description: The size of each GPU as a fraction of a full GPU, between 0 (excluded) and 1 (included).
              returned: when available
              type: float
            logical_gpu_count:
              description: Total number of GPU devices of this type.
              returned: when available
              type: int
            manufacturer:
              description: The manufacturer of the GPU accelerator.
              returned: when available
              type: str
            memory_info:
              description: Describes the memory available to the GPU accelerator.
              returned: when available
              type: dict
              contains:
                size_in_mi_b:
                  description: The size of the memory available to the GPU accelerator, in MiB.
                  returned: when available
                  type: int
            name:
              description: The name of the GPU accelerator.
              returned: when available
              type: str
            workloads:
              description: A list of workload types this GPU supports.
              returned: when available
              type: list
              elements: str
        total_gpu_memory_in_mi_b:
          description: The total size of the memory for the GPU accelerators for the instance type, in MiB.
          returned: when available
          type: int
    hibernation_supported:
      description: Whether On-Demand hibernation is supported.
      returned: when available
      type: bool
    hypervisor:
      description: Hypervisor for the instance type.
      returned: when available
      type: str
    inference_accelerator_info:
      description: Inference accelerator settings for the instance type.
      returned: when available
      type: dict
      contains:
        accelerators:
          description: Describes the Inference accelerators for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            count:
              description: The number of Inference accelerators for the instance type.
              returned: when available
              type: int
            manufacturer:
              description: The manufacturer of the Inference accelerator.
              returned: when available
              type: str
            memory_info:
              description: Describes the memory available to the inference accelerator.
              returned: when available
              type: dict
              contains:
                size_in_mi_b:
                  description: The size of the memory available to the inference accelerator, in MiB.
                  returned: when available
                  type: int
            name:
              description: The name of the Inference accelerator.
              returned: when available
              type: str
        total_inference_memory_in_mi_b:
          description: The total size of the memory for the inference accelerators for the instance type, in MiB.
          returned: when available
          type: int
    instance_storage_info:
      description: Instance storage for the instance type.
      returned: when available
      type: dict
      contains:
        disks:
          description: Describes the disks that are available for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            count:
              description: The number of disks with this configuration.
              returned: when available
              type: int
            size_in_gb:
              description: The size of the disk in GB.
              returned: when available
              type: int
            type:
              description: The type of disk.
              returned: when available
              type: str
        encryption_support:
          description: Indicates whether data is encrypted at rest.
          returned: when available
          type: str
        nvme_support:
          description: Indicates whether non-volatile memory express (NVMe) is supported.
          returned: when available
          type: str
        total_size_in_gb:
          description: The total size of the disks, in GB.
          returned: when available
          type: int
    instance_storage_supported:
      description: Whether instance storage is supported.
      returned: when available
      type: bool
    instance_type:
      description: Name of the instance type.
      returned: always
      type: str
    memory_info:
      description:
        - Memory for the instance type.
        - The size in MiB is returned as C(size_in_mi_b).
      returned: when available
      type: dict
      contains:
        size_in_mi_b:
          description: The size of the memory, in MiB.
          returned: when available
          type: int
    media_accelerator_info:
      description: Media accelerator settings for the instance type.
      returned: when available
      type: dict
      contains:
        accelerators:
          description: Describes the media accelerators for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            count:
              description: The number of media accelerators for the instance type.
              returned: when available
              type: int
            manufacturer:
              description: The manufacturer of the media accelerator.
              returned: when available
              type: str
            memory_info:
              description: Describes the memory available to the media accelerator.
              returned: when available
              type: dict
              contains:
                size_in_mi_b:
                  description: The size of the memory available to each media accelerator, in MiB.
                  returned: when available
                  type: int
            name:
              description: The name of the media accelerator.
              returned: when available
              type: str
        total_media_memory_in_mi_b:
          description: The total size of the memory for the media accelerators for the instance type, in MiB.
          returned: when available
          type: int
    network_info:
      description: Network settings for the instance type.
      returned: when available
      type: dict
      contains:
        bandwidth_weightings:
          description: A list of valid settings for configurable bandwidth weighting for the instance type, if supported.
          returned: when available
          type: list
          elements: str
        connection_tracking_configuration:
          description: Indicates conntrack information for the instance type.
          returned: when available
          type: dict
          contains:
            default_tcp_established_timeout:
              description: Default timeout (in seconds) for idle TCP connections in an established state.
              returned: when available
              type: int
            default_udp_stream_timeout:
              description:
                - Default timeout (in seconds) for idle UDP flows classified as streams which have seen more than one request-response transaction.
              returned: when available
              type: int
            default_udp_timeout:
              description:
                - Default timeout (in seconds) for idle UDP flows that have seen traffic only in a single direction or a single request-response transaction.
              returned: when available
              type: int
        default_network_card_index:
          description: The index of the default network card, starting at 0.
          returned: when available
          type: int
        efa_info:
          description: Describes the Elastic Fabric Adapters for the instance type.
          returned: when available
          type: dict
          contains:
            maximum_efa_interfaces:
              description: The maximum number of Elastic Fabric Adapters for the instance type.
              returned: when available
              type: int
        efa_supported:
          description: Indicates whether Elastic Fabric Adapter (EFA) is supported.
          returned: when available
          type: bool
        ena_srd_supported:
          description: Indicates whether the instance type supports ENA Express.
          returned: when available
          type: bool
        ena_support:
          description: Indicates whether Elastic Network Adapter (ENA) is supported.
          returned: when available
          type: str
        encryption_in_transit_supported:
          description: Indicates whether the instance type automatically encrypts in-transit traffic between instances.
          returned: when available
          type: bool
        flexible_ena_queues_support:
          description: Indicates whether changing the number of ENA queues is supported.
          returned: when available
          type: str
        ipv4_addresses_per_interface:
          description: The maximum number of IPv4 addresses per network interface.
          returned: when available
          type: int
        ipv4_addresses_per_secondary_interface:
          description: The maximum number of IPv4 addresses per secondary interface.
          returned: when available
          type: int
        ipv6_addresses_per_interface:
          description: The maximum number of IPv6 addresses per network interface.
          returned: when available
          type: int
        ipv6_supported:
          description: Indicates whether IPv6 is supported.
          returned: when available
          type: bool
        maximum_network_cards:
          description: The maximum number of physical network cards that can be allocated to the instance.
          returned: when available
          type: int
        maximum_network_interfaces:
          description: The maximum number of network interfaces for the instance type.
          returned: when available
          type: int
        maximum_secondary_network_interfaces:
          description: The maximum number of secondary interfaces for the instance type.
          returned: when available
          type: int
        network_cards:
          description: Describes the network cards for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            additional_flexible_network_interfaces:
              description:
                - The number of additional network interfaces that can be attached to an instance when using flexible Elastic Network Adapter (ENA) queues.
              returned: when available
              type: int
            baseline_bandwidth_in_gbps:
              description: The baseline network performance of the network card, in Gbps.
              returned: when available
              type: float
            default_ena_queue_count_per_interface:
              description: The default number of the ENA queues for each interface.
              returned: when available
              type: int
            interface_types:
              description: The supported interface types for the network card.
              returned: when available
              type: list
              elements: str
            maximum_ena_queue_count:
              description: The maximum number of the ENA queues.
              returned: when available
              type: int
            maximum_ena_queue_count_per_interface:
              description: The maximum number of the ENA queues for each interface.
              returned: when available
              type: int
            maximum_network_interfaces:
              description: The maximum number of network interfaces for the network card.
              returned: when available
              type: int
            network_card_index:
              description: The index of the network card.
              returned: when available
              type: int
            network_performance:
              description: The network performance of the network card.
              returned: when available
              type: str
            peak_bandwidth_in_gbps:
              description: The peak (burst) network performance of the network card, in Gbps.
              returned: when available
              type: float
        network_performance:
          description: The network performance.
          returned: when available
          type: str
        secondary_network_supported:
          description: Indicates whether secondary interface attachments from secondary network are supported.
          returned: when available
          type: bool
    neuron_info:
      description: Neuron accelerator settings for the instance type.
      returned: when available
      type: dict
      contains:
        neuron_devices:
          description: Describes the neuron accelerators for the instance type.
          returned: when available
          type: list
          elements: dict
          contains:
            core_info:
              description: Describes the cores available to each neuron accelerator.
              returned: when available
              type: dict
              contains:
                count:
                  description: The number of cores available to the neuron accelerator.
                  returned: when available
                  type: int
                version:
                  description: The version of the neuron accelerator.
                  returned: when available
                  type: int
            count:
              description: The number of neuron accelerators for the instance type.
              returned: when available
              type: int
            memory_info:
              description: Describes the memory available to each neuron accelerator.
              returned: when available
              type: dict
              contains:
                size_in_mi_b:
                  description: The size of the memory available to the neuron accelerator, in MiB.
                  returned: when available
                  type: int
            name:
              description: The name of the neuron accelerator.
              returned: when available
              type: str
        total_neuron_device_memory_in_mi_b:
          description: The total size of the memory for the neuron accelerators for the instance type, in MiB.
          returned: when available
          type: int
    nitro_enclaves_support:
      description: Whether Nitro Enclaves is supported.
      returned: when available
      type: str
    nitro_tpm_info:
      description: Supported NitroTPM versions for the instance type.
      returned: when available
      type: dict
      contains:
        supported_versions:
          description: Indicates the supported NitroTPM versions.
          returned: when available
          type: list
          elements: str
    nitro_tpm_support:
      description: Whether NitroTPM is supported.
      returned: when available
      type: str
    phc_support:
      description: Whether a local Precision Time Protocol (PTP) hardware clock (PHC) is supported.
      returned: when available
      type: str
    placement_group_info:
      description: Placement group settings for the instance type.
      returned: when available
      type: dict
      contains:
        supported_strategies:
          description: The supported placement group types.
          returned: when available
          type: list
          elements: str
    processor_info:
      description: Processor of the instance type.
      returned: when available
      type: dict
      contains:
        manufacturer:
          description: The manufacturer of the processor.
          returned: when available
          type: str
        supported_architectures:
          description: The architectures supported by the instance type.
          returned: when available
          type: list
          elements: str
        supported_features:
          description: Additional processor features supported by the instance type, such as C(amd-sev-snp).
          returned: when available
          type: list
          elements: str
        sustained_clock_speed_in_ghz:
          description: The speed of the processor, in GHz.
          returned: when available
          type: float
    reboot_migration_support:
      description: Whether reboot migration during a user-initiated reboot is supported for instances with a scheduled C(system-reboot) event.
      returned: when available
      type: str
    supported_boot_modes:
      description: Supported boot modes.
      returned: when available
      type: list
      elements: str
    supported_in_region:
      description: Whether the instance type is supported in the current region.
      returned: when available
      type: bool
    supported_root_device_types:
      description: Supported root device types.
      returned: when available
      type: list
      elements: str
    supported_usage_classes:
      description: Whether the instance type is offered for Spot, On-Demand, or Capacity Blocks.
      returned: when available
      type: list
      elements: str
    supported_virtualization_types:
      description: Supported virtualization types.
      returned: when available
      type: list
      elements: str
    v_cpu_info:
      description: vCPU configurations for the instance type.
      returned: when available
      type: dict
      contains:
        default_cores:
          description: The default number of cores for the instance type.
          returned: when available
          type: int
        default_threads_per_core:
          description: The default number of threads per core for the instance type.
          returned: when available
          type: int
        default_v_cpus:
          description: The default number of vCPUs for the instance type.
          returned: when available
          type: int
        valid_cores:
          description: The valid number of cores that can be configured for the instance type.
          returned: when available
          type: list
          elements: int
        valid_threads_per_core:
          description: The valid number of threads per core that can be configured for the instance type.
          returned: when available
          type: list
          elements: int
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    MAX_FILTER_VALUES_PER_REQUEST,
    ansible_dict_to_string_filter_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "include_unsupported_in_region": {"default": False, "type": "bool"},
        "instance_types": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    filters = dict(module.params["filters"] or {})
    instance_types = list(dict.fromkeys(module.params["instance_types"] or []))

    # InstanceTypes fails for a type that is not offered in the region, so
    # instance types are sent as the documented instance-type filter.
    if instance_types:
        filters["instance-type"] = instance_types

    # EC2 rejects a call with more than 200 values across all of its filters.
    if sum(len(value) if isinstance(value, list) else 1 for value in filters.values()) > MAX_FILTER_VALUES_PER_REQUEST:
        module.fail_json(
            msg=f"filters and instance_types must contain at most {MAX_FILTER_VALUES_PER_REQUEST} values in total"
        )

    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    request = {}
    if filters:
        request["Filters"] = ansible_dict_to_string_filter_list(filters)

    if module.params.get("include_unsupported_in_region"):
        request["IncludeUnsupportedInRegion"] = True

    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_instance_types": tuple(request) + ("MaxResults", "NextToken")},
    )

    instance_types = query_list(
        module,
        client,
        "describe_instance_types",
        "InstanceTypes",
        "Unable to describe EC2 instance types",
        **request,
    )

    if any(not isinstance(instance_type, dict) for instance_type in instance_types):
        module.fail_json(msg="EC2 returned invalid instance type information")

    module.exit_json(
        changed=False,
        instance_types=boto3_resource_list_to_ansible_dict(instance_types, transform_tags=False, force_tags=False),
    )


if __name__ == "__main__":
    main()
