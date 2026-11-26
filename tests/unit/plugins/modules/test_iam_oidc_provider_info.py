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


@pytest.mark.parametrize("found", [{"OpenIDConnectProviderArn": "arn:aws:iam::1:oidc-provider/example.com/id"}, None])
def test_url_lookup_returns_the_matched_provider_as_a_list(found):
    # get_provider_by_url matches the URL; its tests cover the matching rules.
    client = Mock()
    module = FakeModule({"arn": None, "url": "https://example.com/id"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_provider_by_url", return_value=found) as get,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    get.assert_called_once_with(client, module, "https://example.com/id")
    assert raised.value.values["open_id_connect_providers"] == (
        [{"open_id_connect_provider_arn": "arn:aws:iam::1:oidc-provider/example.com/id"}] if found else []
    )


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
