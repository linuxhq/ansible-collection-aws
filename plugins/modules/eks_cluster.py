#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: eks_cluster
short_description: Manage aws elastic kubernetes service clusters
description:
  - Creates, updates, and deletes AWS EKS clusters.
  - Supports modern EKS cluster settings exposed by the EKS API.
author:
  - Taylor Kimball (@tkimball83)
options:
  access_config:
    default:
      authentication_mode: API_AND_CONFIG_MAP
      bootstrap_cluster_creator_admin_permissions: true
    description:
      - The cluster access configuration.
    suboptions:
      authentication_mode:
        choices:
          - API
          - API_AND_CONFIG_MAP
          - CONFIG_MAP
        description:
          - The cluster authentication mode.
        default: API_AND_CONFIG_MAP
        type: str
      bootstrap_cluster_creator_admin_permissions:
        description:
          - Whether to bootstrap admin permissions for the creator.
          - This setting is only used when creating a cluster.
        default: true
        type: bool
    type: dict
  bootstrap_self_managed_addons:
    default: true
    description:
      - Whether to bootstrap self-managed add-ons when creating the cluster.
      - This setting is only used when creating a cluster.
    type: bool
  compute_config:
    description:
      - The EKS Auto Mode compute configuration.
    suboptions:
      enabled:
        description:
          - Whether EKS Auto Mode compute is enabled.
        type: bool
      node_pools:
        description:
          - The EKS Auto Mode node pools.
        elements: str
        type: list
      node_role_arn:
        description:
          - The IAM role ARN used by EKS Auto Mode nodes.
        type: str
    type: dict
  encryption_config:
    description:
      - The cluster encryption configuration.
      - This setting is only used when creating a cluster.
      - This must contain at most one entry.
      - An empty list is treated the same as omitting this option.
    elements: dict
    suboptions:
      provider:
        description:
          - The encryption provider configuration.
        suboptions:
          key_arn:
            description:
              - The KMS key ARN.
            type: str
        type: dict
      resources:
        description:
          - The resources to encrypt.
        elements: str
        type: list
    type: list
  kubernetes_network_config:
    description:
      - The Kubernetes network configuration.
    suboptions:
      elastic_load_balancing:
        description:
          - The EKS Auto Mode load balancing configuration.
          - This requires botocore C(1.35.72) or later.
        suboptions:
          enabled:
            description:
              - Whether EKS Auto Mode load balancing is enabled.
            type: bool
        type: dict
      ip_family:
        choices:
          - ipv4
          - ipv6
        description:
          - The IP family used to assign Kubernetes pod and service addresses.
          - This requires botocore C(1.23.29) or later.
        type: str
      service_ipv4_cidr:
        description:
          - The CIDR block Kubernetes assigns service IP addresses from.
        type: str
    type: dict
  logging:
    description:
      - The cluster control plane logging configuration.
      - The configuration is compared against the current cluster by its
        effective set of enabled log types, so entry grouping does not affect
        idempotency.
    suboptions:
      cluster_logging:
        description:
          - The cluster logging entries.
        elements: dict
        suboptions:
          enabled:
            description:
              - Whether the log types are enabled.
            required: true
            type: bool
          types:
            description:
              - The log types in this entry.
            elements: str
            required: true
            type: list
        type: list
    type: dict
  name:
    description:
      - The EKS cluster name.
    required: true
    type: str
  purge_tags:
    default: true
    description:
      - Whether to remove tags not present in O(tags).
      - This option is only used when O(tags) is provided.
    type: bool
  resources_vpc_config:
    description:
      - The VPC configuration for the cluster.
    suboptions:
      endpoint_private_access:
        description:
          - Whether the Kubernetes API server private endpoint is enabled.
          - When omitted while creating a cluster, AWS uses its default value.
          - When omitted while updating a cluster, the existing value is left unchanged.
          - This requires botocore C(1.12.117) or later.
        type: bool
      endpoint_public_access:
        description:
          - Whether the Kubernetes API server public endpoint is enabled.
          - When omitted while creating a cluster, AWS uses its default value.
          - When omitted while updating a cluster, the existing value is left unchanged.
          - This requires botocore C(1.12.117) or later.
        type: bool
      public_access_cidrs:
        description:
          - CIDR blocks that can access the public Kubernetes API endpoint.
          - This requires botocore C(1.12.117) or later.
        elements: str
        type: list
      security_group_ids:
        description:
          - Security group IDs for the cross-account elastic network interfaces.
        elements: str
        type: list
      subnet_ids:
        description:
          - Subnet IDs for the cluster.
          - Required when creating a cluster.
        elements: str
        type: list
    type: dict
  role_arn:
    description:
      - ARN of the IAM role used by the EKS cluster.
      - Required when creating a cluster.
    type: str
  state:
    choices:
      - absent
      - present
    default: present
    description:
      - Desired state of the EKS cluster.
    type: str
  storage_config:
    description:
      - The EKS Auto Mode storage configuration.
    suboptions:
      block_storage:
        description:
          - The EKS Auto Mode block storage configuration.
        suboptions:
          enabled:
            description:
              - Whether EKS Auto Mode block storage is enabled.
            type: bool
        type: dict
    type: dict
  tags:
    description:
      - Tags to apply to the EKS cluster.
      - A cluster can have at most 50 tags; keys must contain 1 to 128
        characters and values at most 256 characters.
    type: dict
  upgrade_policy:
    default:
      support_type: EXTENDED
    description:
      - The cluster upgrade policy.
    suboptions:
      support_type:
        choices:
          - EXTENDED
          - STANDARD
        description:
          - The support type for the cluster.
        default: EXTENDED
        type: str
    type: dict
  version:
    description:
      - Kubernetes version.
      - Quote the version in playbooks so YAML does not parse values such as
        V(1.30) as the float C(1.3).
    type: str
  wait:
    default: true
    description:
      - Whether to wait for cluster create, update, or delete operations.
    type: bool
  wait_delay:
    default: 15
    description:
      - The delay in seconds between update polling attempts when O(wait=true).
      - This must be 1 or greater.
    type: int
  wait_timeout:
    default: 1200
    description:
      - The maximum number of seconds to wait.
      - This must be 1 or greater.
    type: int
  zonal_shift_config:
    description:
      - The cluster zonal shift configuration.
    suboptions:
      enabled:
        description:
          - Whether zonal shift is enabled.
        type: bool
    type: dict
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure an EKS cluster is present
  linuxhq.aws.eks_cluster:
    name: molecule-eks
    role_arn: arn:aws:iam::123456789012:role/EksClusterRole
    resources_vpc_config:
      subnet_ids:
        - subnet-aaaa1111
        - subnet-bbbb2222
      security_group_ids:
        - sg-aaaa1111
    version: "1.34"
    wait: true

