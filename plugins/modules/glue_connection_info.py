#!/usr/bin/python

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: glue_connection_info
version_added: 1.9.1
short_description: Gather information about AWS Glue connections
description:
  - Gathers information about AWS Glue connections.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about Glue connections
  linuxhq.aws.glue_connection_info:
"""

RETURN = r"""
connections:
  description:
    - A list of AWS Glue connections.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
)


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("glue")

    module.exit_json(
        changed=False,
        connections=aws_resource_list_to_snake_dicts(
            aws_paginated_list(
                client,
                module,
                "get_connections",
                "ConnectionList",
            ),
            ignore_list=["ConnectionProperties"],
        ),
    )


if __name__ == "__main__":
    main()
