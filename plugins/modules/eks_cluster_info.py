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

- name: Gather information about a selected EKS cluster
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
      returned: unless the cluster is an EKS Connector cluster
      type: dict
      contains:
        authentication_mode:
          description: The cluster authentication mode.
          returned: unless the cluster is an EKS Connector cluster
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
      returned: unless the cluster is an EKS Connector cluster
      type: dict
      contains:
        active:
          description: The certificate authority that currently signs certificates for the cluster.
          returned: when returned by AWS
          type: dict
          contains:
            activated_by:
              description: The entity that activated the current signing certificate authority, either C(CUSTOMER) or C(EKS).
              returned: when returned by AWS
              type: str
            id:
              description: The ID of the certificate authority that currently signs certificates for the cluster.
              returned: when returned by AWS
              type: str
        data:
          description: The Base64-encoded certificate data required to communicate with the cluster.
          returned: when returned by AWS
          type: str
    client_request_token:
      description: The unique, case-sensitive identifier provided to ensure request idempotency.
      returned: when returned by AWS
      type: str
    compute_config:
      description: The EKS Auto Mode compute configuration.
      returned: when returned by AWS
      type: dict
      contains:
        enabled:
          description: Whether the EKS Auto Mode compute capability is enabled.
          returned: when returned by AWS
          type: bool
        node_pools:
          description: The EKS Auto Mode node pools.
          returned: when returned by AWS
          type: list
          elements: str
        node_role_arn:
          description: The ARN of the IAM role that EKS assigns to EKS Auto Mode EC2 managed instances.
          returned: when returned by AWS
          type: str
    connector_config:
      description: The EKS Connector configuration of a registered cluster.
      returned: when the cluster is an EKS Connector cluster
      type: dict
      contains:
        activation_expiry:
          description: The expiration time of the connected cluster's activation.
          returned: when returned by AWS
          type: str
        activation_id:
          description: The unique ID of the connected cluster's activation.
          returned: when returned by AWS
          type: str
        provider:
          description: The cluster's cloud service provider.
          returned: when returned by AWS
          type: str
        role_arn:
          description: The ARN of the EKS Connector agent role, which the connected cluster uses to communicate with AWS services.
          returned: when returned by AWS
          type: str
    control_plane_scaling_config:
      description: The control plane scaling tier configuration.
      returned: when returned by AWS
      type: dict
      contains:
        tier:
          description: The control plane scaling tier.
          returned: when returned by AWS
          type: str
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
      contains:
        provider:
          description: The KMS key used for envelope encryption of Kubernetes API data.
          returned: when returned by AWS
          type: dict
          contains:
            key_arn:
              description: The ARN or alias of the KMS key.
              returned: when returned by AWS
              type: str
        resources:
          description:
            - The resources stored for the encryption configuration, C(secrets).
            - For a cluster running Kubernetes 1.28 or later, this no longer affects which resources are encrypted.
          returned: when returned by AWS
          type: list
          elements: str
    endpoint:
      description: The Kubernetes API server endpoint.
      returned: when the cluster is active, unless the cluster is an EKS Connector cluster
      type: str
    health:
      description: The health of the cluster.
      returned: when returned by AWS
      type: dict
      contains:
        issues:
          description: The health issues of the cluster.
          returned: when returned by AWS
          type: list
          elements: dict
          contains:
            code:
              description: The error code of the issue.
              returned: when returned by AWS
              type: str
            message:
              description: A description of the issue.
              returned: when returned by AWS
              type: str
            resource_ids:
              description: The resource IDs that the issue relates to.
              returned: when returned by AWS
              type: list
              elements: str
    id:
      description: The ID of a local cluster on AWS Outposts.
      returned: when returned by AWS
      type: str
    identity:
      description: The identity provider information for the cluster.
      returned: when returned by AWS
      type: dict
      contains:
        oidc:
          description: The OpenID Connect identity provider information.
          returned: when returned by AWS
          type: dict
          contains:
            issuer:
              description: The issuer URL for the OIDC identity provider.
              returned: when returned by AWS
              type: str
    kube_api_server_config:
      description: The Kubernetes API server configuration.
      returned: when returned by AWS
      type: dict
      contains:
        event_ttl:
          description: The duration that Kubernetes events are retained.
          returned: when returned by AWS
          type: str
        service_node_port_range:
          description: The port range for NodePort services.
          returned: when returned by AWS
          type: dict
          contains:
            max_port:
              description: The maximum port number in the range.
              returned: when returned by AWS
              type: int
            min_port:
              description: The minimum port number in the range.
              returned: when returned by AWS
              type: int
    kube_controller_manager_config:
      description: The Kubernetes controller manager configuration.
      returned: when returned by AWS
      type: dict
      contains:
        horizontal_pod_autoscaler_controller_config:
          description: The horizontal pod autoscaler controller configuration.
          returned: when returned by AWS
          type: dict
          contains:
            horizontal_pod_autoscaler_sync_period:
              description: The interval between each sync of the horizontal pod autoscaler.
              returned: when returned by AWS
              type: str
        pod_gc_controller_config:
          description: The pod garbage collection controller configuration.
          returned: when returned by AWS
          type: dict
          contains:
            terminated_pod_gc_threshold:
              description: The number of terminated pods that can exist before the garbage collector starts deleting them.
              returned: when returned by AWS
              type: int
    kube_scheduler_config:
      description: The Kubernetes scheduler configuration.
      returned: when returned by AWS
      type: dict
      contains:
        node_resources_fit:
          description: The node resource fit scoring configuration for the scheduler.
          returned: when returned by AWS
          type: dict
          contains:
            scoring_strategy:
              description: The scoring strategy used to rank nodes during scheduling.
              returned: when returned by AWS
              type: dict
              contains:
                resources:
                  description: The resource weights used for scoring nodes.
                  returned: when returned by AWS
                  type: list
                  elements: dict
                  contains:
                    name:
                      description: The name of the resource (for example, C(cpu) or C(memory)).
                      returned: when returned by AWS
                      type: str
                    weight:
                      description: The weight assigned to the resource for scoring.
                      returned: when returned by AWS
                      type: int
                type:
                  description: The scoring strategy type.
                  returned: when returned by AWS
                  type: str
    kubernetes_network_config:
      description: The Kubernetes network configuration.
      returned: unless the cluster is an EKS Connector cluster
      type: dict
      contains:
        elastic_load_balancing:
          description: The EKS Auto Mode load balancing capability configuration.
          returned: when returned by AWS
          type: dict
          contains:
            enabled:
              description: Whether the EKS Auto Mode load balancing capability is enabled.
              returned: when returned by AWS
              type: bool
            gateway_api:
              description: The Kubernetes Gateway API configuration of the load balancing capability.
              returned: when returned by AWS
              type: dict
              contains:
                crds:
                  description: The Gateway API custom resource definition (CRD) management configuration.
                  returned: when returned by AWS
                  type: dict
                  contains:
                    managed:
                      description: Whether Gateway API CRD management is enabled.
                      returned: when returned by AWS
                      type: bool
        ip_family:
          description: The IP family used to assign Kubernetes C(Pod) and C(Service) objects IP addresses.
          returned: when returned by AWS
          type: str
        service_ipv4_cidr:
          description: The CIDR block Kubernetes assigns service IP addresses from.
          returned: when returned by AWS
          type: str
        service_ipv6_cidr:
          description: The CIDR block Kubernetes assigns service IP addresses from when the cluster uses the C(ipv6) IP family.
          returned: when returned by AWS
          type: str
    logging:
      description: The control plane logging configuration.
      returned: unless the cluster is an EKS Connector cluster
      type: dict
      contains:
        cluster_logging:
          description: The cluster control plane logging configuration.
          returned: when returned by AWS
          type: list
          elements: dict
          contains:
            enabled:
              description: Whether the log types export their control plane logs to CloudWatch Logs.
              returned: when returned by AWS
              type: bool
            types:
              description: The available cluster control plane log types.
              returned: when returned by AWS
              type: list
              elements: str
    name:
      description: The cluster name.
      returned: always
      type: str
    outpost_config:
      description: The configuration of a local cluster on AWS Outposts.
      returned: when returned by AWS
      type: dict
      contains:
        control_plane_instance_type:
          description: The EC2 instance type of the Kubernetes control plane instances of a local cluster on AWS Outposts.
          returned: when returned by AWS
          type: str
        control_plane_placement:
          description: The placement configuration of the control plane instances of a local cluster on AWS Outposts.
          returned: when returned by AWS
          type: dict
          contains:
            group_name:
              description: The name of the placement group for the Kubernetes control plane instances.
              returned: when returned by AWS
              type: str
            spread_level:
              description: The spread level used with the placement group for the control plane instances.
              returned: when returned by AWS
              type: str
        etcd_instance_type:
          description: The EC2 instance type of the etcd instances of a local cluster on AWS Outposts.
          returned: when returned by AWS
          type: str
        etcd_placement:
          description: The placement configuration of the etcd instances of a local cluster on AWS Outposts.
          returned: when returned by AWS
          type: dict
          contains:
            spread_level:
              description: The spread level used with the placement group for the etcd instances.
              returned: when returned by AWS
              type: str
        outpost_arns:
          description: The ARNs of the Outposts used by the local cluster.
          returned: when returned by AWS
          type: list
          elements: str
    platform_version:
      description: The EKS platform version.
      returned: unless the cluster is an EKS Connector cluster
      type: str
    remote_network_config:
      description: The remote node and pod networks for EKS hybrid nodes.
      returned: when configured
      type: dict
      contains:
        remote_node_networks:
          description: The list of network CIDRs that can contain hybrid nodes.
          returned: when returned by AWS
          type: list
          elements: dict
          contains:
            cidrs:
              description: A network CIDR that can contain hybrid nodes.
              returned: when returned by AWS
              type: list
              elements: str
        remote_pod_networks:
          description: The list of network CIDRs that can contain pods that run Kubernetes webhooks on hybrid nodes.
          returned: when returned by AWS
          type: list
          elements: dict
          contains:
            cidrs:
              description: A network CIDR that can contain pods that run Kubernetes webhooks on hybrid nodes.
              returned: when returned by AWS
              type: list
              elements: str
    resources_vpc_config:
      description: The cluster VPC configuration.
      returned: unless the cluster is an EKS Connector cluster
      type: dict
      contains:
        cluster_security_group_id:
          description: The cluster security group ID created by EKS.
          returned: when returned by AWS
          type: str
        control_plane_egress_mode:
          description: The control plane egress routing mode.
          returned: when returned by AWS
          type: str
          sample: AWS_MANAGED
        endpoint_private_access:
          description: Whether the private API server endpoint is enabled.
          returned: unless the cluster is an EKS Connector cluster
          type: bool
        endpoint_public_access:
          description: Whether the public API server endpoint is enabled.
          returned: unless the cluster is an EKS Connector cluster
          type: bool
        public_access_cidrs:
          description: The CIDR blocks that can access the public API server endpoint.
          returned: unless the cluster is an EKS Connector cluster
          type: list
          elements: str
        security_group_ids:
          description: The additional security group IDs.
          returned: unless the cluster is an EKS Connector cluster
          type: list
          elements: str
        subnet_ids:
          description: The cluster subnet IDs.
          returned: unless the cluster is an EKS Connector cluster
          type: list
          elements: str
        vpc_id:
          description: The cluster VPC ID.
          returned: unless the cluster is an EKS Connector cluster
          type: str
    role_arn:
      description: The cluster IAM role ARN.
      returned: unless the cluster is an EKS Connector cluster
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
      contains:
        block_storage:
          description: The EKS Auto Mode block storage capability configuration.
          returned: when returned by AWS
          type: dict
          contains:
            enabled:
              description: Whether the EKS Auto Mode block storage capability is enabled.
              returned: when returned by AWS
              type: bool
    tags:
      description: The cluster tags with key case preserved.
      returned: when returned by AWS
      type: dict
    upgrade_policy:
      description: The cluster upgrade policy.
      returned: when returned by AWS
      type: dict
      contains:
        support_type:
          description: The cluster support type.
          returned: unless the cluster is an EKS Connector cluster
          type: str
          sample: EXTENDED
    version:
      description: The Kubernetes version.
      returned: unless the cluster is an EKS Connector cluster
      type: str
      sample: "1.34"
    zonal_shift_config:
      description: The zonal shift configuration.
      returned: when returned by AWS
      type: dict
      contains:
        enabled:
          description: Whether the zonal shift is enabled.
          returned: when returned by AWS
          type: bool
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

from ansible_collections.linuxhq.aws.plugins.module_utils.eks import has_valid_cluster_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_cluster(module, cluster, expected_name):
    if not isinstance(cluster, dict) or cluster.get("name") != expected_name or not has_valid_cluster_tags(cluster):
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

    clusters = boto3_resource_list_to_ansible_dict(
        clusters, transform_tags=False, force_tags=False, ignore_list=["tags"]
    )

    module.exit_json(
        changed=False,
        clusters=clusters,
    )


if __name__ == "__main__":
    main()
