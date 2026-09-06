#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_zone_associate
short_description: Manage AWS Route53 zone associations
description:
  - Manages AWS Route53 private hosted zone VPC associations.
  - The last VPC association of a private hosted zone cannot be removed;
    the Route53 API rejects the request.
author:
  - Taylor Kimball (@tkimball83)
options:
  hosted_zone_id:
    description:
      - The private hosted zone ID.
      - This accepts a bare ID or the full C(/hostedzone/ID) path.
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
      - This must match the AWS region name format, for example V(us-west-2).
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
  contains:
    vpc_id:
      description:
        - The VPC ID.
      returned: always
      type: str
    vpc_region:
      description:
        - The AWS region of the VPC.
      returned: always
      type: str
vpcs:
  description:
    - The current hosted zone VPC associations.
  returned: always
  type: list
  elements: dict
  contains:
    vpc_id:
      description:
        - The VPC ID.
      returned: always
      type: str
    vpc_region:
      description:
        - The AWS region of the VPC.
      returned: always
      type: str
"""

import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def ensure_absent(client, module, hosted_zone_id):
    vpcs = route53_vpc_list(get_vpc_associations(client, module, hosted_zone_id))
    requested_vpc = route53_vpc(module)
    changed = requested_vpc in vpcs

    if changed and not module.check_mode:
        try:
            client.disassociate_vpc_from_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC=requested_vpc,
                aws_retry=True,
            )
        except is_boto3_error_code("VPCAssociationNotFound"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    f"Unable to disassociate VPC {module.params['vpc_id']} from AWS "
                    f"Route53 hosted zone {hosted_zone_id}"
                ),
            )

    if changed:
        vpcs = [vpc for vpc in vpcs if vpc != requested_vpc]

    module.exit_json(
        changed=changed,
        hosted_zone_id=hosted_zone_id,
        state="absent",
        vpc=boto3_resource_to_ansible_dict(requested_vpc, transform_tags=False, force_tags=False),
        vpcs=boto3_resource_list_to_ansible_dict(vpcs, transform_tags=False, force_tags=False),
    )


def ensure_present(client, module, hosted_zone_id):
    vpcs = route53_vpc_list(get_vpc_associations(client, module, hosted_zone_id))
    requested_vpc = route53_vpc(module)
    changed = requested_vpc not in vpcs

    if changed and not module.check_mode:
        try:
            client.associate_vpc_with_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC=requested_vpc,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    f"Unable to associate VPC {module.params['vpc_id']} with AWS "
                    f"Route53 hosted zone {hosted_zone_id}"
                ),
            )

    if changed:
        vpcs = route53_vpc_list(vpcs + [requested_vpc])

    module.exit_json(
        changed=changed,
        hosted_zone_id=hosted_zone_id,
        state="present",
        vpc=boto3_resource_to_ansible_dict(requested_vpc, transform_tags=False, force_tags=False),
        vpcs=boto3_resource_list_to_ansible_dict(vpcs, transform_tags=False, force_tags=False),
    )


def get_vpc_associations(client, module, hosted_zone_id):
    try:
        response = client.get_hosted_zone(
            Id=hosted_zone_id,
            aws_retry=True,
        )
    except is_boto3_error_code("NoSuchHostedZone"):
        return []
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 hosted zone {hosted_zone_id}",
        )

    if not isinstance(response, dict) or not isinstance(response.get("VPCs", []), list):
        module.fail_json(msg=f"AWS Route53 returned an invalid hosted zone response for {hosted_zone_id}")

    vpcs = response.get("VPCs", [])
    for vpc in vpcs:
        if (
            not isinstance(vpc, dict)
            or not isinstance(vpc.get("VPCId"), str)
            or not vpc["VPCId"]
            or not isinstance(vpc.get("VPCRegion"), str)
            or not vpc["VPCRegion"]
        ):
            module.fail_json(msg=f"AWS Route53 returned an invalid VPC association for hosted zone {hosted_zone_id}")

    return vpcs


def route53_vpc(module):
    return {
        "VPCId": module.params["vpc_id"],
        "VPCRegion": module.params["vpc_region"],
    }


def route53_vpc_list(vpcs):
    normalized = [
        {
            "VPCId": vpc["VPCId"],
            "VPCRegion": vpc["VPCRegion"],
        }
        for vpc in vpcs or []
    ]
    return sorted(normalized, key=lambda vpc: (vpc["VPCId"], vpc["VPCRegion"]))


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
    state = module.params["state"]
    vpc_region = module.params["vpc_region"]

    if not 2 <= len(vpc_region) <= 25 or not re.fullmatch(r"[a-z]{1,2}(?:-[a-z]{1,15})+-[0-9]", vpc_region):
        module.fail_json(msg="vpc_region must be a valid AWS region name")

    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())
    hosted_zone_id = module.params["hosted_zone_id"].rsplit("/", 1)[-1]
    methods = {"get_hosted_zone": ("Id",)}
    if state == "present":
        methods["associate_vpc_with_hosted_zone"] = ("HostedZoneId", "VPC")

    if state == "absent":
        methods["disassociate_vpc_from_hosted_zone"] = ("HostedZoneId", "VPC")

    require_client_methods(module, client, "Route53", methods)

    if state == "present":
        ensure_present(client, module, hosted_zone_id)

    if state == "absent":
        ensure_absent(client, module, hosted_zone_id)


if __name__ == "__main__":
    main()
