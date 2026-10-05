#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: eks_cluster
version_added: "1.9.0"
short_description: Manage AWS Elastic Kubernetes Service clusters
description:
  - Creates, updates, and deletes AWS EKS clusters.
  - Supports modern EKS cluster settings exposed by the EKS API.
author:
  - Taylor Kimball (@tkimball83)
options:
  access_config:
    description:
      - The cluster access configuration.
      - When omitted while creating a cluster, AWS uses its default values.
      - When omitted while updating a cluster, the existing values are left unchanged.
    suboptions:
      authentication_mode:
        choices:
          - API
          - API_AND_CONFIG_MAP
          - CONFIG_MAP
        description:
          - The cluster authentication mode.
          - When omitted while creating a cluster, AWS uses C(CONFIG_MAP).
          - When omitted while updating a cluster, the existing value is left unchanged.
          - AWS only permits changes from C(CONFIG_MAP) to C(API_AND_CONFIG_MAP) to C(API).
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
      - This requires botocore C(1.35.72) or later.
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
  deletion_protection:
    description:
      - Whether deletion protection is enabled for the cluster.
      - AWS rejects deleting a cluster while deletion protection is enabled.
      - When omitted while creating a cluster, AWS uses its default value.
      - When omitted while updating a cluster, the existing value is left unchanged.
      - This requires botocore C(1.40.3) or later.
    type: bool
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
          - This can only be set when creating a cluster.
          - The module fails if this differs from the existing cluster.
          - This requires botocore C(1.23.29) or later.
        type: str
      service_ipv4_cidr:
        description:
          - The CIDR block Kubernetes assigns service IP addresses from.
          - This can only be set when creating a cluster.
          - The module fails if this differs from the existing cluster.
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
  remote_network_config:
    description:
      - The remote node and pod networks for EKS hybrid nodes.
      - The supplied configuration is sent as a whole when it differs from the cluster.
      - This requires botocore C(1.35.72) or later, and C(1.37.24) or later to update an existing cluster.
    suboptions:
      remote_node_networks:
        description:
          - The remote node networks. This must contain at most one entry.
        elements: dict
        suboptions:
          cidrs:
            description:
              - The CIDR blocks of the remote node network.
            elements: str
            required: true
            type: list
        type: list
      remote_pod_networks:
        description:
          - The remote pod networks. This must contain at most one entry.
        elements: dict
        suboptions:
          cidrs:
            description:
              - The CIDR blocks of the remote pod network.
            elements: str
            required: true
            type: list
        type: list
    type: dict
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
      - This requires botocore C(1.35.72) or later.
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
  upgrade_policy:
    description:
      - The cluster upgrade policy.
    suboptions:
      support_type:
        choices:
          - EXTENDED
          - STANDARD
        description:
          - The support type for the cluster.
          - When omitted while creating a cluster, AWS uses C(EXTENDED).
          - When omitted while updating a cluster, the existing value is left unchanged.
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
      - The delay in seconds between cluster status and update polling attempts.
      - This also applies when O(wait=false), because the module still waits for a deleting cluster
        before recreating it, for a cluster to become active before changing or deleting it, for
        in-progress updates before deleting it, and between dependent updates.
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
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts cluster configuration, version, and tag changes without modifying AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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
    - The EKS cluster. Empty when the cluster does not exist.
  returned: always
  type: dict
  contains:
    access_config:
      description: The cluster access configuration.
      returned: when the cluster exists
      type: dict
      contains:
        authentication_mode:
          description: The cluster authentication mode.
          returned: always
          type: str
          sample: API_AND_CONFIG_MAP
        bootstrap_cluster_creator_admin_permissions:
          description: Whether the cluster creator was granted admin permissions at creation.
          returned: when returned by AWS
          type: bool
    arn:
      description: The cluster ARN.
      returned: when the cluster exists
      type: str
    certificate_authority:
      description: The certificate authority data for the cluster.
      returned: when the cluster exists
      type: dict
    compute_config:
      description: The EKS Auto Mode compute configuration.
      returned: when returned by AWS
      type: dict
    created_at:
      description: The time the cluster was created.
      returned: when the cluster exists
      type: str
    deletion_protection:
      description: Whether deletion protection is enabled.
      returned: when returned by AWS
      type: bool
    encryption_config:
      description: The cluster encryption configuration.
      returned: when configured
      type: list
      elements: dict
    endpoint:
      description: The Kubernetes API server endpoint.
      returned: when the cluster is active
      type: str
    identity:
      description: The identity provider information for the cluster.
      returned: when returned by AWS
      type: dict
    kubernetes_network_config:
      description: The Kubernetes network configuration.
      returned: when the cluster exists
      type: dict
    logging:
      description: The control plane logging configuration.
      returned: when the cluster exists
      type: dict
    name:
      description: The cluster name.
      returned: when the cluster exists
      type: str
    platform_version:
      description: The EKS platform version.
      returned: when the cluster exists
      type: str
    remote_network_config:
      description: The remote node and pod networks for EKS hybrid nodes.
      returned: when configured
      type: dict
    resources_vpc_config:
      description: The cluster VPC configuration.
      returned: when the cluster exists
      type: dict
      contains:
        cluster_security_group_id:
          description: The cluster security group ID created by EKS.
          returned: when returned by AWS
          type: str
        endpoint_private_access:
          description: Whether the private API server endpoint is enabled.
          returned: always
          type: bool
        endpoint_public_access:
          description: Whether the public API server endpoint is enabled.
          returned: always
          type: bool
        public_access_cidrs:
          description: The CIDR blocks that can access the public API server endpoint.
          returned: always
          type: list
          elements: str
        security_group_ids:
          description: The additional security group IDs.
          returned: always
          type: list
          elements: str
        subnet_ids:
          description: The cluster subnet IDs.
          returned: always
          type: list
          elements: str
        vpc_id:
          description: The cluster VPC ID.
          returned: always
          type: str
    role_arn:
      description: The cluster IAM role ARN.
      returned: when the cluster exists
      type: str
    status:
      description: The cluster status.
      returned: when the cluster exists
      type: str
      sample: ACTIVE
    storage_config:
      description: The EKS Auto Mode storage configuration.
      returned: when returned by AWS
      type: dict
    tags:
      description: The cluster tags with key case preserved.
      returned: when the cluster exists
      type: dict
    upgrade_policy:
      description: The cluster upgrade policy.
      returned: when returned by AWS
      type: dict
      contains:
        support_type:
          description: The cluster support type.
          returned: always
          type: str
          sample: EXTENDED
    version:
      description: The Kubernetes version.
      returned: when the cluster exists
      type: str
      sample: "1.34"
    zonal_shift_config:
      description: The zonal shift configuration.
      returned: when returned by AWS
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
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
    "deletion_protection",
    "encryption_config",
    "kubernetes_network_config",
    "logging",
    "remote_network_config",
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
    "deletion_protection",
    "kubernetes_network_config",
    "logging",
    "remote_network_config",
    "resources_vpc_config",
    "storage_config",
    "upgrade_policy",
    "zonal_shift_config",
]

