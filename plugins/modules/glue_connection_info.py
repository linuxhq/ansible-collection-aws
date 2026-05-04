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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def normalize_connection(connection):
    return boto3_resource_to_ansible_dict(
        connection,
        force_tags=False,
        ignore_list=["ConnectionProperties"],
    )


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("glue")

    try:
        response = paginated_query_with_retries(client, "get_connections")
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get AWS Glue connections")

    module.exit_json(
        changed=False,
        connections=[
            normalize_connection(connection)
            for connection in response.get("ConnectionList", [])
        ],
    )


if __name__ == "__main__":
    main()
