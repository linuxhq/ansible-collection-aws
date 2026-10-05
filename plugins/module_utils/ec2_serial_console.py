# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def normalized_serial_console_access(module, response, changed=False):
    """Normalize the access status; changed reports whether it was already modified, for failure results."""
    if not isinstance(response, dict) or not isinstance(response.get("SerialConsoleAccessEnabled"), bool):
        module.fail_json(changed=changed, msg="EC2 returned an invalid serial console access status")

    return boto3_resource_to_ansible_dict(
        {key: value for key, value in response.items() if key != "ResponseMetadata"},
        transform_tags=False,
        force_tags=False,
    )


def get_serial_console_access(client, module):
    require_client_methods(
        module,
        client,
        "EC2",
        {"get_serial_console_access_status": ()},
    )

    try:
        response = client.get_serial_console_access_status(aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 serial console access in region {module.region}",
        )

    return normalized_serial_console_access(module, response)
