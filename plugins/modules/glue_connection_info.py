#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: glue_connection_info
short_description: Gather information about aws glue connections
description:
  - Gathers information about AWS Glue connections.
author:
  - Taylor Kimball (@tkimball83)
options:
  apply_override_for_compute_environment:
    description:
      - Whether to apply an override for the compute environment when getting
        a selected Glue connection by O(name).
      - Requires O(name).
    type: bool
  catalog_id:
    description:
      - The ID of the Data Catalog in which the connections reside.
    type: str
  filters:
    description:
      - A dict of filters to apply when listing Glue connections.
      - Filter keys and values are passed to the Glue C(GetConnections) API.
      - Mutually exclusive with O(name).
    type: dict
  hide_password:
    default: true
    description:
      - Whether to hide passwords in the returned connection properties.
    type: bool
  name:
    description:
      - Glue connection name used to limit the result set.
      - When set, the module uses the Glue C(GetConnection) API.
      - Mutually exclusive with O(filters).
    type: str
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
    name: molecule

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
)


def main():
    argument_spec = {
        "apply_override_for_compute_environment": {"type": "bool"},
        "catalog_id": {"type": "str"},
        "filters": {"type": "dict"},
        "hide_password": {"default": True, "no_log": False, "type": "bool"},
        "name": {"type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["name", "filters"]],
        required_by={"apply_override_for_compute_environment": "name"},
        supports_check_mode=True,
    )
    client = module.client("glue", retry_decorator=AWSRetry.jittered_backoff())
    if module.params["name"]:
        request = {
            "HidePassword": module.params["hide_password"],
            "Name": module.params["name"],
        }
        if module.params["apply_override_for_compute_environment"] is not None:
            request["ApplyOverrideForComputeEnvironment"] = module.params[
                "apply_override_for_compute_environment"
            ]
        if module.params["catalog_id"] is not None:
            request["CatalogId"] = module.params["catalog_id"]

        try:
            connection = client.get_connection(**request, aws_retry=True).get(
                "Connection"
            )
        except is_boto3_error_code("EntityNotFoundException"):
            connection = None
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to get AWS Glue connection {module.params['name']}"
            )

        connections = [connection] if connection else []
    else:
        request = {"HidePassword": module.params["hide_password"]}
        if module.params["catalog_id"] is not None:
            request["CatalogId"] = module.params["catalog_id"]
        if module.params["filters"]:
            request["Filter"] = snake_dict_to_camel_dict(
                module.params["filters"], capitalize_first=True
            )

        try:
            connections = paginated_query_with_retries(
                client,
                "get_connections",
                **request,
            ).get("ConnectionList", [])
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to list AWS Glue connections")

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
