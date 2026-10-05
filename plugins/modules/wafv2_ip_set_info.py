#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_ip_set_info
version_added: '1.9.0'
short_description: Gather information about AWS WAFv2 IP sets
description:
  - Gathers information about AWS WAFv2 IP sets.
  - Lists IP sets for the requested scope and returns each full IP set definition
    with its tags.
author:
  - Taylor Kimball (@tkimball83)
options:
  id:
    description:
      - WAFv2 IP set ID used to limit the result set.
      - This must not be empty when specified.
      - The module lists IP set summaries for the selected O(scope), filters by
        ID, and then gathers each full IP set definition.
      - When both O(id) and O(name) are specified, the module gets the IP set
        directly without listing summaries.
    type: str
  name:
    description:
      - WAFv2 IP set name used to limit the result set.
      - This must not be empty when specified.
      - The module lists IP set summaries for the selected O(scope), filters by
        name, and then gathers each full IP set definition.
      - When both O(id) and O(name) are specified, the module gets the IP set
        directly without listing summaries.
      - An IP set that does not exist results in an empty list.
    type: str
  scope:
    description:
      - The scope of the IP sets to gather.
      - Use C(cloudfront) for global IP sets and C(regional) for regional IP sets.
      - V(cloudfront) requires the C(us-east-1) region; any other region fails
        before AWS is called.
    choices:
      - cloudfront
      - regional
    default: regional
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about regional WAFv2 IP sets
  linuxhq.aws.wafv2_ip_set_info:

- name: Gather information about CloudFront WAFv2 IP sets
  linuxhq.aws.wafv2_ip_set_info:
    scope: cloudfront
    region: us-east-1

- name: Gather information about selected WAFv2 IP sets
  linuxhq.aws.wafv2_ip_set_info:
    name: molecule
"""

RETURN = r"""
ip_sets:
  description:
    - A list of AWS WAFv2 IP set definitions.
  returned: always
  type: list
  elements: dict
  contains:
    addresses:
      description: IP addresses and CIDR ranges included in the IP set.
      returned: always
      type: list
      elements: str
    arn:
      description: ARN of the IP set.
      returned: always
      type: str
    description:
      description: Description of the IP set.
      returned: when available
      type: str
    id:
      description: ID of the IP set.
      returned: always
      type: str
    ip_address_version:
      description: IP address version used by the IP set.
      returned: always
      type: str
    name:
      description: Name of the IP set.
      returned: always
      type: str
    tags:
      description:
        - Tags of the IP set.
        - Tag keys keep their original case.
      returned: always
      type: dict
scope:
  description: The AWS WAFv2 scope that was queried.
  returned: always
  type: str
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods
from ansible_collections.linuxhq.aws.plugins.module_utils.wafv2 import (
    get_resource_tags,
    list_resource_summaries,
    require_lookup_params,
)


def main():
    argument_spec = {
        "id": {"type": "str"},
        "name": {"type": "str"},
        "scope": {
            "choices": ["cloudfront", "regional"],
            "default": "regional",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    require_lookup_params(module)

    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(
        module,
        client,
        "WAFv2",
        {
            "list_ip_sets": ("Limit", "NextMarker", "Scope"),
            "get_ip_set": ("Id", "Name", "Scope"),
            "list_tags_for_resource": ("NextMarker", "ResourceARN"),
        },
    )

    scope = module.params["scope"].upper()
    summaries = list_resource_summaries(client, module, "list_ip_sets", "IPSets", "IP sets", scope)

    ip_sets = []
    for summary in summaries:
        try:
            response = client.get_ip_set(
                Id=summary["Id"],
                Name=summary["Name"],
                Scope=scope,
                aws_retry=True,
            )
        except is_boto3_error_code("WAFNonexistentItemException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS WAFv2 IP set {summary['Name']}/{summary['Id']}",
            )

        ip_set = response.get("IPSet") if isinstance(response, dict) else None
        if not isinstance(ip_set, dict):
            module.fail_json(
                msg=f"Unexpected response while getting AWS WAFv2 IP set {summary['Name']}/{summary['Id']}"
            )

        tags = get_resource_tags(client, module, ip_set, "IP set")
        if tags is None:
            continue

        ip_sets.append(dict(ip_set, Tags=tags))

    module.exit_json(
        changed=False,
        ip_sets=boto3_resource_list_to_ansible_dict(
            ip_sets, ignore_list=["Tags"], transform_tags=False, force_tags=False
        ),
        scope=scope.lower(),
    )


if __name__ == "__main__":
    main()
