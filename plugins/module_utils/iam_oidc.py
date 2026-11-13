# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def provider_url(url):
    """Return url as IAM stores it for a provider, in its ARN and Url: without a leading https:// of any case."""
    return url[len("https://") :] if url.lower().startswith("https://") else url


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


def list_provider_summaries(client, module):
    return validate_provider_summaries(
        module,
        query_list(
            module,
            client,
            "list_open_id_connect_providers",
            "OpenIDConnectProviderList",
            "Unable to list AWS IAM OIDC providers",
        ),
    )


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


def get_provider(client, module, arn):
    require_client_methods(
        module,
        client,
        "IAM",
        {"get_open_id_connect_provider": ("OpenIDConnectProviderArn",)},
    )
    return get_provider_by_arn(client, module, arn)


def get_provider_by_url(client, module, url):
    """Return the provider whose URL is exactly url, apart from the https:// prefix, or None.

    IAM keeps URLs that differ only in a trailing slash or host case as separate providers, and STS matches a token's
    issuer to the provider URL exactly, so only the exact URL identifies a provider.
    """
    desired_url = provider_url(url)
    for provider_summary in list_provider_summaries(client, module):
        arn = provider_summary["Arn"]
        if arn.partition(":oidc-provider/")[2] == desired_url:
            provider = get_provider(client, module, arn)
            if provider and provider_url(provider["Url"]) == desired_url:
                return provider

    return None
