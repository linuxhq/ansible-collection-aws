# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def normalized_serial_console_access(module, response):
    if not isinstance(response, dict) or not isinstance(response.get("SerialConsoleAccessEnabled"), bool):
        module.fail_json(msg="EC2 returned an invalid serial console access status")

    return boto3_resource_to_ansible_dict(
        {key: value for key, value in response.items() if key != "ResponseMetadata"},
        transform_tags=False,
        force_tags=False,
    )
