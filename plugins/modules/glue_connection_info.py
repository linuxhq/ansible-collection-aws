#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: glue_connection_info
short_description: Gather information about AWS Glue connections
version_added: "1.9.0"
description:
  - Gathers information about AWS Glue connections.
author:
  - Taylor Kimball (@tkimball83)
options:
  apply_override_for_compute_environment:
    description:
      - The compute environment whose overridden properties to retrieve for
        the selected Glue connection in O(name).
      - Requires O(name).
    choices: [SPARK, ATHENA, PYTHON]
    type: str
  catalog_id:
    description:
      - The ID of the Data Catalog in which the connections reside.
    type: str
  filters:
    description:
      - The filter to apply when listing Glue connections.
      - Passed unchanged to the Glue C(GetConnections) API as C(Filter), so keys
        use the API field names C(ConnectionType), C(ConnectionSchemaVersion),
        and C(MatchCriteria).
      - Mutually exclusive with O(name).
    type: dict
  hide_password:
    default: true
    description:
      - Whether to hide passwords in the returned connection properties.
      - Setting this to V(false) returns secrets in C(connection_properties)
        that Ansible does not mask; register and handle the result with care.
    type: bool
  name:
    description:
      - Glue connection name used to limit the result set.
      - When set, the module uses the Glue C(GetConnection) API.
      - A connection that does not exist results in an empty list.
      - Mutually exclusive with O(filters).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module does not modify state.
    support: full
  diff_mode:
    description: This module does not modify state.
    support: none
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
      ConnectionType: NETWORK
"""

RETURN = r"""
connections:
  description:
    - A list of AWS Glue connections.
    - Keys in C(connection_properties), C(spark_properties), C(athena_properties),
      C(python_properties), and C(token_url_parameters_map) are returned as provided by the Glue API.
  returned: always
  type: list
  elements: dict
  contains:
    athena_properties:
      description: Athena compute environment properties.
      returned: when configured
      type: dict
    authentication_configuration:
      description: The connection authentication configuration.
      returned: when configured
      type: dict
      contains:
        authentication_type:
          description: The authentication type.
          returned: when configured
          type: str
        kms_key_arn:
          description: The KMS key ARN used to encrypt the connection.
          returned: when configured
          type: str
        o_auth2_properties:
          description: The OAuth2 properties.
          returned: when configured
          type: dict
          contains:
            o_auth2_client_application:
              description: The OAuth2 client application.
              returned: when configured
              type: dict
            o_auth2_grant_type:
              description: The OAuth2 grant type.
              returned: when configured
              type: str
            token_url:
              description: The OAuth2 token URL.
              returned: when configured
              type: str
            token_url_parameters_map:
              description: Parameters added to the token request, with keys as provided by the Glue API.
              returned: when configured
              type: dict
        secret_arn:
          description: The Secrets Manager secret ARN that stores the credentials.
          returned: when configured
          type: str
    compatible_compute_environments:
      description: The compute environments that support the connection.
      returned: when returned by AWS
      type: list
      elements: str
    connection_properties:
      description: Connection configuration properties returned by AWS Glue.
      returned: when configured
      type: dict
    connection_schema_version:
      description: The connection schema version.
      returned: when returned by AWS
      type: int
    connection_type:
      description: The connection type.
      returned: when configured
      type: str
    creation_time:
      description: The time the connection was created.
      returned: when returned by AWS
      type: str
    description:
      description: The connection description.
      returned: when configured
      type: str
    last_connection_validation_time:
      description: The time the connection was last validated.
      returned: when returned by AWS
      type: str
    last_updated_by:
      description: The user, group, or role that last updated the connection.
      returned: when returned by AWS
      type: str
    last_updated_time:
      description: The time the connection was last updated.
      returned: when returned by AWS
      type: str
    match_criteria:
      description: The criteria used to select the connection.
      returned: when configured
      type: list
      elements: str
    name:
      description: The connection name.
      returned: always
      type: str
    physical_connection_requirements:
      description: The network requirements for the connection.
      returned: when configured
      type: dict
      contains:
        availability_zone:
          description: The connection Availability Zone.
          returned: when configured
          type: str
        security_group_id_list:
          description: The connection security group IDs.
          returned: when configured
          type: list
          elements: str
        subnet_id:
          description: The connection subnet ID.
          returned: when configured
          type: str
    python_properties:
      description: Python compute environment properties.
      returned: when configured
      type: dict
    spark_properties:
      description: Spark compute environment properties.
      returned: when configured
      type: dict
    status:
      description: The connection status.
      returned: when returned by AWS
      type: str
    status_reason:
      description: The reason for the connection status.
      returned: when returned by AWS
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_connections(module, connections):
    if not isinstance(connections, list) or any(not isinstance(connection, dict) for connection in connections):
        module.fail_json(msg="Unable to get AWS Glue connections: AWS returned an invalid response")

    return connections


