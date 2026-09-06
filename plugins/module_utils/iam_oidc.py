# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)


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


def get_provider_by_arn(client, module, arn):
    try:
        provider = client.get_open_id_connect_provider(
            OpenIDConnectProviderArn=arn,
            aws_retry=True,
        )
    except is_boto3_error_code("NoSuchEntity"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS IAM OIDC provider {arn}")

    valid_provider = (
        isinstance(provider, dict)
        and isinstance(provider.get("Url"), str)
        and isinstance(provider.get("ClientIDList"), list)
        and all(isinstance(client_id, str) for client_id in provider["ClientIDList"])
        and isinstance(provider.get("ThumbprintList"), list)
        and all(isinstance(thumbprint, str) for thumbprint in provider["ThumbprintList"])
        and (
            "Tags" not in provider
            or (
                isinstance(provider["Tags"], list)
                and all(
                    isinstance(tag, dict) and isinstance(tag.get("Key"), str) and isinstance(tag.get("Value"), str)
                    for tag in provider["Tags"]
                )
            )
        )
    )
    if not valid_provider:
        module.fail_json(msg=f"Unable to get AWS IAM OIDC provider {arn}: AWS returned an invalid response")

    provider.pop("ResponseMetadata", None)
    provider["OpenIDConnectProviderArn"] = arn
    return provider
