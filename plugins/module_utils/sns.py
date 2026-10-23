# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass


def get_sms_attributes(client, module, changed=False, **request):
    """Return the SMS attributes; changed reports whether they were already modified, for failure results."""
    try:
        response = client.get_sms_attributes(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg="Unable to get AWS Simple Notification Service SMS attributes")

    attributes = response.get("attributes", {}) if isinstance(response, dict) else None
    if not isinstance(attributes, dict):
        module.fail_json(
            changed=changed,
            msg="Unexpected response while getting AWS Simple Notification Service SMS attributes",
        )

    return attributes
