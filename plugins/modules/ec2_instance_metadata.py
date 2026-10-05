#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_metadata
version_added: "1.9.0"
short_description: Manage AWS EC2 instance metadata defaults
description:
  - Updates EC2 account-level instance metadata defaults for a region.
  - At least one metadata default option must be provided.
  - Fails without changes when a declarative policy manages the defaults that would change.
author:
  - Taylor Kimball (@tkimball83)
options:
  http_endpoint:
    description:
      - Whether the instance metadata service endpoint is enabled by default.
      - C(no-preference) clears the account-level default.
      - Requires botocore 1.34.70 or later.
      - At least one of O(http_endpoint), O(http_put_response_hop_limit),
        O(http_tokens), O(http_tokens_enforced), or O(instance_metadata_tags) is required.
    choices:
      - disabled
      - enabled
      - no-preference
    type: str
  http_put_response_hop_limit:
    description:
      - The default desired HTTP PUT response hop limit.
      - This must be between C(1) and C(64), or C(-1) to clear the
        account-level default.
      - Requires botocore 1.34.70 or later.
      - At least one of O(http_endpoint), O(http_put_response_hop_limit),
        O(http_tokens), O(http_tokens_enforced), or O(instance_metadata_tags) is required.
    type: int
  http_tokens:
    description:
      - Whether IMDSv2 tokens are required by default.
      - C(no-preference) clears the account-level default.
      - Requires botocore 1.34.70 or later.
      - At least one of O(http_endpoint), O(http_put_response_hop_limit),
        O(http_tokens), O(http_tokens_enforced), or O(instance_metadata_tags) is required.
    choices:
      - optional
      - required
      - no-preference
    type: str
  http_tokens_enforced:
    description:
      - Whether launching an instance requires IMDSv2, so instances fail to launch unless
        tokens are required.
      - C(no-preference) clears the account-level default.
      - Requires botocore 1.42.56 or later.
      - At least one of O(http_endpoint), O(http_put_response_hop_limit),
        O(http_tokens), O(http_tokens_enforced), or O(instance_metadata_tags) is required.
    choices:
      - disabled
      - enabled
      - no-preference
    type: str
    version_added: "2.6.0"
  instance_metadata_tags:
    description:
      - Whether access to instance tags from the instance metadata service is enabled by default.
      - C(no-preference) clears the account-level default.
      - Requires botocore 1.34.70 or later.
      - At least one of O(http_endpoint), O(http_put_response_hop_limit),
        O(http_tokens), O(http_tokens_enforced), or O(instance_metadata_tags) is required.
    choices:
      - disabled
      - enabled
      - no-preference
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Predicts changes to account-level instance metadata defaults without modifying AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Ensure account-level EC2 instance metadata defaults are managed
  linuxhq.aws.ec2_instance_metadata:
    region: us-east-1
    http_endpoint: enabled
    http_put_response_hop_limit: 2
    http_tokens: required
    http_tokens_enforced: enabled
    instance_metadata_tags: disabled
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
  description: The AWS region where the defaults were managed.
  returned: always
  type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.ec2_metadata import (
    get_instance_metadata_defaults,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)

NO_PREFERENCE_BY_OPTION = {
    "http_endpoint": "no-preference",
    "http_put_response_hop_limit": -1,
    "http_tokens": "no-preference",
    "http_tokens_enforced": "no-preference",
    "instance_metadata_tags": "no-preference",
}


def main():
    argument_spec = {
        "http_endpoint": {
            "choices": ["disabled", "enabled", "no-preference"],
            "type": "str",
        },
        "http_put_response_hop_limit": {"type": "int"},
        "http_tokens": {
            "choices": ["optional", "required", "no-preference"],
            "type": "str",
        },
        "http_tokens_enforced": {
            "choices": ["disabled", "enabled", "no-preference"],
            "type": "str",
        },
        "instance_metadata_tags": {
            "choices": ["disabled", "enabled", "no-preference"],
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_one_of=[
            [
                "http_endpoint",
                "http_put_response_hop_limit",
                "http_tokens",
                "http_tokens_enforced",
                "instance_metadata_tags",
            ]
        ],
        supports_check_mode=True,
    )

    hop_limit = module.params["http_put_response_hop_limit"]

    if hop_limit is not None and hop_limit != -1 and not 1 <= hop_limit <= 64:
        module.fail_json(
            msg="http_put_response_hop_limit must be between 1 and 64, or -1 to clear the account-level default"
        )

    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    desired = {}
    comparable_desired = {}
    for option_name, no_preference_value in NO_PREFERENCE_BY_OPTION.items():
        option_value = module.params[option_name]

        if option_value is None:
            continue

        desired[option_name] = option_value
        if option_value == no_preference_value:
            comparable_desired[option_name] = None
        else:
            comparable_desired[option_name] = option_value

    desired_update = snake_dict_to_camel_dict(desired, capitalize_first=True)

    require_client_methods(
        module,
        client,
        "EC2",
        {"get_instance_metadata_defaults": ()},
    )

    current_account_level = get_instance_metadata_defaults(client, module)

    current = {}
    for option_name in desired:
        current[option_name] = current_account_level.get(option_name)

    changed = current != comparable_desired

    if changed and current_account_level.get("managed_by") == "declarative-policy":
        module.fail_json(
            msg=(
                "EC2 instance metadata defaults in region "
                f"{module.region} are managed by a declarative policy and cannot be changed"
            ),
            managed_exception_message=current_account_level.get("managed_exception_message"),
        )

    if changed:
        if not module.check_mode:
            require_client_methods(
                module,
                client,
                "EC2",
                {"modify_instance_metadata_defaults": tuple(desired_update)},
            )
            try:
                response = client.modify_instance_metadata_defaults(**desired_update, aws_retry=True)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to modify EC2 instance metadata defaults in region {module.region}",
                )

            if not isinstance(response, dict) or response.get("Return") is not True:
                module.fail_json(
                    changed=True,
                    msg=f"EC2 did not confirm the instance metadata defaults change in region {module.region}",
                )

        current_account_level = dict(current_account_level)
        for option_name, option_value in comparable_desired.items():
            if option_value is None:
                current_account_level.pop(option_name, None)
            else:
                current_account_level[option_name] = option_value

    result = {
        "changed": changed,
        "account_level": current_account_level,
        "region": module.region,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
