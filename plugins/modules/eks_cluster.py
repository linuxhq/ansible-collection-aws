#!/usr/bin/python
# Copyright: Taylor Kimball
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
    type: bool
  resources_vpc_config:
    description:
      - The VPC configuration for the cluster.
    suboptions:
      endpoint_private_access:
        default: false
        description:
          - Whether the Kubernetes API server private endpoint is enabled.
        type: bool
      endpoint_public_access:
        default: true
        description:
          - Whether the Kubernetes API server public endpoint is enabled.
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

from ansible.module_utils.basic import _load_params
from ansible.module_utils.common.dict_transformations import (
    recursive_diff,
    snake_dict_to_camel_dict,
)
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

RESOURCES_VPC_CONFIG_FIELDS = [
    "endpoint_private_access",
    "endpoint_public_access",
    "public_access_cidrs",
    "security_group_ids",
    "subnet_ids",
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
        return sorted((normalized(item) for item in value), key=repr)
    return value


def comparable_subset(current, desired):
    if isinstance(desired, dict):
        current = current or {}
        return {
            key: comparable_subset(current.get(key), value)
            for key, value in desired.items()
        }
    return current


def changed(current, desired):
    current = normalized(current)
    desired = normalized(desired)
    if isinstance(current, dict) and isinstance(desired, dict):
        return recursive_diff(current, desired) is not None
    return current != desired


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
    return None


def describe_cluster(client, module):
    try:
        return client.describe_cluster(
            name=module.params["name"],
            aws_retry=True,
        ).get("cluster")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to describe AWS EKS cluster {module.params['name']}"
        )


def wait_for_cluster(client, module, waiter_name):
    waiter = get_waiter(client, waiter_name)
    attempts = 1 + int(module.params["wait_timeout"] / waiter.config.delay)
    try:
        waiter.wait(
            name=module.params["name"],
            WaiterConfig={"MaxAttempts": attempts},
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Timed out waiting for AWS EKS cluster {module.params['name']}"
        )


def wait_for_update(client, module, update_id):
    deadline = time.time() + module.params["wait_timeout"]
    last_update = {}
    while time.time() < deadline:
        try:
            last_update = client.describe_update(
                name=module.params["name"],
                updateId=update_id,
                aws_retry=True,
            ).get("update", {})
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to describe AWS EKS cluster update "
                    f"{update_id} for {module.params['name']}"
                ),
            )
        status = last_update.get("status")
        if status == "Successful":
            return last_update
        if status in ("Cancelled", "Failed"):
            module.fail_json(
                msg=(
                    "AWS EKS cluster update "
                    f"{update_id} for {module.params['name']} {status.lower()}"
                ),
                update=boto3_resource_to_ansible_dict(
                    last_update, transform_tags=False, force_tags=False
                ),
            )
        time.sleep(min(15, max(1, int(deadline - time.time()))))

    module.fail_json(
        msg=(
            "Timed out waiting for AWS EKS cluster update "
            f"{update_id} for {module.params['name']}"
        ),
        update=boto3_resource_to_ansible_dict(
            last_update, transform_tags=False, force_tags=False
        ),
    )


def desired_cluster(module):
    desired = {
        field: module.params[field]
        for field in CREATE_FIELDS
        if field != "resources_vpc_config"
    }
    desired["resources_vpc_config"] = module.params["resources_vpc_config"]
    return scrub_none_parameters(desired)


def create_request(module):
    desired = desired_cluster(module)
    request = {
        field: desired.get(field)
        for field in CREATE_FIELDS
        if desired.get(field) is not None
    }
    request["name"] = module.params["name"]
    if module.params["tags"] is not None:
        request["tags"] = module.params["tags"]
    return scrub_none_parameters(
        snake_dict_to_camel_dict(request, capitalize_first=False)
    )


