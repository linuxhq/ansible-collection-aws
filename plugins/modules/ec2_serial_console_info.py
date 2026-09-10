#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_serial_console_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 serial console access
description:
  - Gathers EC2 serial console access status for a region.
author:
  - Taylor Kimball (@tkimball83)
requirements:
  - botocore >= 1.20.41
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
  contains:
    serial_console_access_enabled:
      description: Whether EC2 serial console access is enabled.
      returned: always
      type: bool
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.ec2_serial_console import (
    normalized_serial_console_access,
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
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 serial console access in region {module.region}",
        )

    module.exit_json(
        changed=False,
        region=module.region,
        serial_console_access=normalized_serial_console_access(module, serial_console_access),
    )


if __name__ == "__main__":
    main()