- name: Ensure an EKS cluster is configured
  linuxhq.aws.eks_cluster:
    name: molecule-eks
    access_config:
      authentication_mode: API_AND_CONFIG_MAP
    logging:
      cluster_logging:
        - enabled: true
          types:
            - api
            - audit
    resources_vpc_config:
      endpoint_private_access: true
      endpoint_public_access: false
    tags:
      Name: molecule-eks
      Environment: test
    wait: true

- name: Ensure an EKS cluster is absent
  linuxhq.aws.eks_cluster:
    name: molecule-eks
    state: absent
    wait: true
"""

RETURN = r"""
cluster:
  description:
    - The EKS cluster.
  returned: always
  type: dict
name:
  description:
    - The EKS cluster name.
  returned: always
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import time

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import compare_aws_tags
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiters import get_waiter

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
)

CREATE_FIELDS = [
    "access_config",
    "bootstrap_self_managed_addons",
    "compute_config",
    "encryption_config",
    "kubernetes_network_config",
    "logging",
    "resources_vpc_config",
    "role_arn",
    "storage_config",
    "upgrade_policy",
    "version",
    "zonal_shift_config",
]

UPDATE_CONFIG_FIELDS = [
    "access_config",
    "compute_config",
    "kubernetes_network_config",
    "logging",
    "resources_vpc_config",
    "storage_config",
    "upgrade_policy",
    "zonal_shift_config",
]

CREATE_ONLY_FIELDS = [
    "encryption_config",
    "role_arn",
]

RESOURCES_VPC_CONFIG_ENDPOINT_FIELDS = [
    "endpointPrivateAccess",
    "endpointPublicAccess",
    "publicAccessCidrs",
]

RESOURCES_VPC_CONFIG_NETWORK_FIELDS = [
    "securityGroupIds",
    "subnetIds",
]


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        items = map(normalized, value)
        return sorted({repr(item): item for item in items}.values(), key=repr)
    return value


