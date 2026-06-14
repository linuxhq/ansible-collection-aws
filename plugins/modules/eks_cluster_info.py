#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: eks_cluster_info
short_description: Gather information about aws eks clusters
description:
  - Gathers information about AWS EKS clusters.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply to returned EKS clusters.
      - The EKS C(ListClusters) API does not support filters, so filters are
        applied client-side after clusters are described.
      - Filter keys use the returned snake_case cluster fields.
      - Dotted keys can be used for nested values such as
        C(resources_vpc_config.endpoint_private_access).
      - C(tag:Name) can be used to filter by cluster tag.
    type: dict
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
      - Mutually exclusive with O(include).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about EKS clusters
  linuxhq.aws.eks_cluster_info:

- name: Gather information about selected EKS clusters
  linuxhq.aws.eks_cluster_info:
    name: molecule-eks1

- name: Gather information about active private endpoint EKS clusters
  linuxhq.aws.eks_cluster_info:
    filters:
      status: ACTIVE
      resources_vpc_config.endpoint_private_access: true

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
"""

from fnmatch import fnmatchcase

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def value_matches(current, desired):
    if isinstance(current, (list, tuple, set)):
        return any(value_matches(item, desired) for item in current)
    if isinstance(desired, str) and isinstance(current, str):
        return fnmatchcase(current, desired)
    return current == desired


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "include": {"elements": "str", "type": "list"},
            "name": {"type": "str"},
        },
        mutually_exclusive=[["include", "name"]],
        supports_check_mode=True,
    )
    client = module.client("eks", retry_decorator=AWSRetry.jittered_backoff())

    if module.params["name"]:
        cluster_names = [module.params["name"]]
    else:
        request = {}
        if module.params["include"] is not None:
            request["include"] = module.params["include"]

        try:
            cluster_names = paginated_query_with_retries(
                client,
                "list_clusters",
                **request,
            ).get("clusters", [])
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to list AWS EKS clusters")

    clusters = []
    for name in cluster_names:
        try:
            cluster = client.describe_cluster(
                name=name,
                aws_retry=True,
            ).get("cluster")
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except Exception as e:
            module.fail_json_aws(e, msg=f"Unable to describe AWS EKS cluster {name}")

        clusters.append(cluster)

    clusters = boto3_resource_list_to_ansible_dict(
        clusters, transform_tags=False, force_tags=False
    )

    if module.params["filters"]:
        filtered_clusters = []
        for cluster in clusters:
            matches = True
            for key, expected in module.params["filters"].items():
                if isinstance(expected, (list, tuple, set)):
                    expected_values = list(expected)
                else:
                    expected_values = [expected]

                if key.startswith("tag:"):
                    current = (cluster.get("tags") or {}).get(key[4:])
                else:
                    current = cluster
                    for part in key.replace("-", "_").split("."):
                        if not isinstance(current, dict):
                            current = None
                            break

                        current = current.get(part)

                if not any(
                    value_matches(current, expected) for expected in expected_values
                ):
                    matches = False
                    break

            if matches:
                filtered_clusters.append(cluster)

        clusters = filtered_clusters

    module.exit_json(
        changed=False,
        clusters=clusters,
    )


if __name__ == "__main__":
    main()
