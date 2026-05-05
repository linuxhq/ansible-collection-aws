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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
    aws_resource_matches,
)


def normalize_association(association):
    return aws_resource_to_snake_dict(association, ignore_list=["TargetMaps"])


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("ssm")

    associations = [
        normalize_association(association)
        for association in aws_paginated_list(
            client,
            module,
            "list_associations",
            "Associations",
        )
        if not aws_resource_matches(association, name=None)
    ]

    module.exit_json(changed=False, associations=associations)


if __name__ == "__main__":
    main()
