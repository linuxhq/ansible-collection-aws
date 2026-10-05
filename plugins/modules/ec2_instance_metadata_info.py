#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_metadata_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 instance metadata defaults
description:
  - Gathers EC2 account-level instance metadata defaults for a region.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only retrieves information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather EC2 account-level instance metadata defaults
  linuxhq.aws.ec2_instance_metadata_info:
    region: us-east-1
"""

RETURN = r"""
account_level:
  description:
    - The current account-level EC2 instance metadata defaults for the selected region.
    - Options without an account-level default are omitted.
  returned: always
  type: dict
  contains:
    http_endpoint:
      description: Whether the instance metadata service endpoint is enabled or disabled.
      returned: when set
      type: str
    http_put_response_hop_limit:
      description: Maximum number of hops that the metadata token can travel.
      returned: when set
      type: int
    http_tokens:
      description: Whether IMDSv2 is C(optional) or C(required).
      returned: when set
      type: str
    http_tokens_enforced:
      description: Whether IMDSv2 is enforced when an instance launches.
      returned: when set
      type: str
    instance_metadata_tags:
      description: Whether access to instance tags from the instance metadata service is enabled or disabled.
      returned: when set
      type: str
    managed_by:
      description: Entity that manages the defaults, such as C(account) or C(declarative-policy).
      returned: when available
      type: str
    managed_exception_message:
      description: Customized exception message specified in the declarative policy.
      returned: when available
      type: str
region:
  description: The AWS region where the defaults were gathered.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.ec2_metadata import (
    get_instance_metadata_defaults,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "EC2",
        {"get_instance_metadata_defaults": ()},
    )

    module.exit_json(
        changed=False,
        account_level=get_instance_metadata_defaults(client, module),
        region=module.region,
    )


if __name__ == "__main__":
    main()
