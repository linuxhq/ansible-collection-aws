# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods


def list_accelerator_tags(client, module, accelerator_arn, missing_ok=False):
    """Return an accelerator's tag list, or None when missing_ok and it was deleted."""
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

    return response.get("Tags", [])


def get_accelerator_by_arn(client, module, accelerator_arn, changed=False):
    """Describe an accelerator; changed reports whether it was already modified, for failure results."""
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"describe_accelerator": ("AcceleratorArn",)},
        changed=changed,
    )
    try:
        response = client.describe_accelerator(
            AcceleratorArn=accelerator_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("AcceleratorNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=f"Unable to describe AWS Global Accelerator {accelerator_arn}")

    accelerator = response["Accelerator"]
    if accelerator["AcceleratorArn"] != accelerator_arn:
        module.fail_json(changed=changed, msg="Global Accelerator returned an invalid accelerator")

    return accelerator
