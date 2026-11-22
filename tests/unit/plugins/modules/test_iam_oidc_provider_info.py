from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import iam_oidc
from ansible_collections.linuxhq.aws.plugins.modules import iam_oidc_provider_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["arn", "url"]]


def test_empty_listing_does_not_require_provider_get():
    client = Mock()
    module = FakeModule({"arn": None, "url": None}, client=client)
    require_client_methods = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "list_provider_summaries", return_value=[]),
        patch.object(plugin, "require_client_methods", require_client_methods),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require_client_methods.assert_called_once_with(
        module,
        client,
        "IAM",
        {"list_open_id_connect_providers": ()},
    )


def test_listing_requires_provider_get_once_before_describing():
    client = Mock()
    client.get_open_id_connect_provider.side_effect = lambda OpenIDConnectProviderArn, aws_retry: {
        "Url": OpenIDConnectProviderArn.partition(":oidc-provider/")[2]
    }
    module = FakeModule({"arn": None, "url": None}, client=client)
    require_client_methods = Mock()
    summaries = [{"Arn": f"arn:aws:iam::1:oidc-provider/example{index}.com"} for index in range(3)]
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "list_provider_summaries", return_value=summaries),
        patch.object(plugin, "require_client_methods", require_client_methods),
        patch.object(iam_oidc, "require_client_methods") as per_call,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [call.args[3] for call in require_client_methods.call_args_list] == [
        {"list_open_id_connect_providers": ()},
        {"get_open_id_connect_provider": ("OpenIDConnectProviderArn",)},
    ]
    per_call.assert_not_called()
    assert len(raised.value.values["open_id_connect_providers"]) == 3


def test_url_filter_ignores_the_scheme_case_and_other_arns():
    module = FakeModule({"arn": None, "url": "HTTPS://example.com/id"}, client=Mock())
    provider = {
        "OpenIDConnectProviderArn": "arn:aws:iam::1:oidc-provider/example.com/id",
        "Url": "example.com/id",
    }
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(iam_oidc, "require_client_methods"),
        patch.object(
            iam_oidc,
            "query_list",
            return_value=[
                {"Arn": "arn:aws:iam::1:oidc-provider/other.example.com"},
                {"Arn": "arn:aws:iam::1:oidc-provider/example.com/id"},
            ],
        ),
        patch.object(iam_oidc, "get_provider_by_arn", return_value=provider) as get,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["open_id_connect_providers"][0]["url"] == "example.com/id"
    get.assert_called_once()


@pytest.mark.parametrize("url", ["https://example.com/id", "https://example.com/id/", "https://Example.com/id"])
def test_url_filter_returns_nothing_for_a_near_match(url):
    # Live: IAM keeps URLs that differ only in a trailing slash or host case as separate providers.
    near_matches = {"https://example.com/id": "example.com/id/", "https://example.com/id/": "example.com/id"}
    stored = near_matches.get(url, "example.com/id")
    module = FakeModule({"arn": None, "url": url}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(iam_oidc, "require_client_methods"),
        patch.object(iam_oidc, "query_list", return_value=[{"Arn": f"arn:aws:iam::1:oidc-provider/{stored}"}]),
        patch.object(iam_oidc, "get_provider_by_arn") as get,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["open_id_connect_providers"] == []
    get.assert_not_called()


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://sts.windows.net/t/", "arn:aws:iam::1:oidc-provider/sts.windows.net/t/"),
        ("https://sts.windows.net/t", "arn:aws:iam::1:oidc-provider/sts.windows.net/t"),
    ],
)
def test_url_filter_returns_the_provider_with_the_exact_url(url, expected):
    module = FakeModule({"arn": None, "url": url}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(iam_oidc, "require_client_methods"),
        patch.object(
            iam_oidc,
            "query_list",
            return_value=[
                {"Arn": "arn:aws:iam::1:oidc-provider/sts.windows.net/t"},
                {"Arn": "arn:aws:iam::1:oidc-provider/sts.windows.net/t/"},
            ],
        ),
        patch.object(
            iam_oidc,
            "get_provider_by_arn",
            side_effect=lambda client, module, arn: {
                "OpenIDConnectProviderArn": arn,
                "Url": arn.partition(":oidc-provider/")[2],
            },
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    providers = raised.value.values["open_id_connect_providers"]
    assert [provider["open_id_connect_provider_arn"] for provider in providers] == [expected]


def test_missing_provider_arn_returns_an_empty_list():
    client = Mock()
    client.get_open_id_connect_provider.side_effect = ClientError(
        {"Error": {"Code": "NoSuchEntity", "Message": "missing"}}, "GetOpenIDConnectProvider"
    )
    module = FakeModule({"arn": "arn:missing", "url": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(iam_oidc, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["open_id_connect_providers"] == []
