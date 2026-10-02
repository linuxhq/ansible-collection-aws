#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: global_accelerator_info
version_added: "1.9.0"
short_description: Gather information about AWS Global Accelerator accelerators
description:
  - Gathers information about AWS Global Accelerator accelerators, and
    optionally their listeners and endpoint groups.
  - The Global Accelerator control plane uses the C(us-west-2) region.
author:
  - Taylor Kimball (@tkimball83)
options:
  arn:
    description:
      - ARN of the accelerator to gather information about.
      - When omitted, all accelerators are returned.
      - An accelerator that does not exist results in an empty list.
    aliases:
      - accelerator_arn
    type: str
  include_endpoint_groups:
    description:
      - Whether to include each listener's endpoint groups in the results.
      - Enabling this option implies O(include_listeners=true).
    default: false
    type: bool
  include_listeners:
    description:
      - Whether to include each accelerator's listeners in the results.
    default: false
    type: bool
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Queries AWS without modifying resources.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about all Global Accelerator accelerators
  linuxhq.aws.global_accelerator_info:

- name: Gather information about a single Global Accelerator accelerator
  linuxhq.aws.global_accelerator_info:
    arn: arn:aws:globalaccelerator::123456789012:accelerator/01234567-89ab-cdef-0123-456789abcdef

- name: Gather information including listeners and endpoint groups
  linuxhq.aws.global_accelerator_info:
    include_endpoint_groups: true
"""

RETURN = r"""
accelerator_arns:
  description:
    - A list of matching accelerator ARNs.
  returned: always
  type: list
  elements: str
accelerators:
  description:
    - The Global Accelerator accelerators.
    - Each accelerator includes C(listeners) when O(include_listeners=true) or
      O(include_endpoint_groups=true), and each listener includes
      C(endpoint_groups) when O(include_endpoint_groups=true).
  returned: always
  type: list
  elements: dict
  contains:
    accelerator_arn:
      description: The accelerator ARN.
      returned: always
      type: str
    created_time:
      description: The time the accelerator was created.
      returned: when returned by AWS
      type: str
    dns_name:
      description: The IPv4 DNS name of the accelerator.
      returned: when returned by AWS
      type: str
    dual_stack_dns_name:
      description: The dual-stack DNS name of the accelerator.
      returned: when the accelerator is dual-stack
      type: str
    enabled:
      description: Whether the accelerator is enabled.
      returned: always
      type: bool
    ip_address_type:
      description: The accelerator IP address type.
      returned: always
      type: str
      sample: IPV4
    ip_sets:
      description: The static IP addresses assigned to the accelerator.
      returned: when returned by AWS
      type: list
      elements: dict
      contains:
        ip_address_family:
          description: The IP address family.
          returned: when returned by AWS
          type: str
        ip_addresses:
          description: The IP addresses.
          returned: always
          type: list
          elements: str
    last_modified_time:
      description: The time the accelerator was last modified.
      returned: when returned by AWS
      type: str
    name:
      description: The accelerator name.
      returned: always
      type: str
    status:
      description: The accelerator deployment status.
      returned: when returned by AWS
      type: str
      sample: DEPLOYED
    tags:
      description: The accelerator tags with key case preserved.
      returned: when tags are managed or gathered
      type: dict
    listeners:
      description: The accelerator listeners.
      returned: when O(include_listeners=true) or O(include_endpoint_groups=true)
      type: list
      elements: dict
      contains:
        accelerator_arn:
          description: The accelerator ARN.
          returned: always
          type: str
        client_affinity:
          description: The listener client affinity.
          returned: always
          type: str
          sample: NONE
        endpoint_groups:
          description: The listener endpoint groups.
          returned: when O(include_endpoint_groups=true)
          type: list
          elements: dict
          contains:
            endpoint_descriptions:
              description: The endpoints in the endpoint group.
              returned: when returned by AWS
              type: list
              elements: dict
              contains:
                client_ip_preservation_enabled:
                  description: Whether client IP address preservation is enabled.
                  returned: when returned by AWS
                  type: bool
                endpoint_id:
                  description: The endpoint ID.
                  returned: always
                  type: str
                health_reason:
                  description: The reason for the endpoint health state.
                  returned: when returned by AWS
                  type: str
                health_state:
                  description: The endpoint health state.
                  returned: when returned by AWS
                  type: str
                weight:
                  description: The endpoint weight.
                  returned: when returned by AWS
                  type: int
            endpoint_group_arn:
              description: The endpoint group ARN.
              returned: when the endpoint group exists
              type: str
            endpoint_group_region:
              description: The endpoint group region.
              returned: always
              type: str
            health_check_interval_seconds:
              description: The time in seconds between health checks.
              returned: when returned by AWS
              type: int
            health_check_path:
              description: The health check path.
              returned: when returned by AWS
              type: str
            health_check_port:
              description: The health check port.
              returned: when returned by AWS
              type: int
            health_check_protocol:
              description: The health check protocol.
              returned: when returned by AWS
              type: str
            port_overrides:
              description: The listener to endpoint port overrides.
              returned: when returned by AWS
              type: list
              elements: dict
              contains:
                endpoint_port:
                  description: The endpoint port.
                  returned: always
                  type: int
                listener_port:
                  description: The listener port.
                  returned: always
                  type: int
            threshold_count:
              description: The number of health checks required to change endpoint health.
              returned: when returned by AWS
              type: int
            traffic_dial_percentage:
              description: The percentage of traffic sent to the endpoint group.
              returned: when returned by AWS
              type: float
        listener_arn:
          description: The listener ARN.
          returned: when the listener exists
          type: str
        port_ranges:
          description: The listener port ranges.
          returned: always
          type: list
          elements: dict
          contains:
            from_port:
              description: The first port in the range.
              returned: always
              type: int
            to_port:
              description: The last port in the range.
              returned: always
              type: int
        protocol:
          description: The listener protocol.
          returned: always
          type: str
          sample: TCP
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_accelerator(module, accelerator, expected_arn=None):
    if (
        not isinstance(accelerator, dict)
        or not isinstance(accelerator.get("AcceleratorArn"), str)
        or not accelerator["AcceleratorArn"]
        or (expected_arn is not None and accelerator["AcceleratorArn"] != expected_arn)
    ):
        module.fail_json(msg="Global Accelerator returned an invalid accelerator")

    return accelerator


