# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


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
