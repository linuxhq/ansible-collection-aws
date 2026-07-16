#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_serial_console_info
short_description: Gather information about aws ec2 serial console access
description:
  - Gathers EC2 serial console access status for a region.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather EC2 serial console access status
  linuxhq.aws.ec2_serial_console_info:
    region: us-east-1
"""

RETURN = r"""
region:
  description: The AWS region where serial console access was gathered.
  returned: always
  type: str
serial_console_access:
  description:
    - The current EC2 serial console access status for the selected region.
  returned: always
  type: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
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
        {"get_serial_console_access_status": ()},
    )

    try:
        serial_console_access = client.get_serial_console_access_status(aws_retry=True)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 serial console access in region {module.region}",
        )

    serial_console_access.pop("ResponseMetadata", None)

    module.exit_json(
        changed=False,
        region=module.region,
        serial_console_access=boto3_resource_to_ansible_dict(
            serial_console_access,
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
