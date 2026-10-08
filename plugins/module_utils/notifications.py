# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


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
