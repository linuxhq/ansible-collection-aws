# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def account_parameters(module):
    account_id = module.params.get("account_id")
    return {"AccountId": account_id} if account_id is not None else {}


def get_account(module, client, params):
    target = params.get("AccountId", "current account")
    try:
        response = client.get_account_information(**params, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get account information for {target}")

    result = {
        key: response[key]
        for key in ("AccountName", "AccountId", "AccountCreatedDate", "AccountState")
        if key in response
    }

    return boto3_resource_to_ansible_dict(result, transform_tags=False, force_tags=False)
