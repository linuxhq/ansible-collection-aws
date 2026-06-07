#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_zone_associate
short_description: Manage aws route53 zone associations
description:
  - Manages AWS Route53 private hosted zone VPC associations.
author:
  - Taylor Kimball (@tkimball83)
options:
  hosted_zone_id:
    description:
      - The private hosted zone ID.
    required: true
    type: str
  state:
    description:
      - Whether the VPC association should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  vpc_id:
    description:
      - The VPC ID to associate with the hosted zone.
    required: true
    type: str
  vpc_region:
    description:
      - The AWS region of the VPC.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a VPC is associated with a hosted zone
  linuxhq.aws.route53_zone_associate:
    hosted_zone_id: Z0123456789ABCDEFG
    vpc_id: vpc-0123456789abcdef0
    vpc_region: us-east-1

- name: Ensure a VPC is disassociated from a hosted zone
  linuxhq.aws.route53_zone_associate:
    hosted_zone_id: Z0123456789ABCDEFG
    state: absent
    vpc_id: vpc-0123456789abcdef0
    vpc_region: us-east-1
"""

RETURN = r"""
hosted_zone_id:
  description:
    - The requested hosted zone ID.
  returned: always
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
vpc:
  description:
    - The requested VPC association.
  returned: always
  type: dict
vpcs:
  description:
    - The current hosted zone VPC associations.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def ensure_absent(client, module, hosted_zone_id):
    vpcs = get_vpc_associations(client, module, hosted_zone_id)
    current_vpcs = route53_vpc_list(vpcs)
    requested_vpc = route53_vpc(module)
    changed = requested_vpc in current_vpcs

    if changed and not module.check_mode:
        try:
            client.disassociate_vpc_from_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC=requested_vpc,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    f"Unable to disassociate VPC {module.params['vpc_id']} from AWS "
                    f"Route53 hosted zone {hosted_zone_id}"
                ),
            )

    if changed:
        vpcs = []
        for vpc in current_vpcs:
            if vpc == requested_vpc:
                continue

            vpcs.append(vpc)

    module.exit_json(
        changed=changed,
        hosted_zone_id=hosted_zone_id,
        state=module.params["state"],
        vpc=boto3_resource_to_ansible_dict(
            requested_vpc, transform_tags=False, force_tags=False
        ),
        vpcs=boto3_resource_list_to_ansible_dict(
            vpcs, transform_tags=False, force_tags=False
        ),
    )


def ensure_present(client, module, hosted_zone_id):
    vpcs = get_vpc_associations(client, module, hosted_zone_id)
    current_vpcs = route53_vpc_list(vpcs)
    requested_vpc = route53_vpc(module)
    changed = requested_vpc not in current_vpcs

    if changed and not module.check_mode:
        try:
            client.associate_vpc_with_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC=requested_vpc,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    f"Unable to associate VPC {module.params['vpc_id']} with AWS "
                    f"Route53 hosted zone {hosted_zone_id}"
                ),
            )

    if changed:
        vpcs = route53_vpc_list(current_vpcs + [requested_vpc])

    module.exit_json(
        changed=changed,
        hosted_zone_id=hosted_zone_id,
        state=module.params["state"],
        vpc=boto3_resource_to_ansible_dict(
            requested_vpc, transform_tags=False, force_tags=False
        ),
        vpcs=boto3_resource_list_to_ansible_dict(
            vpcs, transform_tags=False, force_tags=False
        ),
    )


def get_vpc_associations(client, module, hosted_zone_id):
    try:
        return client.get_hosted_zone(
            Id=hosted_zone_id,
            aws_retry=True,
        ).get("VPCs", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 hosted zone {hosted_zone_id}",
        )


def route53_vpc(module):
    return {
        "VPCId": module.params["vpc_id"],
        "VPCRegion": module.params["vpc_region"],
    }


def route53_vpc_list(vpcs):
    normalized = []
    for vpc in vpcs or []:
        normalized.append(
            {
                "VPCId": vpc.get("VPCId") or vpc.get("vpc_id"),
                "VPCRegion": vpc.get("VPCRegion") or vpc.get("vpc_region"),
            }
        )
    return sorted(normalized, key=lambda vpc: (vpc.get("VPCId"), vpc.get("VPCRegion")))


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "hosted_zone_id": {"required": True, "type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "vpc_id": {"required": True, "type": "str"},
            "vpc_region": {"required": True, "type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())
    hosted_zone_id = module.params["hosted_zone_id"].rsplit("/", 1)[-1]

    state = module.params["state"]
    method_names = {"get_hosted_zone"}
    if state == "present":
        method_names.add("associate_vpc_with_hosted_zone")
    elif state == "absent":
        method_names.add("disassociate_vpc_from_hosted_zone")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support Route53 {method_name}"
            )

    required_method_parameters = {
        "associate_vpc_with_hosted_zone": {"HostedZoneId", "VPC"},
        "disassociate_vpc_from_hosted_zone": {"HostedZoneId", "VPC"},
        "get_hosted_zone": {"Id"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Route53 "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module, hosted_zone_id)
    elif state == "absent":
        ensure_absent(client, module, hosted_zone_id)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
