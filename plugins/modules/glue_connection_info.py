#!/usr/bin/python

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: glue_connection_info
version_added: "1.9.5"
short_description: Gather information about AWS Glue connections
description:
  - Gathers information about AWS Glue connections.
author:
  - Taylor Kimball (@tkimball83)
options:
  apply_override_for_compute_environment:
    description:
      - Whether to apply an override for the compute environment when getting
        selected Glue connections by O(names).
    type: bool
  catalog_id:
    description:
      - The ID of the Data Catalog in which the connections reside.
    type: str
  filters:
    description:
      - A dict of filters to apply when listing Glue connections.
      - Filter keys and values are passed to the Glue C(GetConnections) API.
    type: dict
  hide_password:
    default: true
    description:
      - Whether to hide passwords in the returned connection properties.
    type: bool
  names:
    description:
      - Glue connection names used to limit the result set.
      - When set, the module uses the Glue C(GetConnection) API.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about Glue connections
  linuxhq.aws.glue_connection_info:

- name: Gather information about selected Glue connections
  linuxhq.aws.glue_connection_info:
    names:
      - molecule

- name: Gather information about Glue connections using filters
  linuxhq.aws.glue_connection_info:
    filters:
      connection_type: NETWORK
"""

RETURN = r"""
connections:
  description:
    - A list of AWS Glue connections.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    scrub_none_parameters,
)


def get_connection(client, module, name):
    try:
        return client.get_connection(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "apply_override_for_compute_environment": module.params[
                            "apply_override_for_compute_environment"
                        ],
                        "catalog_id": module.params["catalog_id"],
                        "hide_password": module.params["hide_password"],
                        "name": name,
                    },
                    capitalize_first=True,
                )
            ),
            aws_retry=True,
        ).get("Connection")
    except is_boto3_error_code("EntityNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS Glue connection {name}")


def list_connections(client, module):
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "catalog_id": module.params["catalog_id"],
                "hide_password": module.params["hide_password"],
            },
            capitalize_first=True,
        )
    )
    if module.params["filters"]:
        request["Filter"] = snake_dict_to_camel_dict(
            module.params["filters"], capitalize_first=True
        )
    return paginated_query_with_retries(
        client,
        "get_connections",
        **request,
    ).get("ConnectionList", [])


def main():
    argument_spec = {
        "apply_override_for_compute_environment": {"type": "bool"},
        "catalog_id": {"type": "str"},
        "filters": {"type": "dict"},
        "hide_password": {"default": True, "no_log": False, "type": "bool"},
        "names": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("glue", retry_decorator=AWSRetry.jittered_backoff())
    if module.params["names"]:
        connections = [
            connection
            for connection in [
                get_connection(client, module, name) for name in module.params["names"]
            ]
            if connection
        ]
    else:
        connections = list_connections(client, module)

    module.exit_json(
        changed=False,
        connections=boto3_resource_list_to_ansible_dict(
            connections,
            ignore_list=["ConnectionProperties"],
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
