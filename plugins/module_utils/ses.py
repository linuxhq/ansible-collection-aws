# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_account(client, module, changed=False):
    """Return the SES account; changed reports whether the account was already modified, for failure results."""
    try:
        account = client.get_account(aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg="Unable to get AWS Simple Email Service account details")

    if not isinstance(account, dict):
        module.fail_json(changed=changed, msg="AWS Simple Email Service returned an invalid account response")

    account.pop("ResponseMetadata", None)
    return boto3_resource_to_ansible_dict(account, transform_tags=False, force_tags=False)
