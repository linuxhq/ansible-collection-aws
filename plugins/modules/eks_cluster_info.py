#!/usr/bin/python
# Copyright: Taylor Kimball
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
    elements: str
    type: list
  names:
    description:
      - EKS cluster names used to limit the result set.
      - When omitted, all EKS clusters are returned.
    elements: str
    type: list
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
    names:
      - molecule-eks1
      - molecule-eks2

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


def filter_values(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def nested_value(resource, key):
    if key.startswith("tag:"):
        return (resource.get("tags") or {}).get(key[4:])

    value = resource
    for part in key.replace("-", "_").split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def value_matches(current, desired):
    if isinstance(current, (list, tuple, set)):
        return any(value_matches(item, desired) for item in current)
    if isinstance(desired, str) and isinstance(current, str):
        return fnmatchcase(current, desired)
    return current == desired


def filter_matches(resource, filters):
    return all(
        any(value_matches(nested_value(resource, key), desired) for desired in values)
        for key, values in (
            (key, filter_values(value)) for key, value in (filters or {}).items()
        )
    )


def describe_cluster(client, module, name):
    try:
        return client.describe_cluster(
            name=name,
            aws_retry=True,
        ).get("cluster")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to describe AWS EKS cluster {name}")


def cluster_names(client, module):
    if module.params["names"]:
        return module.params["names"]
    request = {}
    if module.params["include"] is not None:
        request["include"] = module.params["include"]
    return paginated_query_with_retries(
        client,
        "list_clusters",
        **request,
    ).get("clusters", [])


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "include": {"elements": "str", "type": "list"},
            "names": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )
    client = module.client("eks", retry_decorator=AWSRetry.jittered_backoff())

    clusters = [
        cluster
        for cluster in [
            describe_cluster(client, module, name)
            for name in cluster_names(client, module)
        ]
        if cluster is not None
    ]
    clusters = boto3_resource_list_to_ansible_dict(
        clusters, transform_tags=False, force_tags=False
    )
    if module.params["filters"]:
        clusters = [
            cluster
            for cluster in clusters
            if filter_matches(cluster, module.params["filters"])
        ]

    module.exit_json(
        changed=False,
        clusters=clusters,
    )


if __name__ == "__main__":
    main()