def main():
    argument_spec = {
        "apply_override_for_compute_environment": {"choices": ["SPARK", "ATHENA", "PYTHON"], "type": "str"},
        "catalog_id": {"type": "str"},
        "filters": {"type": "dict"},
        "hide_password": {"default": True, "no_log": False, "type": "bool"},
        "name": {"type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["name", "filters"]],
        required_by={"apply_override_for_compute_environment": ["name"]},
        supports_check_mode=True,
    )
    client = module.client("glue", retry_decorator=AWSRetry.jittered_backoff())

    apply_override = module.params["apply_override_for_compute_environment"]
    catalog_id = module.params["catalog_id"]
    filters = module.params["filters"]
    name = module.params["name"]

    required_parameters = []
    if name and apply_override is not None:
        required_parameters.append("ApplyOverrideForComputeEnvironment")

    if catalog_id:
        required_parameters.append("CatalogId")

    if not name and filters:
        required_parameters.append("Filter")

    required_parameters.append("HidePassword")
    if name:
        required_parameters.append("Name")
    else:
        required_parameters.extend(("MaxResults", "NextToken"))

    require_client_methods(
        module,
        client,
        "AWS Glue",
        {"get_connection" if name else "get_connections": tuple(required_parameters)},
    )

    request = {"HidePassword": module.params["hide_password"]}
    if catalog_id:
        request["CatalogId"] = catalog_id

    if name:
        request["Name"] = name
        if apply_override is not None:
            request["ApplyOverrideForComputeEnvironment"] = apply_override

        try:
            response = client.get_connection(**request, aws_retry=True)
        except is_boto3_error_code("EntityNotFoundException"):
            connection = None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to get AWS Glue connection {name}")
        else:
            if not isinstance(response, dict) or not isinstance(response.get("Connection"), dict):
                module.fail_json(msg=f"Unable to get AWS Glue connection {name}: AWS returned an invalid response")

            connection = response["Connection"]

        connections = [connection] if connection else []
    else:
        if filters:
            request["Filter"] = filters

        connections = query_list(
            module,
            client,
            "get_connections",
            "ConnectionList",
            "Unable to list AWS Glue connections",
            **request,
        )

    connections = validate_connections(module, connections)

    results = boto3_resource_list_to_ansible_dict(
        connections,
        ignore_list=["AthenaProperties", "ConnectionProperties", "PythonProperties", "SparkProperties"],
        transform_tags=False,
        force_tags=False,
    )
    for result, connection in zip(results, connections):
        # ignore_list only applies to top-level keys; keep these user-defined parameter names unchanged.
        oauth2 = (connection.get("AuthenticationConfiguration") or {}).get("OAuth2Properties") or {}
        if isinstance(oauth2.get("TokenUrlParametersMap"), dict):
            result["authentication_configuration"]["o_auth2_properties"]["token_url_parameters_map"] = dict(
                oauth2["TokenUrlParametersMap"]
            )

    module.exit_json(changed=False, connections=results)


if __name__ == "__main__":
    main()
