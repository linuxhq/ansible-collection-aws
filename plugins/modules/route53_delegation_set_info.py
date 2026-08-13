#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set_info
short_description: Gather information about aws route53 delegation sets
description:
  - Gathers information about AWS Route53 reusable delegation sets.
author:
  - Taylor Kimball (@tkimball83)
options:
  id:
    description:
      - Route53 reusable delegation set ID used to limit the result set.
      - This accepts a bare ID or the full C(/delegationset/ID) path.
      - A delegation set that does not exist results in an empty list.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather Route53 reusable delegation set information
  linuxhq.aws.route53_delegation_set_info:

- name: Gather a specific Route53 reusable delegation set
  linuxhq.aws.route53_delegation_set_info:
    id: N1PA6795SAMPLE
"""

RETURN = r"""
delegation_sets:
  description:
    - The reusable delegation sets for the current AWS account.
  returned: always
  type: list
  elements: dict
"""

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
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "id": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())
    delegation_set_id = module.params["id"]

    require_client_methods(
        module,
        client,
        "Route53",
        (
            {"get_reusable_delegation_set": ("Id",)}
            if delegation_set_id
            else {"list_reusable_delegation_sets": ("Marker", "MaxItems")}
        ),
    )

    delegation_sets = []
    if delegation_set_id:
        try:
            delegation_set = client.get_reusable_delegation_set(
                Id=delegation_set_id,
                aws_retry=True,
            ).get("DelegationSet", {})
        except is_boto3_error_code("NoSuchDelegationSet"):
            delegation_set = {}
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to get AWS Route53 reusable delegation set " f"{delegation_set_id}"),
            )

        if delegation_set:
            delegation_sets.append(delegation_set)
    else:
        delegation_sets = query_list(
            module,
            client,
            "list_reusable_delegation_sets",
            "DelegationSets",
            "Unable to list AWS Route53 reusable delegation sets",
        )

    module.exit_json(
        changed=False,
        delegation_sets=boto3_resource_list_to_ansible_dict(delegation_sets, transform_tags=False, force_tags=False),
    )


if __name__ == "__main__":
    main()
