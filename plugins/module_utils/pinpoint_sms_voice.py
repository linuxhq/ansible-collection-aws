# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import scrub_none_parameters

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def unique_resource_ids(identifiers):
    """Return identifiers without repeats of one resource given as an ID and an ARN.

    The ARN form is kept because a resource shared from another account can only be described by its ARN.
    """
    unique = {}
    for identifier in identifiers:
        resource_id = identifier.rsplit("/", 1)[-1]
        if resource_id not in unique or identifier.startswith("arn:"):
            unique[resource_id] = identifier

    return list(unique.values())


def is_phone_number_identity(origination):
    """Return whether a ListPoolOriginationIdentities item is a phone number rather than a sender ID."""
    arn = origination.get("OriginationIdentityArn")
    return isinstance(origination.get("PhoneNumber"), str) or (isinstance(arn, str) and ":phone-number/" in arn)


def identity_matches(origination, identities):
    """Return whether an origination item's ID or ARN is one of identities."""
    return any(
        origination.get(key) in identities
        for key in ("OriginationIdentity", "OriginationIdentityArn")
        if origination.get(key)
    )


def predicted_origination_identity(origination_identity, iso_country_code):
    """Project an origination identity as AWS returns it once associated with a pool."""
    identity = {
        "IsoCountryCode": iso_country_code,
        "OriginationIdentity": origination_identity,
    }
    # A phone number is returned by its ID; a sender ID ARN ends with its country, so it is kept as given.
    if origination_identity.startswith("arn:") and ":phone-number/" in origination_identity:
        identity["OriginationIdentity"] = origination_identity.rsplit("/", 1)[-1]
        identity["OriginationIdentityArn"] = origination_identity

    return scrub_none_parameters(identity)


def is_last_phone_number(originations, identities):
    """Return whether the phone number named by identities is the only phone number in a pool's originations."""
    phone_numbers = [origination for origination in originations if is_phone_number_identity(origination)]
    return len(phone_numbers) == 1 and identity_matches(phone_numbers[0], identities)


def last_phone_number_message(phone_number, pool_id):
    return (
        f"Phone number {phone_number} is the last phone number in Pinpoint SMS Voice V2 pool {pool_id}, "
        "which AWS does not allow to be disassociated; delete the pool with "
        "linuxhq.aws.pinpoint_sms_voice_phone_pool first"
    )


def is_last_phone_number_conflict(error):
    """Return whether a ConflictException ClientError has the LAST_PHONE_NUMBER reason."""
    response = getattr(error, "response", None) or {}
    # botocore adds modeled error members, such as Reason, beside Error in the parsed response.
    reason = response.get("Reason") or (response.get("Error") or {}).get("Reason")
    return reason == "LAST_PHONE_NUMBER"


def pool_is_deleting(client, module, pool_id):
    """Return whether a pool is gone or DELETING, which this collection treats as missing."""
    try:
        response = paginated_query_with_retries(client, "describe_pools", PoolIds=[pool_id])
    except is_boto3_error_code("ResourceNotFoundException"):
        return True
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe Pinpoint SMS Voice V2 pool {pool_id}")

    pools = response.get("Pools") if isinstance(response, dict) else None
    if not isinstance(pools, list) or any(not isinstance(pool, dict) for pool in pools):
        module.fail_json(msg=f"AWS returned malformed data while describing Pinpoint SMS Voice V2 pool {pool_id}")

    return not pools or pools[0].get("Status") == "DELETING"


def list_tags(client, module, arn, resource, changed=False, missing_ok=False):
    """Return a resource's tag list; resource names it in messages, such as "pool".

    changed reports whether the resource was already modified, for failure results. With missing_ok, a resource
    deleted since it was described returns None instead of failing.
    """
    msg = f"Unable to list tags for Pinpoint SMS Voice V2 {resource} {arn}"
    try:
        response = client.list_tags_for_resource(
            ResourceArn=arn,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException") as e:
        if missing_ok:
            return None

        module.fail_json_aws(e, changed=changed, msg=msg)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=msg)

    return require_valid_tag_list(
        module,
        response.get("Tags", []) if isinstance(response, dict) else None,
        f"AWS returned malformed tags for Pinpoint SMS Voice V2 {resource} {arn}",
        changed=changed,
    )
