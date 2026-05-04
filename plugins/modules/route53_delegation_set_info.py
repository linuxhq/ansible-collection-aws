#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set_info
version_added: 1.9.1
short_description: Gather AWS Route53 reusable delegation set information
description:
  - Gathers AWS Route53 reusable delegation sets.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The reusable delegation set caller reference to query.
      - When omitted, all reusable delegation sets are returned.
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
    name: molecule-01
"""

RETURN = r"""
delegation_sets:
  description:
    - The reusable delegation sets for the current AWS account.
  returned: always
  type: list
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_delegation_sets(client, module):
    delegation_sets = []
    marker = None

    while True:
        kwargs = {}
        if marker:
            kwargs["Marker"] = marker

        try:
            response = client.list_reusable_delegation_sets(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Route53 reusable delegation sets",
            )

        delegation_sets.extend(response.get("DelegationSets", []))
        if not response.get("IsTruncated"):
            break
        marker = response.get("NextMarker")

    return [
        camel_dict_to_snake_dict(delegation_set)
        for delegation_set in delegation_sets
        if delegation_set.get("CallerReference") is not None
        and (
            module.params["name"] is None
            or delegation_set.get("CallerReference") == module.params["name"]
        )
    ]


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53")

    module.exit_json(
        changed=False,
        delegation_sets=list_delegation_sets(client, module),
    )


if __name__ == "__main__":
    main()
