#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_pool_associate
short_description: Manage aws end user messaging sms phone pool associations
description:
  - Manages AWS End User Messaging SMS phone pool origination identity
    associations.
  - This module maps to the Pinpoint SMS Voice V2
    C(AssociateOriginationIdentity) API, the API behind
    C(aws pinpoint-sms-voice-v2 associate-origination-identity).
author:
  - Taylor Kimball (@tkimball83)
options:
  client_token:
    description:
      - Unique idempotency token for association requests.
      - When omitted, AWS generates an idempotency token for the request.
    type: str
  iso_country_code:
    description:
      - The two-character ISO 3166-1 alpha-2 country or region code.
    required: true
    type: str
  origination_identity:
    description:
      - Origination identity to associate with the pool.
      - This can be a phone number ID, phone number ARN, sender ID, or sender
        ID ARN.
    required: true
    type: str
  pool_id:
    description:
      - The pool ID or ARN.
    required: true
    type: str
  state:
    choices:
      - absent
      - present
    default: present
    description:
      - Whether the origination identity should be associated with the pool.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure phone numbers are associated with a phone pool
  linuxhq.aws.pinpoint_sms_voice_phone_pool_associate:
    pool_id: pool-0123456789abcdef0123456789abcdef
    origination_identity: phone-0123456789abcdef0123456789abcdef
    iso_country_code: US

- name: Ensure a phone number is not associated with a phone pool
  linuxhq.aws.pinpoint_sms_voice_phone_pool_associate:
    pool_id: pool-0123456789abcdef0123456789abcdef
    origination_identity: phone-0123456789abcdef0123456789abcdef
    iso_country_code: US
    state: absent
"""

RETURN = r"""
association:
  description:
    - The requested origination identity association.
  returned: always
  type: dict
origination_identity:
  description:
    - The requested origination identity.
  returned: always
  type: str
pool_id:
  description:
    - The pool ID or ARN.
  returned: always
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def current_associations(client, module):
    try:
        return paginated_query_with_retries(
            client,
            "list_pool_origination_identities",
            PoolId=module.params["pool_id"],
        ).get("OriginationIdentities", [])
    except is_boto3_error_code("ResourceNotFoundException"):
        return []
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list origination identities for Pinpoint SMS Voice "
                f"V2 pool {module.params['pool_id']}"
            ),
        )


def current_association(module, associations):
    iso_country_code = module.params["iso_country_code"]

    for association in associations:
        if (
            iso_country_code is not None
            and association.get("IsoCountryCode") != iso_country_code
        ):
            continue

        for identity in (
            association.get("OriginationIdentity"),
            association.get("OriginationIdentityArn"),
        ):
            if identity is None:
                continue

            if identity == module.params["origination_identity"]:
                return association

    return None


def association_request(client, module, method_name):
    request = snake_dict_to_camel_dict(
        scrub_none_parameters(
            {
                "client_token": module.params["client_token"],
                "iso_country_code": module.params["iso_country_code"],
                "origination_identity": module.params["origination_identity"],
                "pool_id": module.params["pool_id"],
            }
        ),
        capitalize_first=True,
    )

    try:
        supported_parameters = set(
            get_boto3_client_method_parameters(client, method_name)
        )
    except Exception:
        module.fail_json(
            msg=(
                "Installed botocore does not support Pinpoint SMS Voice V2 "
                f"{method_name}"
            )
        )

    unsupported_parameters = sorted(set(request) - supported_parameters)

    if unsupported_parameters:
        module.fail_json(
            msg=(
                "Installed botocore does not support Pinpoint SMS Voice V2 "
                f"{method_name} parameter(s): "
                f"{', '.join(unsupported_parameters)}"
            )
        )
    return request


def exit_result(module, changed, association):
    module.exit_json(
        changed=changed,
        association=boto3_resource_to_ansible_dict(
            association or {}, transform_tags=False, force_tags=False
        ),
        origination_identity=module.params["origination_identity"],
        pool_id=module.params["pool_id"],
        state=module.params["state"],
    )


def ensure_present(client, module):
    current = current_associations(client, module)
    association = current_association(module, current)
    changed = association is None

    if changed and not module.check_mode:
        try:
            association = client.associate_origination_identity(
                **association_request(client, module, "associate_origination_identity"),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to associate origination identity "
                    f"{module.params['origination_identity']} with "
                    "Pinpoint SMS Voice V2 pool "
                    f"{module.params['pool_id']}"
                ),
            )

    elif changed and module.check_mode:
        association = scrub_none_parameters(
            {
                "IsoCountryCode": module.params["iso_country_code"],
                "OriginationIdentity": module.params["origination_identity"],
                "PoolId": module.params["pool_id"],
            }
        )

    exit_result(module, changed, association)


def ensure_absent(client, module):
    current = current_associations(client, module)
    association = current_association(module, current)
    changed = association is not None

    if changed and not module.check_mode:
        try:
            client.disassociate_origination_identity(
                **association_request(
                    client, module, "disassociate_origination_identity"
                ),
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            pass
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to disassociate origination identity "
                    f"{module.params['origination_identity']} from "
                    "Pinpoint SMS Voice V2 pool "
                    f"{module.params['pool_id']}"
                ),
            )

        association = None

    exit_result(module, changed, association)


def main():
    argument_spec = {
        "client_token": {"no_log": False, "type": "str"},
        "iso_country_code": {"required": True, "type": "str"},
        "origination_identity": {"required": True, "type": "str"},
        "pool_id": {"required": True, "type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client(
        "pinpoint-sms-voice-v2",
        retry_decorator=AWSRetry.jittered_backoff(),
    )

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
