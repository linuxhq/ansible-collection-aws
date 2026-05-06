#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota_info
version_added: 1.9.1
short_description: Gather information about an AWS service quota
description:
  - Gathers information about an AWS service quota.
author:
  - Taylor Kimball (@tkimball83)
options:
  quota_code:
    description:
      - The quota code to gather.
    required: true
    type: str
  service_code:
    description:
      - The service code that owns the quota.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about an EC2 service quota
  linuxhq.aws.service_quota_info:
    service_code: ec2
    quota_code: L-0263D0A3

- name: Gather information about an IAM service quota in a specific region
  linuxhq.aws.service_quota_info:
    service_code: iam
    quota_code: L-0DA4ABF3
    region: us-east-1
"""

RETURN = r"""
quota:
  description:
    - The AWS service quota details.
  returned: always
  type: dict
quota_code:
  description: The gathered quota code.
  returned: always
  type: str
service_code:
  description: The gathered service code.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.service_quota import (
    get_service_quota,
)


def main():
    argument_spec = {
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("service-quotas")

    module.exit_json(
        changed=False,
        quota=aws_resource_to_snake_dict(get_service_quota(client, module)),
        quota_code=module.params["quota_code"],
        service_code=module.params["service_code"],
    )


if __name__ == "__main__":
    main()