def comparable_subset(current, desired):
    if not isinstance(desired, dict):
        return current
    current = current or {}
    return {
        key: comparable_subset(current.get(key), value)
        for key, value in desired.items()
    }


def changed(current, desired):
    return normalized(current) != normalized(desired)


def changed_request(current, desired):
    if isinstance(desired, dict):
        current = current or {}
        request = {}
        for key, value in desired.items():
            subrequest = changed_request(current.get(key), value)

            if subrequest is not None:
                request[key] = subrequest
        return request or None
    if changed(current, desired):
        return desired


def require_nested_request_parameters(module, client, operation_name, request):
    operation_parameters = client.meta.service_model.operation_model(
        operation_name
    ).input_shape.members
    for parameter_name in ("kubernetesNetworkConfig", "resourcesVpcConfig"):
        nested_request = request.get(parameter_name)
        if nested_request is None:
            continue
        available_parameters = operation_parameters[parameter_name].members
        for nested_parameter in sorted(nested_request):
            if nested_parameter not in available_parameters:
                module.fail_json(
                    msg=(
                        "Installed botocore does not support EKS "
                        f"{operation_name} {parameter_name} parameter "
                        f"{nested_parameter}"
                    )
                )

        elastic_load_balancing = nested_request.get("elasticLoadBalancing")
        if elastic_load_balancing is None:
            continue
        available_elastic_parameters = available_parameters[
            "elasticLoadBalancing"
        ].members
        for nested_parameter in sorted(elastic_load_balancing):
            if nested_parameter not in available_elastic_parameters:
                module.fail_json(
                    msg=(
                        "Installed botocore does not support EKS "
                        f"{operation_name} {parameter_name} "
                        "elasticLoadBalancing parameter "
                        f"{nested_parameter}"
                    )
                )


def enabled_log_types(logging_config):
    return {
        log_type
        for entry in (logging_config or {}).get("clusterLogging") or []
        if entry.get("enabled")
        for log_type in entry.get("types") or []
    }


def describe_cluster(client, module):
    name = module.params["name"]

    try:
        return client.describe_cluster(
            name=name,
            aws_retry=True,
        ).get("cluster")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe AWS EKS cluster {name}")


def wait_for_cluster(client, module, waiter_name):
    name = module.params["name"]
    waiter = get_waiter(client, waiter_name)
    wait_delay = module.params["wait_delay"]
    attempts = 1 + int(module.params["wait_timeout"] / wait_delay)

    try:
        waiter.wait(
            name=name,
            WaiterConfig={"Delay": wait_delay, "MaxAttempts": attempts},
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Timed out waiting for AWS EKS cluster {name}")


def wait_for_update(client, module, update_id):
    name = module.params["name"]
    wait_delay = module.params["wait_delay"]
    deadline = time.monotonic() + module.params["wait_timeout"]
    last_update = {}
    require_client_methods(
        module,
        client,
        "EKS",
        {"describe_update": ("name", "updateId")},
    )
    while time.monotonic() < deadline:
        try:
            last_update = client.describe_update(
                name=name,
                updateId=update_id,
                aws_retry=True,
            ).get("update", {})
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to describe AWS EKS cluster update "
                    f"{update_id} for {name}"
                ),
            )

        status = last_update.get("status")

        if status == "Successful":
            return last_update
        if status in ("Cancelled", "Failed"):
            module.fail_json(
                msg=(
                    "AWS EKS cluster update " f"{update_id} for {name} {status.lower()}"
                ),
                update=boto3_resource_to_ansible_dict(
                    last_update, transform_tags=False, force_tags=False
                ),
            )
        time.sleep(min(wait_delay, max(0, deadline - time.monotonic())))

    module.fail_json(
        msg=f"Timed out waiting for AWS EKS cluster update {update_id} for {name}",
        update=boto3_resource_to_ansible_dict(
            last_update, transform_tags=False, force_tags=False
        ),
    )


def desired_cluster(module):
    desired = scrub_none_parameters(
        {field: module.params[field] for field in CREATE_FIELDS}
    )

    if desired.get("encryption_config") == []:
        del desired["encryption_config"]

    return desired


