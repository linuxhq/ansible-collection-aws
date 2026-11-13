# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import iam_oidc
from ansible_collections.linuxhq.aws.plugins.module_utils.iam_oidc import (
    get_provider,
    get_provider_by_arn,
    get_provider_by_url,
    list_provider_summaries,
    provider_url,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


def test_provider_url_removes_only_the_https_prefix():
    for value, expected in (
        ("https://example.com/id/", "example.com/id/"),
        ("HTTPS://Example.COM/CaseSensitivePath/", "Example.COM/CaseSensitivePath/"),
        ("example.com/id", "example.com/id"),
        ("https://", ""),
    ):
        assert provider_url(value) == expected


def test_provider_includes_arn_without_response_metadata():
    client = Mock(
        get_open_id_connect_provider=Mock(
            return_value={"ClientIDList": [], "ThumbprintList": [], "Url": "example.com/id", "ResponseMetadata": {}}
        )
    )
    assert get_provider_by_arn(client, Mock(), "arn:provider") == {
        "OpenIDConnectProviderArn": "arn:provider",
        "ClientIDList": [],
        "ThumbprintList": [],
        "Url": "example.com/id",
    }
    client.get_open_id_connect_provider.assert_called_once_with(OpenIDConnectProviderArn="arn:provider", aws_retry=True)


def test_provider_rejects_invalid_response():
    client = Mock(get_open_id_connect_provider=Mock(return_value={}))
    module = Mock()
    module.fail_json.side_effect = SystemExit
    with pytest.raises(SystemExit):
        get_provider_by_arn(client, module, "arn:provider")

    module.fail_json.assert_called_once_with(
        changed=False, msg="Unable to get AWS IAM OIDC provider arn:provider: AWS returned an invalid response"
    )


def test_provider_treats_missing_lists_as_empty():
    client = Mock(get_open_id_connect_provider=Mock(return_value={"Url": "example.com/id"}))
    assert get_provider_by_arn(client, Mock(), "arn:provider") == {
        "OpenIDConnectProviderArn": "arn:provider",
        "ClientIDList": [],
        "ThumbprintList": [],
        "Url": "example.com/id",
    }


@pytest.mark.parametrize(
    "fields",
    [
        {"ClientIDList": None},
        {"ThumbprintList": "abc"},
        {"ClientIDList": [1]},
        {"ThumbprintList": [None]},
        {"Tags": None},
        {"Tags": [{"Key": "Name"}]},
    ],
)
@pytest.mark.parametrize("changed", [False, True])
def test_provider_rejects_present_invalid_fields(fields, changed):
    client = Mock(get_open_id_connect_provider=Mock(return_value=dict({"Url": "example.com/id"}, **fields)))
    module = Mock()
    module.fail_json.side_effect = SystemExit
    with pytest.raises(SystemExit):
        get_provider_by_arn(client, module, "arn:provider", changed=changed)

    module.fail_json.assert_called_once_with(
        changed=changed, msg="Unable to get AWS IAM OIDC provider arn:provider: AWS returned an invalid response"
    )


def test_provider_lookup_lists_providers_and_reads_the_exact_match():
    client = Mock()
    module = SimpleNamespace(params={})
    provider = {
        "OpenIDConnectProviderArn": "arn:aws:iam::1:oidc-provider/example.com/id",
        "Url": "example.com/id",
    }
    providers = [
        {"Arn": "arn:aws:iam::1:oidc-provider/other.example.com"},
        {"Arn": "arn:aws:iam::1:oidc-provider/example.com/id"},
    ]
    with (
        patch.object(iam_oidc, "query_list", return_value=providers) as query_list,
        patch.object(iam_oidc, "get_provider_by_arn", return_value=provider) as get,
        patch.object(iam_oidc, "require_client_methods"),
    ):
        result = get_provider_by_url(client, module, "HTTPS://example.com/id")

    assert result == provider
    get.assert_called_once_with(client, module, "arn:aws:iam::1:oidc-provider/example.com/id")
    query_list.assert_called_once_with(
        module,
        client,
        "list_open_id_connect_providers",
        "OpenIDConnectProviderList",
        "Unable to list AWS IAM OIDC providers",
    )


def provider_from_arn(client, module, arn):
    """Return a provider as IAM reports it: the URL is the ARN's resource part."""
    return {"OpenIDConnectProviderArn": arn, "Url": arn.partition(":oidc-provider/")[2]}


# Live: IAM keeps these as separate providers, and STS matches a token's issuer exactly.
NEAR_MATCHES = ["sts.windows.net/t", "sts.windows.net/t/", "STS.windows.net/t"]


@pytest.mark.parametrize("reverse", [False, True], ids=["listed", "reversed"])
@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://sts.windows.net/t", "sts.windows.net/t"),
        ("https://sts.windows.net/t/", "sts.windows.net/t/"),
        ("HTTPS://STS.windows.net/t", "STS.windows.net/t"),
        ("sts.windows.net/t/", "sts.windows.net/t/"),
    ],
)
def test_provider_lookup_matches_only_the_exact_url(reverse, url, expected):
    providers = [{"Arn": f"arn:aws:iam::1:oidc-provider/{stored}"} for stored in NEAR_MATCHES]
    if reverse:
        providers.reverse()

    client = Mock()
    module = SimpleNamespace(params={})
    with (
        patch.object(iam_oidc, "query_list", return_value=providers),
        patch.object(iam_oidc, "get_provider_by_arn", side_effect=provider_from_arn) as get,
        patch.object(iam_oidc, "require_client_methods"),
    ):
        result = get_provider_by_url(client, module, url)

    assert result["OpenIDConnectProviderArn"] == f"arn:aws:iam::1:oidc-provider/{expected}"
    get.assert_called_once_with(client, module, f"arn:aws:iam::1:oidc-provider/{expected}")


