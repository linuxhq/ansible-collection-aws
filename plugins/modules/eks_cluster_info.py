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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def list_cluster_names(client, module):
    try:
        response = paginated_query_with_retries(client, "list_clusters")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS EKS clusters",
        )
    return response.get("clusters", [])


def describe_cluster(client, module, name):
    describe_cluster = AWSRetry.jittered_backoff()(client.describe_cluster)
    try:
        response = describe_cluster(name=name)
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to describe AWS EKS cluster {name}",
        )
    return response.get("cluster")


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
        clusters = [
            cluster
            for cluster in [
                describe_cluster(client, module, name)
                for name in list_cluster_names(client, module)
            ]
            if cluster is not None
        ]

    module.exit_json(
        changed=False,
        clusters=boto3_resource_list_to_ansible_dict(clusters, force_tags=False),
    )


if __name__ == "__main__":
    main()
