#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: eks_cluster_info
version_added: 1.9.1
short_description: Gather information about AWS EKS clusters
description:
  - Gathers information about AWS EKS clusters.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The EKS cluster name to query.
      - When omitted, all EKS clusters are returned.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about EKS clusters
  linuxhq.aws.eks_cluster_info:

- name: Gather information about a single EKS cluster
  linuxhq.aws.eks_cluster_info:
    name: molecule-eks1
"""

RETURN = r"""
clusters:
  description:
    - The EKS clusters.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_resource,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
)


def describe_cluster(client, module, name):
    return aws_resource(
        client,
        module,
        "describe_cluster",
        "cluster",
        ignore_error_codes="ResourceNotFoundException",
        ignored_error_result=None,
        name=name,
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("eks")

    if module.params["name"] is not None:
        cluster = describe_cluster(client, module, module.params["name"])
        clusters = [] if cluster is None else [cluster]
    else:
        clusters = []
        for name in aws_paginated_list(client, module, "list_clusters", "clusters"):
            cluster = describe_cluster(client, module, name)
            if cluster is not None:
                clusters.append(cluster)

    module.exit_json(
        changed=False,
        clusters=aws_resource_list_to_snake_dicts(clusters),
    )


if __name__ == "__main__":
    main()