def update_config_request(module):
    desired = desired_cluster(module)
    request = {}
    for field in UPDATE_CONFIG_FIELDS:
        if desired.get(field) is not None:
            request[field] = desired[field]

    resources_vpc_config = explicit_resources_vpc_config(module, request)
    if resources_vpc_config:
        request["resources_vpc_config"] = resources_vpc_config
    else:
        request.pop("resources_vpc_config", None)

    access_config = request.get("access_config")
    if access_config is not None:
        access_config = {
            "authentication_mode": access_config.get("authentication_mode"),
        }
        if scrub_none_parameters(access_config):
            request["access_config"] = access_config
        else:
            request.pop("access_config")

    if not request:
        return {}
    return scrub_none_parameters(
        snake_dict_to_camel_dict(request, capitalize_first=False)
    )


def explicit_resources_vpc_config(module, request):
    raw_resources_vpc_config = (
        getattr(module, "_linuxhq_raw_params", {}).get("resources_vpc_config") or {}
    )
    resources_vpc_config = request.get("resources_vpc_config") or {}
    return {
        field: resources_vpc_config.get(field)
        for field in RESOURCES_VPC_CONFIG_FIELDS
        if field in raw_resources_vpc_config
        and resources_vpc_config.get(field) is not None
    }


def update_config_requests(current, request):
    requests = []
    for field, value in request.items():
        field_request = {field: value}
        update_request = changed_request(current, field_request)
        if update_request is None:
            continue
        if field == "resourcesVpcConfig":
            requests.extend(resources_vpc_config_update_requests(update_request))
        else:
            requests.append(update_request)
    return requests


def resources_vpc_config_update_requests(request):
    resources_vpc_config = request.get("resourcesVpcConfig") or {}
    requests = []
    endpoint_config = {
        field: resources_vpc_config[field]
        for field in RESOURCES_VPC_CONFIG_ENDPOINT_FIELDS
        if field in resources_vpc_config
    }
    network_config = {
        field: resources_vpc_config[field]
        for field in RESOURCES_VPC_CONFIG_NETWORK_FIELDS
        if field in resources_vpc_config
    }
    if endpoint_config:
        requests.append({"resourcesVpcConfig": endpoint_config})
    if network_config:
        requests.append({"resourcesVpcConfig": network_config})
    return requests


def validate_create(module, request):
    if request.get("roleArn") is None:
        module.fail_json(msg="role_arn is required to create an EKS cluster")
    if not (request.get("resourcesVpcConfig") or {}).get("subnetIds"):
        module.fail_json(
            msg="resources_vpc_config.subnet_ids is required to create an EKS cluster"
        )


def validate_create_only_fields(module, current):
    desired = scrub_none_parameters(
        snake_dict_to_camel_dict(desired_cluster(module), capitalize_first=False)
    )
    for field in CREATE_ONLY_FIELDS:
        camel_field = snake_dict_to_camel_dict(
            {field: None}, capitalize_first=False
        ).keys()
        camel_field = next(iter(camel_field))
        if desired.get(camel_field) is None:
            continue
        current_value = comparable_subset(current, {camel_field: desired[camel_field]})
        if changed(current_value, {camel_field: desired[camel_field]}):
            module.fail_json(
                msg=(
                    f"Cannot modify {field} for existing EKS cluster "
                    f"{module.params['name']}"
                )
            )


def apply_tag_changes(client, module, cluster, tags_to_set, tag_keys_to_unset):
    arn = cluster.get("arn")
    if not arn:
        module.fail_json(msg=f"Unable to tag EKS cluster {module.params['name']}")

    if tag_keys_to_unset:
        try:
            client.untag_resource(
                resourceArn=arn,
                tagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to remove tags from EKS cluster {module.params['name']}"
            )

    if tags_to_set:
        try:
            client.tag_resource(
                resourceArn=arn,
                tags=tags_to_set,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to tag EKS cluster {module.params['name']}"
            )


def cluster_with_updated_tags(cluster, tags_to_set, tag_keys_to_unset):
    cluster = dict(cluster)
    tags = dict((cluster or {}).get("tags") or {})
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)
    tags.update(tags_to_set)
    cluster["tags"] = tags
    return cluster


