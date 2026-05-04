#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_zone_associate
version_added: 1.9.1
short_description: Manage AWS Route53 private hosted zone VPC associations
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def normalize_hosted_zone_id(hosted_zone_id):
    return hosted_zone_id.rsplit("/", 1)[-1]


def get_hosted_zone(client, module, hosted_zone_id):
    get_hosted_zone = AWSRetry.jittered_backoff()(client.get_hosted_zone)
    try:
        response = get_hosted_zone(Id=hosted_zone_id)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 hosted zone {hosted_zone_id}",
        )
    return response


def get_vpc_associations(client, module, hosted_zone_id):
    response = get_hosted_zone(client, module, hosted_zone_id)
    return response.get("VPCs", [])


def is_associated(vpcs, module):
    for vpc in vpcs:
        if (
            vpc.get("VPCId") == module.params["vpc_id"]
            and vpc.get("VPCRegion") == module.params["vpc_region"]
        ):
            return True
    return False


def build_result(module, changed, vpcs):
    module.exit_json(
        changed=changed,
        hosted_zone_id=module.params["hosted_zone_id"],
        state=module.params["state"],
        vpc=boto3_resource_to_ansible_dict(
            {
                "VPCId": module.params["vpc_id"],
                "VPCRegion": module.params["vpc_region"],
            },
            force_tags=False,
        ),
        vpcs=boto3_resource_list_to_ansible_dict(vpcs, force_tags=False),
    )


def ensure_present(client, module, hosted_zone_id):
    vpcs = get_vpc_associations(client, module, hosted_zone_id)
    changed = not is_associated(vpcs, module)

    if changed and not module.check_mode:
        associate_vpc_with_hosted_zone = AWSRetry.jittered_backoff()(
            client.associate_vpc_with_hosted_zone
        )
        try:
            associate_vpc_with_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC={
                    "VPCId": module.params["vpc_id"],
                    "VPCRegion": module.params["vpc_region"],
                },
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to associate VPC {module.params['vpc_id']} with AWS Route53 hosted zone {hosted_zone_id}",
            )
        vpcs = get_vpc_associations(client, module, hosted_zone_id)

    build_result(module, changed, vpcs)


def ensure_absent(client, module, hosted_zone_id):
    vpcs = get_vpc_associations(client, module, hosted_zone_id)
    changed = is_associated(vpcs, module)

    if changed and not module.check_mode:
        disassociate_vpc_from_hosted_zone = AWSRetry.jittered_backoff()(
            client.disassociate_vpc_from_hosted_zone
        )
        try:
            disassociate_vpc_from_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC={
                    "VPCId": module.params["vpc_id"],
                    "VPCRegion": module.params["vpc_region"],
                },
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to disassociate VPC {module.params['vpc_id']} from AWS Route53 hosted zone {hosted_zone_id}",
            )
        vpcs = get_vpc_associations(client, module, hosted_zone_id)

    build_result(module, changed, vpcs)


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
    client = module.client("route53")
    hosted_zone_id = normalize_hosted_zone_id(module.params["hosted_zone_id"])
    module.params["hosted_zone_id"] = hosted_zone_id

    if module.params["state"] == "present":
        ensure_present(client, module, hosted_zone_id)
    ensure_absent(client, module, hosted_zone_id)


if __name__ == "__main__":
    main()
