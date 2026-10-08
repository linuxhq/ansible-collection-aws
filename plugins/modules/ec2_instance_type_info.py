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
      - An instance type that is not offered in the region results in no entry; no error is raised.
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
    fpga_info:
      description: FPGA accelerator settings for the instance type.
      returned: when available
      type: dict
    free_tier_eligible:
      description: Whether the instance type is eligible for the free tier.
      returned: when available
      type: bool
    gpu_info:
      description: GPU accelerator settings for the instance type.
      returned: when available
      type: dict
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
    instance_storage_info:
      description: Instance storage for the instance type.
      returned: when available
      type: dict
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
    media_accelerator_info:
      description: Media accelerator settings for the instance type.
      returned: when available
      type: dict
    network_info:
      description: Network settings for the instance type.
      returned: when available
      type: dict
    neuron_info:
      description: Neuron accelerator settings for the instance type.
      returned: when available
      type: dict
    nitro_enclaves_support:
      description: Whether Nitro Enclaves is supported.
      returned: when available
      type: str
    nitro_tpm_info:
      description: Supported NitroTPM versions for the instance type.
      returned: when available
      type: dict
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
    processor_info:
      description: Processor of the instance type.
      returned: when available
      type: dict
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
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    ansible_dict_to_string_filter_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)

MAX_FILTER_VALUES = 200


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
    if sum(len(value) if isinstance(value, list) else 1 for value in filters.values()) > MAX_FILTER_VALUES:
        module.fail_json(msg=f"filters and instance_types must contain at most {MAX_FILTER_VALUES} values in total")

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
