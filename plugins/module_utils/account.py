# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import re
from datetime import datetime

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict


def account_parameters(module):
    account_id = module.params.get("account_id")
    if account_id is not None and not re.fullmatch(r"[0-9]{12}", account_id):
        module.fail_json(msg="account_id must contain exactly 12 digits")

    return {"AccountId": account_id} if account_id is not None else {}


def get_account(module, client, params):
    target = params.get("AccountId", "current account")
    try:
        response = client.get_account_information(**params, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get account information for {target}")

    if (
        not isinstance(response, dict)
        or not isinstance(response.get("AccountName"), str)
        or not response["AccountName"]
    ):
        module.fail_json(msg=f"Unable to get account information for {target}: AWS returned an invalid response")

    for key in ("AccountId", "AccountState"):
        if key in response and not isinstance(response[key], str):
            module.fail_json(msg=f"Unable to get account information for {target}: AWS returned an invalid {key}")

    if "AccountCreatedDate" in response and not isinstance(response["AccountCreatedDate"], datetime):
        module.fail_json(
            msg=f"Unable to get account information for {target}: AWS returned an invalid AccountCreatedDate"
        )

    result = {
        key: response[key]
        for key in ("AccountName", "AccountId", "AccountCreatedDate", "AccountState")
        if key in response
    }
    if "AccountCreatedDate" in result:
        result["AccountCreatedDate"] = result["AccountCreatedDate"].isoformat()

    return camel_dict_to_snake_dict(result)
