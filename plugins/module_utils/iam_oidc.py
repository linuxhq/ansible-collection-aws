# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def normalize_provider_url(url):
    if url is None:
        return None

    normalized = url
    if normalized.lower().startswith("https://"):
        normalized = normalized[8:]

    normalized = normalized.rstrip("/")
    host, separator, path = normalized.partition("/")

    return host.lower() + separator + path


def validate_provider_summaries(module, providers):
    valid = isinstance(providers, list) and all(
        isinstance(provider, dict)
        and isinstance(provider.get("Arn"), str)
        and ":oidc-provider/" in provider["Arn"]
        and bool(provider["Arn"].partition(":oidc-provider/")[2])
        for provider in providers
    )
    if not valid:
        module.fail_json(msg="Unable to list AWS IAM OIDC providers: AWS returned an invalid response")

    return providers


def get_provider_by_arn(client, module, arn, changed=False):
    """Describe a provider; changed reports whether it was already modified, for failure results."""
    try:
        provider = client.get_open_id_connect_provider(
            OpenIDConnectProviderArn=arn,
            aws_retry=True,
        )
    except is_boto3_error_code("NoSuchEntity"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=f"Unable to get AWS IAM OIDC provider {arn}")

    msg = f"Unable to get AWS IAM OIDC provider {arn}: AWS returned an invalid response"
    if not isinstance(provider, dict) or not isinstance(provider.get("Url"), str):
        module.fail_json(changed=changed, msg=msg)

    # A provider can have no client IDs or thumbprints, so a missing list is empty.
    for field in ("ClientIDList", "ThumbprintList"):
        values = provider.setdefault(field, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            module.fail_json(changed=changed, msg=msg)

    if "Tags" in provider:
        require_valid_tag_list(module, provider["Tags"], msg, changed=changed)

    provider.pop("ResponseMetadata", None)
    provider["OpenIDConnectProviderArn"] = arn
    return provider
