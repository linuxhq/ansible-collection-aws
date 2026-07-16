#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: global_accelerator_info
short_description: Gather information about aws global accelerators
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
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


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

    methods = {"list_tags_for_resource": ("ResourceArn",)}
    if arn is None:
        methods["list_accelerators"] = ("MaxResults", "NextToken")
    else:
        methods["describe_accelerator"] = ("AcceleratorArn",)
    if include_listeners:
        methods["list_listeners"] = ("AcceleratorArn", "MaxResults", "NextToken")
    if include_endpoint_groups:
        methods["list_endpoint_groups"] = ("ListenerArn", "MaxResults", "NextToken")

    require_client_methods(module, client, "Global Accelerator", methods)

    accelerators = []

    if arn is None:
        try:
            accelerators = paginated_query_with_retries(
                client,
                "list_accelerators",
            ).get("Accelerators", [])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Global Accelerator accelerators",
            )
    else:
        try:
            accelerator = client.describe_accelerator(
                AcceleratorArn=arn,
                aws_retry=True,
            ).get("Accelerator")
        except is_boto3_error_code("AcceleratorNotFoundException"):
            accelerator = None
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to describe AWS Global Accelerator {arn}",
            )

        if accelerator is not None:
            accelerators.append(accelerator)

    for accelerator in accelerators:
        accelerator_arn = accelerator.get("AcceleratorArn")

        if accelerator_arn is None:
            accelerator["Tags"] = []
            continue

        try:
            accelerator["Tags"] = client.list_tags_for_resource(
                ResourceArn=accelerator_arn,
                aws_retry=True,
            ).get("Tags", [])
        except is_boto3_error_code("AcceleratorNotFoundException"):
            accelerator["Tags"] = []
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to list tags for AWS Global Accelerator "
                    f"{accelerator_arn}"
                ),
            )

        if not include_listeners:
            continue

        try:
            listeners = paginated_query_with_retries(
                client,
                "list_listeners",
                AcceleratorArn=accelerator_arn,
            ).get("Listeners", [])
        except is_boto3_error_code("AcceleratorNotFoundException"):
            listeners = []
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to list AWS Global Accelerator listeners for "
                    f"{accelerator_arn}"
                ),
            )

        for listener in listeners:
            listener["AcceleratorArn"] = accelerator_arn

            if not include_endpoint_groups:
                continue

            listener_arn = listener.get("ListenerArn")

            try:
                listener["EndpointGroups"] = paginated_query_with_retries(
                    client,
                    "list_endpoint_groups",
                    ListenerArn=listener_arn,
                ).get("EndpointGroups", [])
            except is_boto3_error_code("ListenerNotFoundException"):
                listener["EndpointGroups"] = []
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to list AWS Global Accelerator endpoint "
                        f"groups for {listener_arn}"
                    ),
                )

        accelerator["Listeners"] = listeners

    normalized_accelerators = boto3_resource_list_to_ansible_dict(
        accelerators,
        transform_tags=True,
        force_tags=False,
    )

    accelerator_arns = []
    for accelerator in normalized_accelerators:
        if accelerator.get("accelerator_arn"):
            accelerator_arns.append(accelerator["accelerator_arn"])

    module.exit_json(
        accelerator_arns=accelerator_arns,
        accelerators=normalized_accelerators,
        changed=False,
    )


if __name__ == "__main__":
    main()
