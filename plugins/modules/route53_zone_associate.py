#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_zone_associate
version_added: '1.9.0'
short_description: Manage AWS Route53 zone associations
description:
  - Manages AWS Route53 private hosted zone VPC associations.
  - The last VPC association of a private hosted zone cannot be removed.
  - When the hosted zone belongs to another AWS account, the association is
    looked up with C(ListHostedZonesByVPC), and only the requested VPC is
    returned in RV(vpcs). The zone owner must first authorize the VPC.
author:
  - Taylor Kimball (@tkimball83)
options:
  hosted_zone_id:
    description:
      - The private hosted zone ID.
      - This accepts a bare ID or the full C(/hostedzone/ID) path.
      - When O(state=present), the hosted zone must exist and be private.
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
  wait:
    description:
      - Whether to wait for the change to propagate to all Route53 DNS servers.
    default: false
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    default: 300
    type: int
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

- name: Ensure a VPC is associated with a hosted zone and the change is in sync
  linuxhq.aws.route53_zone_associate:
    hosted_zone_id: Z0123456789ABCDEFG
    vpc_id: vpc-0123456789abcdef0
    vpc_region: us-east-1
    wait: true

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
    - When the hosted zone belongs to another AWS account, this contains only
      the requested VPC when it is associated.
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
from ansible_collections.amazon.aws.plugins.module_utils.waiter import custom_waiter_config

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import require_positive_wait_bounds


def ensure_absent(client, module, hosted_zone_id):
    zone = get_hosted_zone(client, module, hosted_zone_id)
    vpcs = route53_vpc_list(zone["vpcs"])
    requested_vpc = route53_vpc(module)
    changed = requested_vpc in vpcs

    if changed and not zone["shared"] and vpcs == [requested_vpc]:
        module.fail_json(msg=last_vpc_association_message(module, hosted_zone_id))

    if changed and not module.check_mode:
        try:
            response = client.disassociate_vpc_from_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC=requested_vpc,
                aws_retry=True,
            )
        except is_boto3_error_code("VPCAssociationNotFound"):
            response = None
        except is_boto3_error_code("LastVPCAssociation") as e:
            module.fail_json_aws(e, msg=last_vpc_association_message(module, hosted_zone_id))
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to disassociate VPC {module.params['vpc_id']} from AWS Route53 hosted zone {hosted_zone_id}",
            )

        wait_for_change(client, module, response, hosted_zone_id)

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
    zone = get_hosted_zone(client, module, hosted_zone_id)
    if not zone["found"]:
        module.fail_json(msg=f"AWS Route53 hosted zone {hosted_zone_id} does not exist")

    if not zone["private"]:
        module.fail_json(
            msg=f"AWS Route53 hosted zone {hosted_zone_id} is public; VPCs can be associated only with private hosted zones"
        )

    vpcs = route53_vpc_list(zone["vpcs"])
    requested_vpc = route53_vpc(module)
    changed = requested_vpc not in vpcs

    if changed and not module.check_mode:
        try:
            response = client.associate_vpc_with_hosted_zone(
                HostedZoneId=hosted_zone_id,
                VPC=requested_vpc,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to associate VPC {module.params['vpc_id']} with AWS Route53 hosted zone {hosted_zone_id}",
            )

        wait_for_change(client, module, response, hosted_zone_id)

    if changed:
        vpcs = route53_vpc_list(vpcs + [requested_vpc])

    module.exit_json(
        changed=changed,
        hosted_zone_id=hosted_zone_id,
        state="present",
        vpc=boto3_resource_to_ansible_dict(requested_vpc, transform_tags=False, force_tags=False),
        vpcs=boto3_resource_list_to_ansible_dict(vpcs, transform_tags=False, force_tags=False),
    )


def get_hosted_zone(client, module, hosted_zone_id):
    try:
        response = client.get_hosted_zone(
            Id=hosted_zone_id,
            aws_retry=True,
        )
    except is_boto3_error_code("NoSuchHostedZone"):
        return {"found": False, "private": False, "shared": False, "vpcs": []}
    except is_boto3_error_code("AccessDenied"):
        # The VPC owner cannot read a hosted zone owned by another account.
        return {
            "found": True,
            "private": True,
            "shared": True,
            "vpcs": get_shared_vpc_association(client, module, hosted_zone_id),
        }
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 hosted zone {hosted_zone_id}",
        )

    if (
        not isinstance(response, dict)
        or not isinstance(response.get("HostedZone", {}), dict)
        or not isinstance(response.get("VPCs", []), list)
    ):
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

    private = response.get("HostedZone", {}).get("Config", {}).get("PrivateZone") is True
    return {"found": True, "private": private, "shared": False, "vpcs": vpcs}


def get_shared_vpc_association(client, module, hosted_zone_id):
    require_client_methods(
        module,
        client,
        "Route53",
        {"list_hosted_zones_by_vpc": ("MaxItems", "NextToken", "VPCId", "VPCRegion")},
    )
    requested_vpc = route53_vpc(module)
    summaries = query_list(
        module,
        client,
        "list_hosted_zones_by_vpc",
        "HostedZoneSummaries",
        f"Unable to list AWS Route53 hosted zones associated with VPC {module.params['vpc_id']}",
        VPCId=requested_vpc["VPCId"],
        VPCRegion=requested_vpc["VPCRegion"],
    )
    associated = any(
        isinstance(summary, dict) and str(summary.get("HostedZoneId", "")).rsplit("/", 1)[-1] == hosted_zone_id
        for summary in summaries
    )
    return [requested_vpc] if associated else []


def last_vpc_association_message(module, hosted_zone_id):
    return (
        f"Unable to disassociate VPC {module.params['vpc_id']} from AWS Route53 hosted zone {hosted_zone_id} "
        "because it is the last VPC associated with the private hosted zone"
    )


def wait_for_change(client, module, response, hosted_zone_id):
    if not module.params["wait"] or not isinstance(response, dict):
        return

    change_id = (response.get("ChangeInfo") or {}).get("Id")
    if not isinstance(change_id, str) or not change_id:
        module.fail_json(msg=f"AWS Route53 did not return a change ID for hosted zone {hosted_zone_id}")

    try:
        client.get_waiter("resource_record_sets_changed").wait(
            Id=change_id,
            WaiterConfig=custom_waiter_config(module.params["wait_timeout"], default_pause=module.params["wait_delay"]),
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to wait for AWS Route53 change {change_id} for hosted zone {hosted_zone_id} to become INSYNC",
        )


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
            "wait": {"default": False, "type": "bool"},
            "wait_delay": {"default": 5, "type": "int"},
            "wait_timeout": {"default": 300, "type": "int"},
        },
        supports_check_mode=True,
    )
    state = module.params["state"]
    vpc_region = module.params["vpc_region"]

    if not 2 <= len(vpc_region) <= 25 or not re.fullmatch(r"[a-z]{2,4}(?:-[a-z]{1,15})+-[0-9]", vpc_region):
        module.fail_json(msg="vpc_region must be a valid AWS region name")

    require_positive_wait_bounds(module)

    client = module.client(
        "route53",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["PriorRequestNotComplete"]),
    )
    hosted_zone_id = module.params["hosted_zone_id"].rsplit("/", 1)[-1]
    methods = {"get_hosted_zone": ("Id",)}
    if module.params["wait"]:
        methods["get_change"] = ("Id",)

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