@pytest.mark.parametrize(
    "url", ["https://sts.windows.net/t/", "https://STS.windows.net/t", "https://sts.windows.net/T"]
)
def test_provider_lookup_ignores_providers_differing_in_slash_or_case(url):
    providers = [
        {"Arn": "arn:aws:iam::1:oidc-provider/other.example.com"},
        {"Arn": "arn:aws:iam::1:oidc-provider/sts.windows.net/t"},
    ]
    with (
        patch.object(iam_oidc, "query_list", return_value=providers),
        patch.object(iam_oidc, "get_provider_by_arn", side_effect=provider_from_arn) as get,
        patch.object(iam_oidc, "require_client_methods"),
    ):
        result = get_provider_by_url(Mock(), SimpleNamespace(params={}), url)

    assert result is None
    get.assert_not_called()


def test_provider_lookup_finds_nothing_when_the_exact_provider_disappears():
    # The exact provider is deleted between the listing and the read; a near match is not used instead.
    providers = [
        {"Arn": "arn:aws:iam::1:oidc-provider/sts.windows.net/t"},
        {"Arn": "arn:aws:iam::1:oidc-provider/sts.windows.net/t/"},
    ]
    with (
        patch.object(iam_oidc, "query_list", return_value=providers),
        patch.object(iam_oidc, "get_provider_by_arn", return_value=None) as get,
        patch.object(iam_oidc, "require_client_methods"),
    ):
        result = get_provider_by_url(Mock(), SimpleNamespace(params={}), "https://sts.windows.net/t/")

    assert result is None
    assert [call.args[2] for call in get.call_args_list] == ["arn:aws:iam::1:oidc-provider/sts.windows.net/t/"]


def test_provider_lookup_rejects_invalid_summaries():
    module = FakeModule({})
    with (
        patch.object(iam_oidc, "query_list", return_value=[{}]),
        pytest.raises(ModuleFail) as raised,
    ):
        get_provider_by_url(Mock(), module, "https://example.com/id")

    assert raised.value.values["msg"] == "Unable to list AWS IAM OIDC providers: AWS returned an invalid response"


def test_list_provider_summaries_returns_validated_summaries():
    client = Mock()
    module = FakeModule({})
    providers = [{"Arn": "arn:aws:iam::1:oidc-provider/example.com"}]
    with patch.object(iam_oidc, "query_list", return_value=providers) as query_list:
        assert list_provider_summaries(client, module) == providers

    query_list.assert_called_once_with(
        module,
        client,
        "list_open_id_connect_providers",
        "OpenIDConnectProviderList",
        "Unable to list AWS IAM OIDC providers",
    )


def test_get_provider_requires_get_method_before_describing():
    client = Mock()
    module = FakeModule({})
    calls = Mock()
    calls.get_provider_by_arn.return_value = {"Url": "example.com"}
    with (
        patch.object(iam_oidc, "require_client_methods", calls.require_client_methods),
        patch.object(iam_oidc, "get_provider_by_arn", calls.get_provider_by_arn),
    ):
        assert get_provider(client, module, "arn:provider") == {"Url": "example.com"}

    assert [call[0] for call in calls.mock_calls] == ["require_client_methods", "get_provider_by_arn"]
    calls.require_client_methods.assert_called_once_with(
        module,
        client,
        "IAM",
        {"get_open_id_connect_provider": ("OpenIDConnectProviderArn",)},
    )
    calls.get_provider_by_arn.assert_called_once_with(client, module, "arn:provider")
