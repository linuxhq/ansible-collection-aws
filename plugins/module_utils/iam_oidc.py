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


def matching_providers(client, module, url):
    """Yield each existing provider whose URL normalizes to url, the one with the URL exactly as given first."""
    desired_url = normalize_provider_url(url)
    exact_url = url[len("https://") :] if url.lower().startswith("https://") else url
    candidates = [
        provider_summary["Arn"]
        for provider_summary in list_provider_summaries(client, module)
        if normalize_provider_url(provider_summary["Arn"].partition(":oidc-provider/")[2]) == desired_url
    ]
    # IAM keeps URLs that differ only in a trailing slash or host case as separate providers, and STS matches a token's
    # issuer exactly, so the provider with the URL exactly as given wins over a normalized match. The sort is stable,
    # so the listed order decides otherwise.
    candidates.sort(key=lambda arn: arn.partition(":oidc-provider/")[2] != exact_url)
    for arn in candidates:
        provider = get_provider(client, module, arn)

        if provider and normalize_provider_url(provider.get("Url")) == desired_url:
            yield provider


def get_provider_by_url(client, module, url):
    return next(matching_providers(client, module, url), None)


def get_providers_by_url(client, module, url):
    return list(matching_providers(client, module, url))
