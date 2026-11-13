# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import re

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


def is_phone_number_reference(origination_identity):
    """Return whether a requested origination identity is a phone number ARN or an ID of the form AWS assigns them.

    A sender ID has at most 11 characters, so it never matches the 38-character phone number ID form.
    """
    if origination_identity.startswith("arn:"):
        return ":phone-number/" in origination_identity

    return re.fullmatch(r"phone-[0-9a-f]{32}", origination_identity) is not None


def identity_matches(origination, identities):
    """Return whether an origination item's ID or ARN is one of identities.

    Phone number IDs and ARNs match exactly. Live: AWS treats sender IDs without letter case; it describes a sender ID
    requested as AuP2Mix in uppercase, puts AUP2MIX in its ARN, and lists the ID in a pool in the case it was associated
    with. So a sender ID and its ARN match without letter case, as pinpoint_sms_voice_sender_id compares them.
    """
    if is_phone_number_identity(origination):
        return any(
            origination.get(key) in identities
            for key in ("OriginationIdentity", "OriginationIdentityArn")
            if origination.get(key)
        )

    wanted = {identity.upper() for identity in identities if isinstance(identity, str)}
    return any(
        origination[key].upper() in wanted
        for key in ("OriginationIdentity", "OriginationIdentityArn")
        if isinstance(origination.get(key), str)
    )


def predicted_origination_identity(origination_identity, iso_country_code):
    """Project an origination identity as AWS returns it once associated with a pool."""
    identity = {
        "IsoCountryCode": iso_country_code,
        "OriginationIdentity": origination_identity,
    }
    # Live: AWS returns a phone number or sender ID by its ID, with the ARN beside it.
    sender_id_arn = re.fullmatch(r"arn:.*:sender-id/([^/]+)/([^/]+)", origination_identity)
    if origination_identity.startswith("arn:") and ":phone-number/" in origination_identity:
        identity["OriginationIdentity"] = origination_identity.rsplit("/", 1)[-1]
        identity["OriginationIdentityArn"] = origination_identity
    elif sender_id_arn:
        identity["IsoCountryCode"] = iso_country_code or sender_id_arn.group(2)
        identity["OriginationIdentity"] = sender_id_arn.group(1)
        identity["OriginationIdentityArn"] = origination_identity

    return scrub_none_parameters(identity)


def is_last_phone_number(originations, identities):
    """Return whether identities name a pool's only origination identity, which AWS refuses to disassociate.

    Live: AWS answers LAST_PHONE_NUMBER for a sole phone number or sender ID alike, and accepts removing a phone
    number while a sender ID remains in the pool.
    """
    return len(originations) == 1 and identity_matches(originations[0], identities)


def last_phone_number_message(identity, pool_id, phone_number=True):
    """Return the failure message for a pool's last identity; phone_number is False when it may be a sender ID."""
    subject = (
        f"Phone number {identity} is the last phone number"
        if phone_number
        else f"Origination identity {identity} is the last origination identity"
    )
    return (
        f"{subject} in Pinpoint SMS Voice V2 pool {pool_id}, "
        "which AWS does not allow to be disassociated; delete the pool with "
        "linuxhq.aws.pinpoint_sms_voice_phone_pool first"
    )


def is_last_phone_number_conflict(error):
    """Return whether a ConflictException ClientError has the LAST_PHONE_NUMBER reason."""
    # botocore adds modeled error members, such as Reason, beside Error in the parsed response.
    return error.response.get("Reason") == "LAST_PHONE_NUMBER"


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