def check_mode_cluster(module, current):
    tags = module.params.get("tags")
    cluster = dict(current or {})
    desired = snake_dict_to_camel_dict(desired_cluster(module), capitalize_first=False)
    cluster.update(desired)
    cluster["name"] = module.params["name"]
    if tags is not None:
        current_tags = (
            {} if module.params["purge_tags"] else dict(cluster.get("tags") or {})
        )
        current_tags.update(tags)
        cluster["tags"] = current_tags
    return cluster


def exit_result(module, changed, cluster, state):
    normalized_cluster = boto3_resource_to_ansible_dict(
        cluster or {}, transform_tags=False, force_tags=False
    )

    module.exit_json(
        changed=changed,
        cluster=normalized_cluster,
        name=module.params["name"],
        state=state,
    )


def ensure_present(client, module):
    name = module.params["name"]
    tags = module.params["tags"]
    version = module.params["version"]
    wait = module.params["wait"]
    current = describe_cluster(client, module)
    desired = desired_cluster(module)

    if current is not None and current.get("status") == "DELETING":
        if module.check_mode:
            current = None
        else:
            wait_for_cluster(client, module, "cluster_deleted")
            return ensure_present(client, module)

    if current is None:
        create_request = dict(desired, name=name)
        if tags:
            create_request["tags"] = tags

        create_request = scrub_none_parameters(
            snake_dict_to_camel_dict(create_request, capitalize_first=False)
        )

        if create_request.get("roleArn") is None:
            module.fail_json(msg="role_arn is required to create an EKS cluster")
        if not (create_request.get("resourcesVpcConfig") or {}).get("subnetIds"):
            module.fail_json(
                msg=(
                    "resources_vpc_config.subnet_ids is required to create "
                    "an EKS cluster"
                )
            )

        if module.check_mode:
            exit_result(module, True, check_mode_cluster(module, None), "present")

        require_client_methods(
            module,
            client,
            "EKS",
            {"create_cluster": tuple(create_request)},
        )
        require_nested_request_parameters(
            module, client, "CreateCluster", create_request
        )
        try:
            cluster = client.create_cluster(**create_request, aws_retry=True).get(
                "cluster"
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to create EKS cluster {name}")

        if not (cluster or {}).get("arn"):
            module.fail_json(msg=f"AWS EKS did not return the created cluster {name}")

        if wait:
            wait_for_cluster(client, module, "cluster_active")
            cluster = describe_cluster(client, module)

        exit_result(module, True, cluster, "present")

    if wait and current.get("status") != "ACTIVE":
        wait_for_cluster(client, module, "cluster_active")
        current = describe_cluster(client, module)

    desired_boto3 = snake_dict_to_camel_dict(desired, capitalize_first=False)
    for field in CREATE_ONLY_FIELDS:
        camel_field = next(
            iter(snake_dict_to_camel_dict({field: None}, capitalize_first=False))
        )
        if desired_boto3.get(camel_field) is None:
            continue

        current_value = comparable_subset(
            current, {camel_field: desired_boto3[camel_field]}
        )

        if changed(current_value, {camel_field: desired_boto3[camel_field]}):
            module.fail_json(
                msg=f"Cannot modify {field} for existing EKS cluster {name}"
            )

    config_request = {}
    for field in UPDATE_CONFIG_FIELDS:
        if desired.get(field) is not None:
            config_request[field] = desired[field]

    access_config = config_request.get("access_config")

    if access_config is not None:
        access_config = {
            "authentication_mode": access_config.get("authentication_mode"),
        }
        if scrub_none_parameters(access_config):
            config_request["access_config"] = access_config
        else:
            config_request.pop("access_config")

    if config_request:
        config_request = scrub_none_parameters(
            snake_dict_to_camel_dict(config_request, capitalize_first=False)
        )

    update_requests = []
    for field, value in config_request.items():
        field_request = {field: value}
        update_request = changed_request(current, field_request)

        if update_request is None:
            continue

        if field == "logging" and enabled_log_types(
            update_request.get("logging")
        ) == enabled_log_types(current.get("logging")):
            continue

        if field == "resourcesVpcConfig":
            resources_vpc_config = update_request.get("resourcesVpcConfig") or {}
            endpoint_config = {}
            for endpoint_field in RESOURCES_VPC_CONFIG_ENDPOINT_FIELDS:
                if endpoint_field in resources_vpc_config:
                    endpoint_config[endpoint_field] = resources_vpc_config[
                        endpoint_field
                    ]

            network_config = {}
            for network_field in RESOURCES_VPC_CONFIG_NETWORK_FIELDS:
                if network_field in resources_vpc_config:
                    network_config[network_field] = resources_vpc_config[network_field]

            if endpoint_config:
                update_requests.append({"resourcesVpcConfig": endpoint_config})
            if network_config:
                update_requests.append({"resourcesVpcConfig": network_config})
        else:
            update_requests.append(update_request)

    config_changed = bool(update_requests)
    version_changed = version is not None and version != current.get("version")
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current.get("tags") or {},
            tags,
            purge_tags=module.params["purge_tags"],
        )
        final_tags = dict(current.get("tags") or {})
        for key in tag_keys_to_unset:
            final_tags.pop(key, None)
        final_tags.update(tags_to_set)
        if len(final_tags) > 50:
            module.fail_json(
                msg="The resulting cluster tags must contain at most 50 entries"
            )

    tags_changed = bool(tags_to_set or tag_keys_to_unset)
    cluster_changed = config_changed or version_changed
    resource_changed = cluster_changed or tags_changed

    if resource_changed and not module.check_mode and current.get("status") != "ACTIVE":
        wait_for_cluster(client, module, "cluster_active")
        return ensure_present(client, module)

    if resource_changed and module.check_mode:
        exit_result(module, True, check_mode_cluster(module, current), "present")

    if config_changed:
        for index, update_request in enumerate(update_requests):
            update_request = dict(update_request)
            update_request["name"] = name

            require_client_methods(
                module,
                client,
                "EKS",
                {"update_cluster_config": tuple(update_request)},
            )
            require_nested_request_parameters(
                module, client, "UpdateClusterConfig", update_request
            )
            try:
                update = client.update_cluster_config(
                    **update_request,
                    aws_retry=True,
                ).get("update", {})
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to update EKS cluster {name}")

            update_id = update.get("id")
            if not update_id:
                module.fail_json(
                    msg=f"AWS EKS did not return an update ID for cluster {name}"
                )
            wait_for_next_update = index < len(update_requests) - 1

            if wait or version_changed or wait_for_next_update:
                wait_for_update(client, module, update_id)
                wait_for_cluster(client, module, "cluster_active")

    if version_changed:
        require_client_methods(
            module,
            client,
            "EKS",
            {"update_cluster_version": ("name", "version")},
        )
        try:
            update = client.update_cluster_version(
                name=name,
                version=version,
                aws_retry=True,
            ).get("update", {})
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to update EKS cluster {name} version")

        update_id = update.get("id")
        if not update_id:
            module.fail_json(
                msg=f"AWS EKS did not return a version update ID for cluster {name}"
            )

        if wait:
            wait_for_update(client, module, update_id)
            wait_for_cluster(client, module, "cluster_active")

    if tags_changed:
        arn = current.get("arn")

        if not arn:
            module.fail_json(msg=f"Unable to tag EKS cluster {name}")

        if tag_keys_to_unset:
            require_client_methods(
                module,
                client,
                "EKS",
                {"untag_resource": ("resourceArn", "tagKeys")},
            )
            try:
                client.untag_resource(
                    resourceArn=arn,
                    tagKeys=tag_keys_to_unset,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e, msg=f"Unable to remove tags from EKS cluster {name}"
                )

        if tags_to_set:
            require_client_methods(
                module,
                client,
                "EKS",
                {"tag_resource": ("resourceArn", "tags")},
            )
            try:
                client.tag_resource(
                    resourceArn=arn,
                    tags=tags_to_set,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to tag EKS cluster {name}")

    if cluster_changed:
        if wait:
            current = describe_cluster(client, module) or check_mode_cluster(
                module, current
            )
        else:
            current = check_mode_cluster(module, current)
    elif tags_changed:
        current = dict(current)
        current_tags = dict(current.get("tags") or {})

        for tag_key in tag_keys_to_unset:
            current_tags.pop(tag_key, None)
        current_tags.update(tags_to_set)
        current["tags"] = current_tags

    exit_result(module, resource_changed, current, "present")


def ensure_absent(client, module):
    name = module.params["name"]
    current = describe_cluster(client, module)

    if current is None:
        exit_result(module, False, {}, "absent")

    if current.get("status") == "DELETING":
        if module.params["wait"] and not module.check_mode:
            wait_for_cluster(client, module, "cluster_deleted")
        exit_result(module, False, current, "absent")

    if module.check_mode:
        exit_result(module, True, current, "absent")

    if current.get("status") in {"CREATING", "PENDING", "UPDATING"}:
        wait_for_cluster(client, module, "cluster_active")

    require_client_methods(
        module,
        client,
        "EKS",
        {"delete_cluster": ("name",)},
    )
    try:
        client.delete_cluster(name=name, aws_retry=True)
    except is_boto3_error_code("ResourceNotFoundException"):
        pass
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to delete EKS cluster {name}")

    if module.params["wait"]:
        wait_for_cluster(client, module, "cluster_deleted")

    exit_result(module, True, current, "absent")


def main():
    argument_spec = {
        "access_config": {
            "default": {
                "authentication_mode": "API_AND_CONFIG_MAP",
                "bootstrap_cluster_creator_admin_permissions": True,
            },
            "options": {
                "authentication_mode": {
                    "choices": ["API", "API_AND_CONFIG_MAP", "CONFIG_MAP"],
                    "default": "API_AND_CONFIG_MAP",
                    "type": "str",
                },
                "bootstrap_cluster_creator_admin_permissions": {
                    "default": True,
                    "type": "bool",
                },
            },
            "type": "dict",
        },
        "bootstrap_self_managed_addons": {"default": True, "type": "bool"},
        "compute_config": {
            "options": {
                "enabled": {"type": "bool"},
                "node_pools": {"elements": "str", "type": "list"},
                "node_role_arn": {"type": "str"},
            },
            "type": "dict",
        },
        "encryption_config": {
            "elements": "dict",
            "options": {
                "provider": {
                    "options": {
                        "key_arn": {"no_log": False, "type": "str"},
                    },
                    "type": "dict",
                },
                "resources": {"elements": "str", "type": "list"},
            },
            "type": "list",
        },
        "kubernetes_network_config": {
            "options": {
                "elastic_load_balancing": {
                    "options": {
                        "enabled": {"type": "bool"},
                    },
                    "type": "dict",
                },
                "ip_family": {"choices": ["ipv4", "ipv6"], "type": "str"},
                "service_ipv4_cidr": {"type": "str"},
            },
            "type": "dict",
        },
        "logging": {
            "options": {
                "cluster_logging": {
                    "elements": "dict",
                    "options": {
                        "enabled": {"required": True, "type": "bool"},
                        "types": {
                            "elements": "str",
                            "required": True,
                            "type": "list",
                        },
                    },
                    "type": "list",
                },
            },
            "type": "dict",
        },
        "name": {"required": True, "type": "str"},
        "purge_tags": {"default": True, "type": "bool"},
        "resources_vpc_config": {
            "options": {
                "endpoint_private_access": {"type": "bool"},
                "endpoint_public_access": {"type": "bool"},
                "public_access_cidrs": {"elements": "str", "type": "list"},
                "security_group_ids": {"elements": "str", "type": "list"},
                "subnet_ids": {"elements": "str", "type": "list"},
            },
            "type": "dict",
        },
        "role_arn": {"type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "storage_config": {
            "options": {
                "block_storage": {
                    "options": {
                        "enabled": {"type": "bool"},
                    },
                    "type": "dict",
                },
            },
            "type": "dict",
        },
        "tags": {"type": "dict"},
        "upgrade_policy": {
            "default": {"support_type": "EXTENDED"},
            "options": {
                "support_type": {
                    "choices": ["EXTENDED", "STANDARD"],
                    "default": "EXTENDED",
                    "type": "str",
                },
            },
            "type": "dict",
        },
        "version": {"type": "str"},
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 15, "type": "int"},
        "wait_timeout": {"default": 1200, "type": "int"},
        "zonal_shift_config": {
            "options": {
                "enabled": {"type": "bool"},
            },
            "type": "dict",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    state = module.params["state"]
    tags = module.params.get("tags")
    require_valid_tags(module, tags if state == "present" else None, 50)
    if state == "present" and len(module.params["encryption_config"] or []) > 1:
        module.fail_json(msg="encryption_config must contain at most one entry")
    require_positive_wait_bounds(module, always=True)

    client = module.client("eks", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "EKS",
        {"describe_cluster": ("name",)},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