def validate_resource_list(module, resources, resource_name, arn_key):
    if not isinstance(resources, list) or any(
        not isinstance(resource, dict) or not isinstance(resource.get(arn_key), str) or not resource[arn_key]
        for resource in resources
    ):
        module.fail_json(msg=f"Global Accelerator returned an invalid {resource_name} list")

    return resources


def validate_tags(module, tags):
    if not isinstance(tags, list) or any(
        not isinstance(tag, dict)
        or not isinstance(tag.get("Key"), str)
        or not tag["Key"]
        or not isinstance(tag.get("Value"), str)
        for tag in tags
    ):
        module.fail_json(msg="Global Accelerator returned invalid tags")

    return tags


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "arn": {"aliases": ["accelerator_arn"], "type": "str"},
            "include_endpoint_groups": {"default": False, "type": "bool"},
            "include_listeners": {"default": False, "type": "bool"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "globalaccelerator",
        region="us-west-2",
        retry_decorator=AWSRetry.jittered_backoff(),
    )

    arn = module.params["arn"]
    include_endpoint_groups = module.params["include_endpoint_groups"]
    include_listeners = module.params["include_listeners"] or include_endpoint_groups

    methods = {}
    if arn is None:
        methods["list_accelerators"] = ("MaxResults", "NextToken")
    else:
        methods["describe_accelerator"] = ("AcceleratorArn",)

    require_client_methods(module, client, "Global Accelerator", methods)

    accelerators = []

    if arn is None:
        accelerators = query_list(
            module,
            client,
            "list_accelerators",
            "Accelerators",
            "Unable to list AWS Global Accelerator accelerators",
        )
        validate_resource_list(
            module,
            accelerators,
            "accelerator",
            "AcceleratorArn",
        )
    else:
        try:
            response = client.describe_accelerator(
                AcceleratorArn=arn,
                aws_retry=True,
            )
        except is_boto3_error_code("AcceleratorNotFoundException"):
            response = None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to describe AWS Global Accelerator {arn}",
            )

        if response is not None:
            accelerators.append(
                validate_accelerator(
                    module,
                    response.get("Accelerator") if isinstance(response, dict) else None,
                    expected_arn=arn,
                )
            )

    if accelerators:
        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"list_tags_for_resource": ("ResourceArn",)},
        )

    available_accelerators = []
    for accelerator in accelerators:
        accelerator_arn = accelerator["AcceleratorArn"]

        try:
            response = client.list_tags_for_resource(
                ResourceArn=accelerator_arn,
                aws_retry=True,
            )
        except is_boto3_error_code("AcceleratorNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list tags for AWS Global Accelerator {accelerator_arn}",
            )

        accelerator["Tags"] = validate_tags(
            module,
            response.get("Tags") if isinstance(response, dict) else None,
        )

        if not include_listeners:
            available_accelerators.append(accelerator)
            continue

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"list_listeners": ("AcceleratorArn", "MaxResults", "NextToken")},
        )
        try:
            response = paginated_query_with_retries(
                client,
                "list_listeners",
                AcceleratorArn=accelerator_arn,
            )
        except is_boto3_error_code("AcceleratorNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list AWS Global Accelerator listeners for {accelerator_arn}",
            )

        listeners = validate_resource_list(
            module,
            response.get("Listeners") if isinstance(response, dict) else None,
            "listener",
            "ListenerArn",
        )

        available_listeners = []
        for listener in listeners:
            listener["AcceleratorArn"] = accelerator_arn

            if not include_endpoint_groups:
                available_listeners.append(listener)
                continue

            listener_arn = listener["ListenerArn"]

            require_client_methods(
                module,
                client,
                "Global Accelerator",
                {
                    "list_endpoint_groups": (
                        "ListenerArn",
                        "MaxResults",
                        "NextToken",
                    )
                },
            )
            try:
                response = paginated_query_with_retries(
                    client,
                    "list_endpoint_groups",
                    ListenerArn=listener_arn,
                )
            except is_boto3_error_code("ListenerNotFoundException"):
                continue
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to list AWS Global Accelerator endpoint groups for {listener_arn}",
                )

            listener["EndpointGroups"] = validate_resource_list(
                module,
                response.get("EndpointGroups") if isinstance(response, dict) else None,
                "endpoint group",
                "EndpointGroupArn",
            )
            available_listeners.append(listener)

        accelerator["Listeners"] = available_listeners
        available_accelerators.append(accelerator)

    normalized_accelerators = boto3_resource_list_to_ansible_dict(
        available_accelerators,
        transform_tags=True,
        force_tags=False,
    )

    accelerator_arns = [
        accelerator["accelerator_arn"] for accelerator in normalized_accelerators if accelerator.get("accelerator_arn")
    ]

    module.exit_json(
        accelerator_arns=accelerator_arns,
        accelerators=normalized_accelerators,
        changed=False,
    )


if __name__ == "__main__":
    main()