# Auto Mode capability settings and the path to each within its update parameter.
AUTO_MODE_FIELDS = {
    "computeConfig": (),
    "kubernetesNetworkConfig": ("elasticLoadBalancing",),
    "storageConfig": ("blockStorage",),
}

CREATE_ONLY_FIELDS = [
    "encryption_config",
    "role_arn",
]

KUBERNETES_NETWORK_CREATE_ONLY_FIELDS = {
    "ip_family": "ipFamily",
    "service_ipv4_cidr": "serviceIpv4Cidr",
}

RESOURCES_VPC_CONFIG_ENDPOINT_FIELDS = [
    "endpointPrivateAccess",
    "endpointPublicAccess",
    "publicAccessCidrs",
]

RESOURCES_VPC_CONFIG_NETWORK_FIELDS = [
    "securityGroupIds",
    "subnetIds",
]

CLUSTER_MAPPING_FIELDS = (
    "accessConfig",
    "computeConfig",
    "kubernetesNetworkConfig",
    "logging",
    "remoteNetworkConfig",
    "resourcesVpcConfig",
    "storageConfig",
    "upgradePolicy",
    "zonalShiftConfig",
)


def validate_cluster(module, cluster, changed=False):
    tags = cluster.get("tags") if isinstance(cluster, dict) else None
    if (
        not isinstance(cluster, dict)
        or not isinstance(cluster.get("arn"), str)
        or not cluster["arn"]
        or cluster.get("name") != module.params["name"]
        or not isinstance(cluster.get("status"), str)
        or any(field in cluster and not isinstance(cluster[field], dict) for field in CLUSTER_MAPPING_FIELDS)
        or ("encryptionConfig" in cluster and not isinstance(cluster["encryptionConfig"], list))
        or ("version" in cluster and not isinstance(cluster["version"], str))
        or (tags is not None and not isinstance(tags, dict))
        or (
            isinstance(tags, dict)
            and any(not isinstance(key, str) or not isinstance(value, str) for key, value in tags.items())
        )
    ):
        module.fail_json(changed=changed, msg="EKS returned an invalid cluster")

    return cluster


