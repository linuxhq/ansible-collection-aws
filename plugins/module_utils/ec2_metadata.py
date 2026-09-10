# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_instance_metadata_defaults(client, module):
    try:
        response = client.get_instance_metadata_defaults(aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 instance metadata defaults in region {module.region}",
        )

    account_level = response.get("AccountLevel") if isinstance(response, dict) else None
    if not isinstance(account_level, dict):
        module.fail_json(msg=f"EC2 returned invalid instance metadata defaults in region {module.region}")

    return boto3_resource_to_ansible_dict(
        account_level,
        transform_tags=False,
        force_tags=False,
    )
