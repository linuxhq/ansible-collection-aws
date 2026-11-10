#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_sender_id_info
version_added: '2.6.0'
short_description: Gather information about AWS End User Messaging SMS sender IDs
description:
  - Gathers information about AWS End User Messaging SMS sender IDs.
  - This module maps to the Pinpoint SMS Voice V2 C(DescribeSenderIds) API,
    the API behind C(aws pinpoint-sms-voice-v2 describe-sender-ids).
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing sender IDs.
      - Filter names and values are passed to the Pinpoint SMS Voice V2
        C(DescribeSenderIds) API.
      - This must contain at most 20 filters.
      - Boolean and numeric values, including list entries, are converted to strings.
    type: dict
  max_results:
    description:
      - The maximum number of results returned by each API call.
      - This must be between 1 and 100.
      - The module follows pagination and returns all matching sender IDs.
    type: int
  owner:
    choices:
      - SELF
      - SHARED
    description:
      - The sender ID owner to query.
      - When omitted, the request does not filter by owner.
      - Requires botocore 1.35.26 or later.
      - Mutually exclusive with O(sender_ids).
    type: str
  sender_ids:
    description:
      - Sender IDs used to limit the result set.
      - Sender IDs that do not exist are omitted from the results.
      - A sender ID found by more than one entry, such as by its ID and by its ARN, is returned once.
      - This must contain at most 5 entries.
      - Mutually exclusive with O(owner).
    elements: dict
    type: list
    suboptions:
      iso_country_code:
        description:
          - The two-character ISO 3166-1 alpha-2 country or region code of the sender ID.
          - This must not be empty.
        required: true
        type: str
      sender_id:
        description:
          - The sender ID or sender ID ARN.
          - An ARN is required for a sender ID shared from another account.
          - This must not be empty.
        required: true
        type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  diff_mode:
    description: Diff mode is not supported.
    support: none
  check_mode:
    description: This module does not modify AWS resources.
    support: full
"""

EXAMPLES = r"""
- name: Gather information about End User Messaging SMS sender IDs
  linuxhq.aws.pinpoint_sms_voice_sender_id_info:

- name: Gather information about selected sender IDs
  linuxhq.aws.pinpoint_sms_voice_sender_id_info:
    sender_ids:
      - sender_id: EXAMPLE
        iso_country_code: DE

- name: Gather information about transactional sender IDs in Germany
  linuxhq.aws.pinpoint_sms_voice_sender_id_info:
    filters:
      iso-country-code: DE
      message-type: TRANSACTIONAL
"""

RETURN = r"""
sender_ids:
  description:
    - A list of End User Messaging SMS sender IDs.
  returned: always
  type: list
  elements: dict
  contains:
    deletion_protection_enabled:
      description: Whether deletion protection is enabled.
      returned: when returned by AWS
      type: bool
    iso_country_code:
      description: The two-character ISO country code.
      returned: always
      type: str
    message_types:
      description:
        - The types of messages the sender ID sends, as AWS returns them.
        - C(DescribeSenderIds) returns them in title case, such as C(Transactional).
      returned: when returned by AWS
      type: list
      elements: str
    messaging_limits:
      description:
        - The messaging limits that apply to the sender ID.
        - Map keys are converted to snake_case like other keys, so C(SMS) is
          returned as C(sms) and C(T-MOBILE) as C(t-mobile).
      returned: when returned by AWS
      type: dict
      contains:
        daily_message_caps:
          description: The advisory maximum number of messages that can be sent per day, keyed by carrier.
          returned: when a daily message cap applies
          type: dict
        rate_limits:
          description: The maximum send rate in messages per second, keyed by capability.
          returned: when returned by AWS
          type: dict
    monthly_leasing_price:
      description: The monthly price, in US dollars, to lease the sender ID.
      returned: when returned by AWS
      type: str
    pricing_tier:
      description: The pricing model of the sender ID.
      returned: when returned by AWS
      type: str
    registered:
      description: Whether the sender ID is registered.
      returned: when returned by AWS
      type: bool
    registration_id:
      description: The registration associated with the sender ID.
      returned: when associated with a registration
      type: str
    sender_id:
      description: The sender ID.
      returned: always
      type: str
    sender_id_arn:
      description: The sender ID ARN.
      returned: when returned by AWS
      type: str
    tags:
      description: The sender ID tags with key case preserved.
      returned: always
      type: dict
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    ansible_dict_to_string_filter_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.pinpoint_sms_voice import list_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.validation import require_non_blank


