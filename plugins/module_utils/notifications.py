# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code


def contact_tags(module, response, contact_arn):
    """Return the validated tag dictionary from a NotificationsContacts ListTagsForResource response."""
    tags = response.get("tags", {}) if isinstance(response, dict) else None
    if not isinstance(tags, dict) or any(
        not isinstance(tag_key, str) or not isinstance(tag_value, str) for tag_key, tag_value in tags.items()
    ):
        module.fail_json(
            msg=f"Unable to list tags for AWS Notifications contact {contact_arn}: AWS returned an invalid response"
        )

    return tags


def list_contact_tags(client, module, contact_arn, missing_ok=False):
    """Return a contact's validated tag dictionary, or None when missing_ok and it was deleted."""
    msg = f"Unable to list tags for AWS Notifications contact {contact_arn}"
    try:
        response = client.list_tags_for_resource(arn=contact_arn, aws_retry=True)
    except is_boto3_error_code("ResourceNotFoundException") as e:
        if missing_ok:
            return None

        module.fail_json_aws(e, msg=msg)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=msg)

    return contact_tags(module, response, contact_arn)