def validate_update(module, update, expected_id=None, changed=False):
    if (
        not isinstance(update, dict)
        or not isinstance(update.get("id"), str)
        or not update["id"]
        or (expected_id is not None and update["id"] != expected_id)
        or not isinstance(update.get("status"), str)
    ):
        module.fail_json(changed=changed, msg="EKS returned an invalid cluster update")

    return update


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
    return {key: comparable_subset(current.get(key), value) for key, value in desired.items()}


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


def auto_mode_request(current, config_request):
    request = {}
    for field, path in AUTO_MODE_FIELDS.items():
        current_config = current.get(field) or {}
        desired_config = config_request.get(field) or {}
        for key in path:
            current_config = current_config.get(key) or {}
            desired_config = desired_config.get(key) or {}

        config = dict(desired_config)
        if "enabled" not in config and "enabled" in current_config:
            config["enabled"] = current_config["enabled"]

        if config:
            for key in reversed(path):
                config = {key: config}

            request[field] = config

    return request


def require_nested_request_parameters(module, client, operation_name, request):
    operation_parameters = client.meta.service_model.operation_model(operation_name).input_shape.members
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

        available_elastic_parameters = available_parameters["elasticLoadBalancing"].members
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


def describe_cluster(client, module, changed=False):
    """Describe the cluster; changed reports whether it was already modified, for failure results."""
    name = module.params["name"]

    try:
        response = client.describe_cluster(
            name=name,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=f"Unable to describe AWS EKS cluster {name}")

    return validate_cluster(
        module,
        response.get("cluster") if isinstance(response, dict) else None,
        changed=changed,
    )


def wait_for_cluster(client, module, waiter_name, changed=False, accept_failed=False):
    """Wait for the cluster; accept_failed ends the wait without failing when the cluster is FAILED or gone."""
    name = module.params["name"]
    waiter = client.get_waiter(waiter_name)
    wait_delay = module.params["wait_delay"]
    attempts = 1 + int(module.params["wait_timeout"] / wait_delay)

    try:
        waiter.wait(
            name=name,
            WaiterConfig={"Delay": wait_delay, "MaxAttempts": attempts},
        )
    except (BotoCoreError, ClientError) as e:
        if accept_failed:
            cluster = describe_cluster(client, module, changed=changed)
            if cluster is None or cluster["status"] == "FAILED":
                return

        # Botocore's waiters stop on a terminal state that rules out the target state (such as FAILED or
        # DELETING while waiting for ACTIVE) as well as on timeouts, so the message names neither.
        state = waiter_name.replace("cluster_", "")
        module.fail_json_aws(e, changed=changed, msg=f"Unable to wait for AWS EKS cluster {name} to become {state}")


def describe_update(client, module, update_id, changed=False):
    name = module.params["name"]

    try:
        response = client.describe_update(
            name=name,
            updateId=update_id,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            changed=changed,
            msg=f"Unable to describe AWS EKS cluster update {update_id} for {name}",
        )

    return validate_update(
        module,
        response.get("update") if isinstance(response, dict) else None,
        expected_id=update_id,
        changed=changed,
    )


