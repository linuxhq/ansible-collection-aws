#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association_info
version_added: 1.9.1
short_description: Gather information about AWS Systems Manager associations
description:
  - Gathers information about AWS Systems Manager associations.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about AWS Systems Manager associations
  linuxhq.aws.ssm_association_info:
"""

RETURN = r"""
associations:
  description:
    - A list of AWS Systems Manager associations.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def normalize_association(association):
    normalized = camel_dict_to_snake_dict(association)
    for key, target in (
        ("Targets", "targets"),
        ("TargetMaps", "target_maps"),
    ):
        if key in association:
            normalized[target] = association[key]
    return normalized


def list_associations(client, module):
    associations = []
    next_token = None

    try:
        while True:
            request = {}
            if next_token:
                request["NextToken"] = next_token
            response = client.list_associations(**request)
            associations.extend(response.get("Associations", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Systems Manager associations")

    return associations


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("ssm")

    associations = [
        normalize_association(association)
        for association in list_associations(client, module)
        if association.get("Name")
    ]

    module.exit_json(changed=False, associations=associations)


if __name__ == "__main__":
    main()
