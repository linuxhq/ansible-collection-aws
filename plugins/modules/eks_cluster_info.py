#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: eks_cluster_info
version_added: "1.9.0"
short_description: Gather information about AWS Elastic Kubernetes Service clusters
description:
  - Gathers information about AWS EKS clusters.
author:
  - Taylor Kimball (@tkimball83)
options:
  include:
    description:
      - Additional EKS cluster types to include when listing clusters.
      - Values are passed to the EKS C(ListClusters) API.
      - Mutually exclusive with O(name).
    elements: str
    type: list
  name:
    description:
      - EKS cluster name used to limit the result set.
      - When omitted, all EKS clusters are returned.
      - A cluster that does not exist results in an empty list.
      - Mutually exclusive with O(include).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Queries AWS without modifying resources.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about EKS clusters
  linuxhq.aws.eks_cluster_info:

- name: Gather information about selected EKS clusters
  linuxhq.aws.eks_cluster_info:
    name: molecule-eks1

- name: Gather information about all EKS clusters including external clusters
  linuxhq.aws.eks_cluster_info:
    include:
      - all
"""

RETURN = r"""
clusters:
  description:
    - The EKS clusters.
  returned: always
  type: list
  elements: dict
  contains:
    access_config:
      description: The cluster access configuration.
      returned: always
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
      returned: always
      type: str
    certificate_authority:
      description: The certificate authority data for the cluster.
      returned: always
      type: dict
    compute_config:
      description: The EKS Auto Mode compute configuration.
      returned: when returned by AWS
      type: dict
    created_at:
      description: The time the cluster was created.
      returned: always
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
      returned: always
      type: dict
    logging:
      description: The control plane logging configuration.
      returned: always
      type: dict
    name:
      description: The cluster name.
      returned: always
      type: str
    platform_version:
      description: The EKS platform version.
      returned: always
      type: str
    remote_network_config:
      description: The remote node and pod networks for EKS hybrid nodes.
      returned: when configured
      type: dict
    resources_vpc_config:
      description: The cluster VPC configuration.
      returned: always
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
      returned: always
      type: str
    status:
      description: The cluster status.
      returned: always
      type: str
      sample: ACTIVE
    storage_config:
      description: The EKS Auto Mode storage configuration.
      returned: when returned by AWS
      type: dict
    tags:
      description: The cluster tags with key case preserved.
      returned: always
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
      returned: always
      type: str
      sample: "1.34"
    zonal_shift_config:
      description: The zonal shift configuration.
      returned: when returned by AWS
      type: dict
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


def validate_cluster(module, cluster, expected_name):
    tags = cluster.get("tags") if isinstance(cluster, dict) else None
    if (
        not isinstance(cluster, dict)
        or cluster.get("name") != expected_name
        or (tags is not None and not isinstance(tags, dict))
        or (
            isinstance(tags, dict)
            and any(not isinstance(key, str) or not isinstance(value, str) for key, value in tags.items())
        )
    ):
        module.fail_json(msg=f"EKS returned an invalid cluster for {expected_name}")

    return cluster


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "include": {"elements": "str", "type": "list"},
            "name": {"type": "str"},
        },
        mutually_exclusive=[["include", "name"]],
        supports_check_mode=True,
    )
    client = module.client("eks", retry_decorator=AWSRetry.jittered_backoff())

    include = list(dict.fromkeys(module.params["include"] or []))
    name = module.params["name"]

    if name:
        cluster_names = [name]
    else:
        require_client_methods(
            module,
            client,
            "EKS",
            {"list_clusters": ((("include",) if include else ()) + ("maxResults", "nextToken"))},
        )
        request = {}
        if include:
            request["include"] = include

        cluster_names = query_list(
            module,
            client,
            "list_clusters",
            "clusters",
            "Unable to list AWS EKS clusters",
            **request,
        )

    if not isinstance(cluster_names, list) or any(
        not isinstance(cluster_name, str) or not cluster_name for cluster_name in cluster_names
    ):
        module.fail_json(msg="EKS returned an invalid cluster list")

    if cluster_names:
        require_client_methods(
            module,
            client,
            "EKS",
            {"describe_cluster": ("name",)},
        )

    clusters = []
    for cluster_name in cluster_names:
        try:
            response = client.describe_cluster(
                name=cluster_name,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to describe AWS EKS cluster {cluster_name}")

        clusters.append(
            validate_cluster(
                module,
                response.get("cluster") if isinstance(response, dict) else None,
                cluster_name,
            )
        )

    cluster_tags = [cluster.get("tags") for cluster in clusters]
    clusters = boto3_resource_list_to_ansible_dict(clusters, transform_tags=False, force_tags=False)
    for cluster, tags in zip(clusters, cluster_tags):
        if tags is not None:
            cluster["tags"] = tags

    module.exit_json(
        changed=False,
        clusters=clusters,
    )


if __name__ == "__main__":
    main()