def check_mode_cluster(module, current):
    cluster = dict(current or {})
    desired = scrub_none_parameters(
        snake_dict_to_camel_dict(desired_cluster(module), capitalize_first=False)
    )
    cluster.update(desired)
    cluster["name"] = module.params["name"]
    if module.params["tags"] is not None:
        cluster["tags"] = module.params["tags"]
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


def create_cluster(client, module, request):
    validate_create(module, request)
    try:
        return client.create_cluster(**request, aws_retry=True).get("cluster")
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to create EKS cluster {module.params['name']}"
        )


def update_cluster_config(client, module, request):
    request = dict(request)
    request["name"] = module.params["name"]
    try:
        return client.update_cluster_config(
            **request,
            aws_retry=True,
        ).get("update", {})
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to update EKS cluster {module.params['name']}"
        )


def update_cluster_version(client, module):
    try:
        return client.update_cluster_version(
            name=module.params["name"],
            version=module.params["version"],
            aws_retry=True,
        ).get("update", {})
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to update EKS cluster {module.params['name']} version"
        )


def ensure_present(client, module):
    current = describe_cluster(client, module)
    request = create_request(module)

    if current is None:
        if module.check_mode:
            exit_result(module, True, check_mode_cluster(module, None), "present")
        cluster = create_cluster(client, module, request)
        if module.params["wait"]:
            wait_for_cluster(client, module, "cluster_active")
            cluster = describe_cluster(client, module)
        exit_result(module, True, cluster, "present")

    if module.params["wait"] and current.get("status") != "ACTIVE":
        wait_for_cluster(client, module, "cluster_active")
        current = describe_cluster(client, module)

    validate_create_only_fields(module, current)

    update_requests = update_config_requests(current, update_config_request(module))
    config_changed = bool(update_requests)
    version_changed = module.params["version"] is not None and module.params[
        "version"
    ] != current.get("version")
    tags_to_set, tag_keys_to_unset = ({}, [])
    if module.params["tags"] is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            (current or {}).get("tags") or {},
            module.params["tags"],
            purge_tags=module.params["purge_tags"],
        )
    tags_changed = bool(tags_to_set or tag_keys_to_unset)
    cluster_changed = bool(config_changed or version_changed)
    resource_changed = bool(cluster_changed or tags_changed)

    if resource_changed and module.check_mode:
        exit_result(module, True, check_mode_cluster(module, current), "present")

    if config_changed:
        for index, update_request in enumerate(update_requests):
            update = update_cluster_config(client, module, update_request)
            update_id = update.get("id")
            wait_for_next_update = index < len(update_requests) - 1
            if update_id and (
                module.params["wait"] or version_changed or wait_for_next_update
            ):
                wait_for_update(client, module, update_id)
                wait_for_cluster(client, module, "cluster_active")

    if version_changed:
        update = update_cluster_version(client, module)
        update_id = update.get("id")
        if update_id and module.params["wait"]:
            wait_for_update(client, module, update_id)
            wait_for_cluster(client, module, "cluster_active")

    if tags_changed:
        apply_tag_changes(
            client,
            module,
            current,
            tags_to_set,
            tag_keys_to_unset,
        )

    if cluster_changed:
        current = describe_cluster(client, module)
    elif tags_changed:
        current = cluster_with_updated_tags(current, tags_to_set, tag_keys_to_unset)

    exit_result(module, resource_changed, current, "present")


def ensure_absent(client, module):
    current = describe_cluster(client, module)
    if current is None:
        exit_result(module, False, {}, "absent")

    if module.check_mode:
        exit_result(module, True, current, "absent")

    try:
        client.delete_cluster(name=module.params["name"], aws_retry=True)
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to delete EKS cluster {module.params['name']}"
        )

    if module.params["wait"]:
        wait_for_cluster(client, module, "cluster_deleted")

    exit_result(module, True, current, "absent")


def main():
    raw_params = _load_params()
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
                        "key_arn": {"type": "str"},
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
                "endpoint_private_access": {"default": False, "type": "bool"},
                "endpoint_public_access": {"default": True, "type": "bool"},
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
    module._linuxhq_raw_params = raw_params
    client = module.client("eks", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
