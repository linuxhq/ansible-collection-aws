# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def validate_tag_list(module, tags):
    """Validate a Global Accelerator tag list, which must also have non-empty tag keys."""
    msg = "Global Accelerator returned invalid tags"
    require_valid_tag_list(module, tags, msg)
    if any(not tag["Key"] for tag in tags):
        module.fail_json(msg=msg)

    return tags


def list_accelerator_tags(client, module, accelerator_arn, missing_ok=False):
    """Return an accelerator's validated tag list, or None when missing_ok and it was deleted."""
    msg = f"Unable to list tags for AWS Global Accelerator {accelerator_arn}"
    try:
        response = client.list_tags_for_resource(
            ResourceArn=accelerator_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("AcceleratorNotFoundException") as e:
        if missing_ok:
            return None

        module.fail_json_aws(e, msg=msg)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=msg)

    return validate_tag_list(module, response.get("Tags") if isinstance(response, dict) else None)
