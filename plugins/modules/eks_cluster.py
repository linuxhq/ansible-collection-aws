#!/usr/bin/python
# -*- coding: utf-8 -*-
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
        type: str
      service_ipv4_cidr:
        description:
          - The CIDR block Kubernetes assigns service IP addresses from.
        type: str
    type: dict
  logging:
    description:
      - The cluster control plane logging configuration.
    suboptions:
      cluster_logging:
        description:
          - The cluster logging entries.
        elements: dict
        suboptions:
          enabled:
            description:
              - Whether the log types are enabled.
            type: bool
          types:
            description:
              - The log types in this entry.
            elements: str
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
        type: bool
      endpoint_public_access:
        description:
          - Whether the Kubernetes API server public endpoint is enabled.
          - When omitted while creating a cluster, AWS uses its default value.
          - When omitted while updating a cluster, the existing value is left unchanged.
        type: bool
      public_access_cidrs:
        description:
          - CIDR blocks that can access the public Kubernetes API endpoint.
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
    type: int
  wait_timeout:
    default: 1200
    description:
      - The maximum number of seconds to wait.
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

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
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
        result = {}
        for key in sorted(value):
            result[key] = normalized(value[key])
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.append(normalized(item))
        return sorted(result, key=repr)
    return value


def comparable_subset(current, desired):
    if isinstance(desired, dict):
        current = current or {}
        result = {}
        for key, value in desired.items():
            result[key] = comparable_subset(current.get(key), value)
        return result
    return current


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


def describe_cluster(client, module):
    name = module.params["name"]

    try:
        return client.describe_cluster(
            name=name,
            aws_retry=True,
        ).get("cluster")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to describe AWS EKS cluster {name}")


def wait_for_cluster(client, module, waiter_name):
    name = module.params["name"]
    waiter = get_waiter(client, waiter_name)
    attempts = 1 + int(module.params["wait_timeout"] / waiter.config.delay)

    try:
        waiter.wait(
            name=name,
            WaiterConfig={"MaxAttempts": attempts},
        )
    except Exception as e:
        module.fail_json_aws(e, msg=f"Timed out waiting for AWS EKS cluster {name}")


def wait_for_update(client, module, update_id):
    name = module.params["name"]
    wait_delay = max(1, module.params["wait_delay"])
    deadline = time.time() + module.params["wait_timeout"]
    last_update = {}
    while time.time() < deadline:
        try:
            last_update = client.describe_update(
                name=name,
                updateId=update_id,
                aws_retry=True,
            ).get("update", {})
        except Exception as e:
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
        time.sleep(min(wait_delay, max(1, int(deadline - time.time()))))

    module.fail_json(
        msg=f"Timed out waiting for AWS EKS cluster update {update_id} for {name}",
        update=boto3_resource_to_ansible_dict(
            last_update, transform_tags=False, force_tags=False
        ),
    )


def desired_cluster(module):
    desired = {}
    for field in CREATE_FIELDS:
        desired[field] = module.params[field]
    return scrub_none_parameters(desired)


def check_mode_cluster(module, current):
    tags = module.params["tags"]
    cluster = dict(current or {})
    desired = snake_dict_to_camel_dict(desired_cluster(module), capitalize_first=False)
    cluster.update(desired)
    cluster["name"] = module.params["name"]
    if tags is not None:
        cluster["tags"] = tags
    return cluster


def exit_result(module, changed, cluster, state):
    normalized_cluster = boto3_resource_to_ansible_dict(
        cluster or {}, transform_tags=False, force_tags=False
    )

    result = {
        "changed": changed,
        "cluster": normalized_cluster,
        "name": module.params["name"],
        "state": state,
    }
    result.update(normalized_cluster)
    module.exit_json(**result)


