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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def normalize_connection(connection):
    normalized = camel_dict_to_snake_dict(connection)
    if "ConnectionProperties" in connection:
        normalized["connection_properties"] = connection["ConnectionProperties"]
    return normalized


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("glue")

    connections = []
    next_token = None

    try:
        while True:
            request = {}
            if next_token:
                request["NextToken"] = next_token

            response = client.get_connections(**request)
            connections.extend(response.get("ConnectionList", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get AWS Glue connections")

    module.exit_json(
        changed=False,
        connections=[normalize_connection(connection) for connection in connections],
    )


if __name__ == "__main__":
    main()