def wait_for_update(client, module, update_id, changed=False):
    name = module.params["name"]
    wait_delay = module.params["wait_delay"]
    deadline = time.monotonic() + module.params["wait_timeout"]
    last_update = {}
    require_client_methods(
        module,
        client,
        "EKS",
        {"describe_update": ("name", "updateId")},
        changed=changed,
    )
    while time.monotonic() < deadline:
        last_update = describe_update(client, module, update_id, changed=changed)
        status = last_update.get("status")

        if status == "Successful":
            return last_update

        if status in ("Cancelled", "Failed"):
            module.fail_json(
                changed=changed,
                msg=f"AWS EKS cluster update {update_id} for {name} {status.lower()}",
                update=boto3_resource_to_ansible_dict(last_update, transform_tags=False, force_tags=False),
            )

        time.sleep(min(wait_delay, max(0, deadline - time.monotonic())))

    module.fail_json(
        changed=changed,
        msg=f"Timed out waiting for AWS EKS cluster update {update_id} for {name}",
        update=boto3_resource_to_ansible_dict(last_update, transform_tags=False, force_tags=False),
    )


def wait_for_cluster_updates(client, module):
    name = module.params["name"]
    wait_delay = module.params["wait_delay"]
    deadline = time.monotonic() + module.params["wait_timeout"]
    require_client_methods(
        module,
        client,
        "EKS",
        {
            "describe_update": ("name", "updateId"),
            "list_updates": ("maxResults", "name", "nextToken"),
        },
    )
    update_ids = query_list(
        module,
        client,
        "list_updates",
        "updateIds",
        f"Unable to list AWS EKS cluster updates for {name}",
        name=name,
    )
    if not isinstance(update_ids, list) or any(not isinstance(update_id, str) for update_id in update_ids):
        module.fail_json(msg=f"EKS returned invalid cluster updates for {name}")

    # EKS can start its own update after one completes; DeleteCluster rejects an in-progress update.
    # ListUpdates returns only IDs, so each update is described once and only in-progress ones are polled.
    while update_ids:
        update_ids = [
            update_id
            for update_id in update_ids
            if describe_update(client, module, update_id)["status"] == "InProgress"
        ]
        if not update_ids:
            return

        if time.monotonic() >= deadline:
            module.fail_json(msg=f"Timed out waiting for AWS EKS cluster updates {', '.join(update_ids)} for {name}")

        time.sleep(min(wait_delay, max(0, deadline - time.monotonic())))


def desired_cluster(module):
    desired = scrub_none_parameters({field: module.params[field] for field in CREATE_FIELDS})

    if desired.get("encryption_config") == []:
        del desired["encryption_config"]

    return desired


def merge_cluster_configuration(current, desired):
    result = dict(current or {})
    for key, value in desired.items():
        if isinstance(value, dict):
            result[key] = merge_cluster_configuration(result.get(key), value)
        else:
            result[key] = value

    return result


def check_mode_cluster(module, current):
    tags = module.params.get("tags")
    cluster = dict(current or {})
    desired = snake_dict_to_camel_dict(desired_cluster(module), capitalize_first=False)
    # EKS never returns bootstrapSelfManagedAddons.
    desired.pop("bootstrapSelfManagedAddons", None)
    if current is not None and "accessConfig" in desired:
        desired["accessConfig"].pop("bootstrapClusterCreatorAdminPermissions", None)

    cluster = merge_cluster_configuration(cluster, desired)
    desired_logging = (desired.get("logging") or {}).get("clusterLogging")
    if desired_logging is not None and current is not None:
        log_types = {
            log_type: entry["enabled"]
            for entry in ((current.get("logging") or {}).get("clusterLogging") or []) + desired_logging
            for log_type in entry.get("types") or []
        }
        cluster["logging"]["clusterLogging"] = [
            {"enabled": enabled, "types": sorted(log_type for log_type, value in log_types.items() if value == enabled)}
            for enabled in (True, False)
            if enabled in log_types.values()
        ]

    cluster["name"] = module.params["name"]
    if tags is not None:
        current_tags = {} if module.params["purge_tags"] else dict(cluster.get("tags") or {})
        current_tags.update(tags)
        cluster["tags"] = current_tags

    return cluster