def ensure_present(client, module):
    name = module.params["name"]
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"] if tags is not None else False
    version = module.params["version"]
    wait = module.params["wait"]
    current = describe_cluster(client, module)
    desired = desired_cluster(module)
    create_request = dict(desired, name=name)
    if tags is not None:
        create_request["tags"] = tags
    create_request = scrub_none_parameters(
        snake_dict_to_camel_dict(create_request, capitalize_first=False)
    )

    if current is None:
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

        try:
            cluster = client.create_cluster(**create_request, aws_retry=True).get(
                "cluster"
            )
        except Exception as e:
            module.fail_json_aws(e, msg=f"Unable to create EKS cluster {name}")

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
            purge_tags=purge_tags,
        )

    tags_changed = bool(tags_to_set or tag_keys_to_unset)
    cluster_changed = config_changed or version_changed
    resource_changed = cluster_changed or tags_changed

    if resource_changed and module.check_mode:
        exit_result(module, True, check_mode_cluster(module, current), "present")

    if config_changed:
        for index, update_request in enumerate(update_requests):
            update_request = dict(update_request)
            update_request["name"] = name

            try:
                update = client.update_cluster_config(
                    **update_request,
                    aws_retry=True,
                ).get("update", {})
            except Exception as e:
                module.fail_json_aws(e, msg=f"Unable to update EKS cluster {name}")

            update_id = update.get("id")
            wait_for_next_update = index < len(update_requests) - 1

            if update_id and (wait or version_changed or wait_for_next_update):
                wait_for_update(client, module, update_id)
                wait_for_cluster(client, module, "cluster_active")

    if version_changed:
        try:
            update = client.update_cluster_version(
                name=name,
                version=version,
                aws_retry=True,
            ).get("update", {})
        except Exception as e:
            module.fail_json_aws(e, msg=f"Unable to update EKS cluster {name} version")

        update_id = update.get("id")

        if update_id and wait:
            wait_for_update(client, module, update_id)
            wait_for_cluster(client, module, "cluster_active")

    if tags_changed:
        arn = current.get("arn")

        if not arn:
            module.fail_json(msg=f"Unable to tag EKS cluster {name}")

        if tag_keys_to_unset:
            try:
                client.untag_resource(
                    resourceArn=arn,
                    tagKeys=tag_keys_to_unset,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to remove tags from EKS cluster {name}"
                )

        if tags_to_set:
            try:
                client.tag_resource(
                    resourceArn=arn,
                    tags=tags_to_set,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(e, msg=f"Unable to tag EKS cluster {name}")

    if cluster_changed:
        current = describe_cluster(client, module)
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

    if module.check_mode:
        exit_result(module, True, current, "absent")

    try:
        client.delete_cluster(name=name, aws_retry=True)
    except Exception as e:
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
                        "enabled": {"type": "bool"},
                        "types": {"elements": "str", "type": "list"},
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
    client = module.client("eks", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"] if tags is not None else False
    desired = desired_cluster(module)
    method_names = {"describe_cluster"}

    if state == "present":
        method_names.update(
            {
                "create_cluster",
                "describe_update",
                "update_cluster_config",
            }
        )
        if module.params["version"] is not None:
            method_names.add("update_cluster_version")
        if tags is not None:
            method_names.add("tag_resource")
            if purge_tags:
                method_names.add("untag_resource")
    elif state == "absent":
        method_names.add("delete_cluster")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support EKS {method_name}"
            )

    create_cluster_parameters = {"name"}
    for field in CREATE_FIELDS:
        if desired.get(field) is None:
            continue

        create_cluster_parameters.update(
            snake_dict_to_camel_dict({field: None}, capitalize_first=False)
        )
    if tags is not None:
        create_cluster_parameters.add("tags")

    update_cluster_config_parameters = {"name"}
    for field in UPDATE_CONFIG_FIELDS:
        if desired.get(field) is None:
            continue

        update_cluster_config_parameters.update(
            snake_dict_to_camel_dict({field: None}, capitalize_first=False)
        )

    required_method_parameters = {
        "create_cluster": create_cluster_parameters,
        "delete_cluster": {"name"},
        "describe_cluster": {"name"},
        "describe_update": {"name", "updateId"},
        "tag_resource": {"resourceArn", "tags"},
        "untag_resource": {"resourceArn", "tagKeys"},
        "update_cluster_config": update_cluster_config_parameters,
        "update_cluster_version": {"name", "version"},
    }

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support EKS "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
