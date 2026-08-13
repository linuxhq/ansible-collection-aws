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
    normalized = url.rstrip("/")
    if normalized.lower().startswith("https://"):
        normalized = normalized[8:]
    host, separator, path = normalized.partition("/")

    return host.lower() + separator + path


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

    provider.pop("ResponseMetadata", None)
    provider["OpenIDConnectProviderArn"] = arn
    return provider
