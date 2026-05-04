#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)


def list_account_aliases(client, module):
    try:
        response = paginated_query_with_retries(client, "list_account_aliases")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS IAM account aliases",
        )
    return response.get("AccountAliases", [])