def exit_result(module, changed, cluster, state):
    normalized_cluster = boto3_resource_to_ansible_dict(
        cluster or {}, transform_tags=False, force_tags=False, ignore_list=["tags"]
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
        create_request = scrub_none_parameters(snake_dict_to_camel_dict(create_request, capitalize_first=False))
        if tags:
            create_request["tags"] = tags

        if create_request.get("roleArn") is None:
            module.fail_json(msg="role_arn is required to create an EKS cluster")

        if not (create_request.get("resourcesVpcConfig") or {}).get("subnetIds"):
            module.fail_json(msg="resources_vpc_config.subnet_ids is required to create an EKS cluster")

        if module.check_mode:
            exit_result(module, True, check_mode_cluster(module, None), "present")

        require_client_methods(
            module,
            client,
            "EKS",
            {"create_cluster": tuple(create_request)},
        )
        require_nested_request_parameters(module, client, "CreateCluster", create_request)
        try:
            response = client.create_cluster(**create_request, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to create EKS cluster {name}")

        cluster = validate_cluster(
            module,
            response.get("cluster") if isinstance(response, dict) else None,
            changed=True,
        )

        if wait:
            wait_for_cluster(client, module, "cluster_active", changed=True)
            cluster = describe_cluster(client, module, changed=True)
            if cluster is None:
                module.fail_json(changed=True, msg=f"EKS cluster {name} disappeared after creation")

        exit_result(module, True, cluster, "present")

    if wait and not module.check_mode and current.get("status") != "ACTIVE":
        wait_for_cluster(client, module, "cluster_active")
        current = describe_cluster(client, module)
        if current is None:
            module.fail_json(msg=f"EKS cluster {name} disappeared while waiting for it to become active")

    desired_boto3 = snake_dict_to_camel_dict(desired, capitalize_first=False)
    for field in CREATE_ONLY_FIELDS:
        camel_field = next(iter(snake_dict_to_camel_dict({field: None}, capitalize_first=False)))
        if desired_boto3.get(camel_field) is None:
            continue

        current_value = comparable_subset(current, {camel_field: desired_boto3[camel_field]})

        if changed(current_value, {camel_field: desired_boto3[camel_field]}):
            module.fail_json(msg=f"Cannot modify {field} for existing EKS cluster {name}")

    # EKS rejects these after creation; failing here keeps other updates from applying first.
    current_network_config = current.get("kubernetesNetworkConfig") or {}
    for field, camel_field in KUBERNETES_NETWORK_CREATE_ONLY_FIELDS.items():
        value = (desired.get("kubernetes_network_config") or {}).get(field)
        if value is not None and value != current_network_config.get(camel_field):
            module.fail_json(msg=f"Cannot modify kubernetes_network_config.{field} for existing EKS cluster {name}")

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
        config_request = scrub_none_parameters(snake_dict_to_camel_dict(config_request, capitalize_first=False))

    update_requests = []
    auto_mode_changed = False
    for field, value in config_request.items():
        field_request = {field: value}
        update_request = changed_request(current, field_request)

        if update_request is None:
            continue

        if field in AUTO_MODE_FIELDS:
            auto_mode_changed = True
            continue

        if field == "remoteNetworkConfig":
            update_request = field_request

        if field == "logging":
            current_log_types = enabled_log_types(current.get("logging"))
            if all(
                (log_type in current_log_types) == entry["enabled"]
                for entry in value.get("clusterLogging", [])
                for log_type in entry.get("types", [])
            ):
                continue

        if field == "resourcesVpcConfig":
            resources_vpc_config = update_request.get("resourcesVpcConfig") or {}
            endpoint_config = {}
            for endpoint_field in RESOURCES_VPC_CONFIG_ENDPOINT_FIELDS:
                if endpoint_field in resources_vpc_config:
                    endpoint_config[endpoint_field] = resources_vpc_config[endpoint_field]

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

    if auto_mode_changed:
        # EKS requires compute, load balancing, and storage enablement in one request.
        update_requests.append(auto_mode_request(current, config_request))

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
            module.fail_json(msg="The resulting cluster tags must contain at most 50 entries")

    tags_changed = bool(tags_to_set or tag_keys_to_unset)
    cluster_changed = config_changed or version_changed
    resource_changed = cluster_changed or tags_changed

    if resource_changed and not module.check_mode and current.get("status") != "ACTIVE":
        wait_for_cluster(client, module, "cluster_active")
        return ensure_present(client, module)

    if resource_changed and module.check_mode:
        exit_result(module, True, check_mode_cluster(module, current), "present")

    arn = current.get("arn")
    if tags_changed and not arn:
        module.fail_json(msg=f"Unable to tag EKS cluster {name}")

    # Check every SDK requirement first so an unsupported later call cannot fail after an earlier change.
    update_requests = [dict(update_request, name=name) for update_request in update_requests]
    for update_request in update_requests:
        require_client_methods(
            module,
            client,
            "EKS",
            {"update_cluster_config": tuple(update_request)},
        )
        require_nested_request_parameters(module, client, "UpdateClusterConfig", update_request)

    if version_changed:
        require_client_methods(
            module,
            client,
            "EKS",
            {"update_cluster_version": ("name", "version")},
        )

    if (update_requests and (wait or version_changed or len(update_requests) > 1)) or (version_changed and wait):
        # Updates are waited on between and after these calls.
        require_client_methods(
            module,
            client,
            "EKS",
            {"describe_update": ("name", "updateId")},
        )

    if tag_keys_to_unset:
        require_client_methods(
            module,
            client,
            "EKS",
            {"untag_resource": ("resourceArn", "tagKeys")},
        )

    if tags_to_set:
        require_client_methods(
            module,
            client,
            "EKS",
            {"tag_resource": ("resourceArn", "tags")},
        )

    # Failures after the first successful change report changed=True.
    mutated = False
    for index, update_request in enumerate(update_requests):
        try:
            response = client.update_cluster_config(
                **update_request,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=mutated, msg=f"Unable to update EKS cluster {name}")

        mutated = True
        update = validate_update(
            module,
            response.get("update") if isinstance(response, dict) else None,
            changed=True,
        )
        update_id = update["id"]
        wait_for_next_update = index < len(update_requests) - 1

        if wait or version_changed or wait_for_next_update:
            wait_for_update(client, module, update_id, changed=True)
            wait_for_cluster(client, module, "cluster_active", changed=True)

    if version_changed:
        try:
            response = client.update_cluster_version(
                name=name,
                version=version,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=mutated, msg=f"Unable to update EKS cluster {name} version")

        mutated = True
        update = validate_update(
            module,
            response.get("update") if isinstance(response, dict) else None,
            changed=True,
        )
        update_id = update["id"]

        if wait:
            wait_for_update(client, module, update_id, changed=True)
            wait_for_cluster(client, module, "cluster_active", changed=True)

    if tag_keys_to_unset:
        try:
            client.untag_resource(
                resourceArn=arn,
                tagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=mutated, msg=f"Unable to remove tags from EKS cluster {name}")

        mutated = True

    if tags_to_set:
        try:
            client.tag_resource(
                resourceArn=arn,
                tags=tags_to_set,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=mutated, msg=f"Unable to tag EKS cluster {name}")

    if cluster_changed:
        if wait:
            current = describe_cluster(client, module, changed=True)
            if current is None:
                module.fail_json(changed=True, msg=f"EKS cluster {name} disappeared after update")
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
        # A cluster that fails to create or update can still be deleted.
        wait_for_cluster(client, module, "cluster_active", accept_failed=True)

    wait_for_cluster_updates(client, module)

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
        wait_for_cluster(client, module, "cluster_deleted", changed=True)

    exit_result(module, True, current, "absent")


def main():
    argument_spec = {
        "access_config": {
            "options": {
                "authentication_mode": {
                    "choices": ["API", "API_AND_CONFIG_MAP", "CONFIG_MAP"],
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
        "deletion_protection": {"type": "bool"},
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
        "remote_network_config": {
            "options": {
                "remote_node_networks": {
                    "elements": "dict",
                    "options": {"cidrs": {"elements": "str", "required": True, "type": "list"}},
                    "type": "list",
                },
                "remote_pod_networks": {
                    "elements": "dict",
                    "options": {"cidrs": {"elements": "str", "required": True, "type": "list"}},
                    "type": "list",
                },
            },
            "type": "dict",
        },
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
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
        "upgrade_policy": {
            "options": {
                "support_type": {
                    "choices": ["EXTENDED", "STANDARD"],
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

    for network in ("remote_node_networks", "remote_pod_networks"):
        if state == "present" and len((module.params["remote_network_config"] or {}).get(network) or []) > 1:
            module.fail_json(msg=f"remote_network_config.{network} must contain at most one entry")

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