def unique_sender_ids(sender_ids):
    """Return SenderIdAndCountry entries without exact repeats.

    A plain ID and an ARN are both kept: sender IDs with one name and country can exist in several accounts, and
    only an ARN names one shared from another account. describe_sender_ids_by_id drops a resource found twice.
    """
    unique = {}
    for entry in sender_ids:
        unique[(entry["sender_id"], entry["iso_country_code"])] = {
            "IsoCountryCode": entry["iso_country_code"],
            "SenderId": entry["sender_id"],
        }

    return list(unique.values())


def describe_sender_ids_by_id(module, client, request):
    sender_ids = []
    for sender_id in request["SenderIds"]:
        try:
            response = paginated_query_with_retries(
                client,
                "describe_sender_ids",
                **dict(request, SenderIds=[sender_id]),
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    f"Unable to describe Pinpoint SMS Voice V2 sender ID {sender_id['SenderId']} "
                    f"in {sender_id['IsoCountryCode']}"
                ),
            )

        found = response.get("SenderIds", []) if isinstance(response, dict) else None
        if not isinstance(found, list):
            module.fail_json(msg="AWS returned malformed Pinpoint SMS Voice V2 sender ID data")

        sender_ids.extend(found)

    # A sender ID requested both by its ID and by its ARN is returned once, keyed by the ARN AWS reports.
    unique = {}
    for index, sender_id in enumerate(sender_ids):
        arn = sender_id.get("SenderIdArn") if isinstance(sender_id, dict) else None
        unique.setdefault(arn if isinstance(arn, str) else index, sender_id)

    return list(unique.values())


def validate_sender_id(module, sender_id):
    if (
        not isinstance(sender_id, dict)
        or not isinstance(sender_id.get("SenderId"), str)
        or not isinstance(sender_id.get("IsoCountryCode"), str)
        or ("SenderIdArn" in sender_id and not isinstance(sender_id["SenderIdArn"], str))
    ):
        module.fail_json(msg="AWS returned malformed Pinpoint SMS Voice V2 sender ID data")


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "max_results": {"type": "int"},
        "owner": {"choices": ["SELF", "SHARED"], "type": "str"},
        "sender_ids": {
            "elements": "dict",
            "options": {
                "iso_country_code": {"required": True, "type": "str"},
                "sender_id": {"required": True, "type": "str"},
            },
            "type": "list",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["owner", "sender_ids"]],
        supports_check_mode=True,
    )
    filters = module.params["filters"]
    max_results = module.params["max_results"]
    owner = module.params["owner"]

    if max_results is not None and not 1 <= max_results <= 100:
        module.fail_json(msg="max_results must be between 1 and 100")

    if len(filters or {}) > 20:
        module.fail_json(msg="filters must contain at most 20 entries")

    for entry in module.params["sender_ids"] or []:
        # required counts only supplied keys, so an explicit null passes it.
        for option in ("iso_country_code", "sender_id"):
            require_non_blank(module, entry[option] or "", f"sender_ids {option}")

    sender_ids = unique_sender_ids(module.params["sender_ids"] or [])
    if len(sender_ids) > 5:
        module.fail_json(msg="sender_ids must contain at most 5 entries")

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())

    request = {}
    if max_results is not None:
        request["MaxResults"] = max_results

    if sender_ids:
        request["SenderIds"] = sender_ids

    if owner:
        request["Owner"] = owner

    if filters:
        request["Filters"] = ansible_dict_to_string_filter_list(filters)

    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {
            "describe_sender_ids": tuple(dict.fromkeys((*request, "MaxResults", "NextToken"))),
        },
    )

    if sender_ids:
        found_sender_ids = describe_sender_ids_by_id(module, client, request)
    else:
        found_sender_ids = query_list(
            module,
            client,
            "describe_sender_ids",
            "SenderIds",
            "Unable to describe Pinpoint SMS Voice V2 sender IDs",
            **request,
        )

    for sender_id in found_sender_ids:
        validate_sender_id(module, sender_id)

    if any(sender_id.get("SenderIdArn") for sender_id in found_sender_ids):
        require_client_methods(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {"list_tags_for_resource": ("ResourceArn",)},
        )

    normalized_sender_ids = []
    for sender_id in found_sender_ids:
        arn = sender_id.get("SenderIdArn")
        tags = []

        if arn:
            tags = list_tags(client, module, arn, "sender ID", missing_ok=True)
            if tags is None:
                continue

        normalized_sender_ids.append(
            boto3_resource_to_ansible_dict(
                dict(sender_id, Tags=tags),
                transform_tags=True,
                force_tags=False,
            )
        )

    module.exit_json(changed=False, sender_ids=normalized_sender_ids)


if __name__ == "__main__":
    main()
