#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_serial_console
version_added: "1.9.0"
short_description: Manage AWS EC2 serial console access
description:
  - Enables or disables EC2 serial console access for a region.
  - Fails without changes when a declarative policy manages access that would change.
author:
  - Taylor Kimball (@tkimball83)
options:
  state:
    description:
      - Whether EC2 serial console access should be enabled.
      - Use C(present) to enable access and C(absent) to disable access.
      - Requires botocore 1.20.41 or later.
    choices:
      - absent
      - present
    default: present
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Predicts serial console access changes without modifying AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Ensure EC2 serial console access is enabled
  linuxhq.aws.ec2_serial_console:
    region: us-east-1
    state: present

- name: Ensure EC2 serial console access is disabled
  linuxhq.aws.ec2_serial_console:
    region: us-east-1
    state: absent
"""

RETURN = r"""
region:
  description: The AWS region where serial console access was managed.
  returned: always
  type: str
serial_console_access:
  description:
    - The current EC2 serial console access status for the selected region.
  returned: always
  type: dict
  contains:
    managed_by:
      description:
        - The entity that manages EC2 serial console access.
        - C(account) when the account manages access and C(declarative-policy) when a declarative policy manages access.
      returned: when returned by AWS
      type: str
      sample: account
    serial_console_access_enabled:
      description: Whether EC2 serial console access is enabled.
      returned: always
      type: bool
state:
  description: The requested state of EC2 serial console access.
  returned: always
  type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.ec2_serial_console import (
    get_serial_console_access,
    normalized_serial_console_access,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    desired_enabled = state == "present"

    current = get_serial_console_access(client, module)

    changed = current.get("serial_console_access_enabled") != desired_enabled

    if changed and current.get("managed_by") == "declarative-policy":
        module.fail_json(
            msg=(
                "EC2 serial console access in region "
                f"{module.region} is managed by a declarative policy and cannot be changed"
            ),
        )

    if changed and not module.check_mode:
        action = "enable" if desired_enabled else "disable"
        method_name = "enable_serial_console_access" if desired_enabled else "disable_serial_console_access"
        require_client_methods(module, client, "EC2", {method_name: ()})

        # Resolve the method only after require_client_methods confirms it exists.
        method = client.enable_serial_console_access if desired_enabled else client.disable_serial_console_access
        try:
            response = method(aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to {action} EC2 serial console access in region {module.region}",
            )

        current = {**current, **normalized_serial_console_access(module, response, changed=True)}

    elif changed:
        current = {**current, "serial_console_access_enabled": desired_enabled}

    module.exit_json(
        changed=changed,
        region=module.region,
        serial_console_access=current,
        state=state,
    )


if __name__ == "__main__":
    main()
