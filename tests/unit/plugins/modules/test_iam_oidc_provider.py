from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import iam_oidc_provider as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


@pytest.mark.parametrize("error_code", ["ConcurrentModification", "AccessDenied"])
def test_configured_retry_handles_concurrent_modification_only(error_code):
    module = FakeModule({"state": "absent", "url": "https://issuer.example", "tags": None}, client=Mock())
    original = plugin.AWSRetry.jittered_backoff
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_absent"),
        patch.object(plugin.AWSRetry, "jittered_backoff", wraps=original) as configured,
    ):
        plugin.main()

    decorator = original(retries=2, delay=0, **configured.call_args.kwargs)
    error = ClientError(
        {"Error": {"Code": error_code, "Message": "conflict or denied"}},
        "AddClientIDToOpenIDConnectProvider",
    )
    operation = Mock(side_effect=[error, {"ok": True}])
    if error_code == "ConcurrentModification":
        assert decorator(operation)() == {"ok": True}
        assert operation.call_count == 2
    else:
        with pytest.raises(ClientError) as raised:
            decorator(operation)()

        assert raised.value is error
        assert operation.call_count == 1


def test_absent_tolerates_provider_disappearing_during_delete():
    client = Mock()
    client.delete_open_id_connect_provider.side_effect = plugin.ClientError(
        {"Error": {"Code": "NoSuchEntity", "Message": "gone"}},
        "DeleteOpenIDConnectProvider",
    )
    module = FakeModule({"url": "https://example.com/id"})
    current = {"OpenIDConnectProviderArn": "arn:provider"}
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]


def test_module_contract():
    options = assert_module_contract(plugin)
    assert "required_if" not in options
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]


def test_main_only_requires_provider_listing_before_reconciliation():
    module = Mock(
        params={
            "client_id_list": ["client"],
            "state": "present",
            "tags": None,
            "thumbprint_list": ["a" * 40],
            "url": "https://example.com/id",
        },
        client=Mock(return_value=Mock()),
    )
    require_client_methods = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "ensure_present"),
        patch.object(plugin, "require_client_methods", require_client_methods),
    ):
        plugin.main()

    require_client_methods.assert_called_once_with(
        module,
        module.client.return_value,
        "IAM",
        {"list_open_id_connect_providers": ()},
    )


def test_provider_lookup_normalizes_url():
    client = Mock()
    module = SimpleNamespace(params={"url": "https://EXAMPLE.com/id"})
    provider = {
        "OpenIDConnectProviderArn": "arn:aws:iam::1:oidc-provider/example.com/id",
        "Url": "example.com/id",
    }
    providers = [{"Arn": "arn:aws:iam::1:oidc-provider/example.com/id"}]
    with (
        patch.object(plugin, "query_list", return_value=providers) as query_list,
        patch.object(plugin, "get_provider_by_arn", return_value=provider),
        patch.object(plugin, "require_client_methods"),
    ):
        result = plugin.get_provider_by_url(client, module)

    assert result == provider
    query_list.assert_called_once_with(
        module,
        client,
        "list_open_id_connect_providers",
        "OpenIDConnectProviderList",
        "Unable to list AWS IAM OIDC providers",
    )


def test_provider_lookup_rejects_invalid_summaries():
    module = FakeModule({"url": "https://example.com/id"})
    with (
        patch.object(plugin, "query_list", return_value=[{}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_provider_by_url(Mock(), module)

    assert raised.value.values["msg"] == "Unable to list AWS IAM OIDC providers: AWS returned an invalid response"


def test_non_hexadecimal_thumbprint_is_rejected():
    assert_module_rejects(
        plugin,
        {
            "client_id_list": ["client"],
            "state": "present",
            "tags": None,
            "thumbprint_list": ["z" * 40],
            "url": "https://example.com/id",
        },
        ("thumbprint_list entries must be exactly 40 hexadecimal " f"characters: {'z' * 40}"),
    )


def test_present_rejects_non_https_url():
    assert_module_rejects(
        plugin,
        {
            "client_id_list": [],
            "state": "present",
            "tags": None,
            "thumbprint_list": [],
            "url": "http://example.com/id",
        },
        "url must begin with https://",
    )


def test_present_rejects_url_without_host():
    for url in ("https://", "https:///path"):
        assert_module_rejects(
            plugin,
            {
                "client_id_list": ["client"],
                "state": "present",
                "tags": None,
                "thumbprint_list": ["a" * 40],
                "url": url,
            },
            "url must identify an OIDC provider host",
        )


def test_provider_list_limits_are_rejected():
    cases = [
        (
            {
                "client_id_list": [str(index) for index in range(101)],
                "state": "present",
                "tags": None,
                "thumbprint_list": ["a" * 40],
                "url": "https://example.com/id",
            },
            "client_id_list must contain at most 100 unique entries",
        ),
        (
            {
                "client_id_list": ["client"],
                "state": "present",
                "tags": None,
                "thumbprint_list": [f"{index:040x}" for index in range(6)],
                "url": "https://example.com/id",
            },
            "thumbprint_list must contain at most 5 unique entries",
        ),
    ]
    for params, message in cases:
        assert_module_rejects(plugin, params, message)


def test_empty_thumbprint_list_is_rejected_before_aws_calls():
    assert_module_rejects(
        plugin,
        {
            "client_id_list": ["client"],
            "state": "present",
            "tags": None,
            "thumbprint_list": [],
            "url": "https://example.com/id",
        },
        "thumbprint_list must not be empty; omit it to let IAM retrieve the thumbprint on create "
        "and to leave the existing thumbprints unchanged on update",
    )


def test_thumbprint_case_does_not_trigger_an_update():
    client = Mock()
    module = FakeModule(
        {
            "client_id_list": [],
            "purge_tags": True,
            "tags": None,
            "thumbprint_list": ["A" * 40],
            "url": "https://example.com/id",
        }
    )
    current = {
        "ClientIDList": [],
        "OpenIDConnectProviderArn": "arn:provider",
        "ThumbprintList": ["a" * 40],
        "Url": "example.com/id",
    }
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    client.update_open_id_connect_provider_thumbprint.assert_not_called()


def test_existing_provider_reconciles_client_ids_and_thumbprints():
    client = Mock()
    module = FakeModule(
        {
            "client_id_list": ["keep", "new"],
            "purge_tags": True,
            "tags": None,
            "thumbprint_list": ["new-thumbprint"],
            "url": "https://example.com/id",
        }
    )
    current = {
        "ClientIDList": ["keep", "old"],
        "OpenIDConnectProviderArn": "arn:provider",
        "ThumbprintList": ["old-thumbprint"],
        "Url": "example.com/id",
    }
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        patch.object(plugin, "get_provider_by_arn") as get_provider_by_arn,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert raised.value.values["open_id_connect_provider"]["client_id_list"] == ["keep", "new"]
    assert raised.value.values["open_id_connect_provider"]["thumbprint_list"] == ["new-thumbprint"]
    get_provider_by_arn.assert_not_called()
    client.remove_client_id_from_open_id_connect_provider.assert_called_once_with(
        OpenIDConnectProviderArn="arn:provider",
        ClientID="old",
        aws_retry=True,
    )
    client.add_client_id_to_open_id_connect_provider.assert_called_once_with(
        OpenIDConnectProviderArn="arn:provider",
        ClientID="new",
        aws_retry=True,
    )
    assert client.method_calls.index(
        call.add_client_id_to_open_id_connect_provider(
            OpenIDConnectProviderArn="arn:provider",
            ClientID="new",
            aws_retry=True,
        )
    ) < client.method_calls.index(
        call.remove_client_id_from_open_id_connect_provider(
            OpenIDConnectProviderArn="arn:provider",
            ClientID="old",
            aws_retry=True,
        )
    )
    client.update_open_id_connect_provider_thumbprint.assert_called_once_with(
        OpenIDConnectProviderArn="arn:provider",
        ThumbprintList=["new-thumbprint"],
        aws_retry=True,
    )


def test_new_provider_request_deduplicates_ids_and_includes_tags():
    client = Mock()
    client.create_open_id_connect_provider.return_value = {"OpenIDConnectProviderArn": "arn:provider"}
    module = FakeModule(
        {
            "client_id_list": ["client-b", "client-a", "client-a"],
            "purge_tags": True,
            "tags": {"Name": "main"},
            "thumbprint_list": ["thumbprint", "thumbprint"],
            "url": "https://example.com/id",
        }
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=None),
        patch.object(plugin, "get_provider_by_arn", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert raised.value.values["open_id_connect_provider"] == {
        "client_id_list": ["client-a", "client-b"],
        "open_id_connect_provider_arn": "arn:provider",
        "tags": {"Name": "main"},
        "thumbprint_list": ["thumbprint"],
        "url": "example.com/id",
    }
    client.create_open_id_connect_provider.assert_called_once_with(
        ClientIDList=["client-a", "client-b"],
        Tags=[{"Key": "Name", "Value": "main"}],
        ThumbprintList=["thumbprint"],
        Url="https://example.com/id",
        aws_retry=True,
    )


def test_new_provider_omits_unset_lists_so_aws_applies_its_defaults():
    client = Mock()
    client.create_open_id_connect_provider.return_value = {"OpenIDConnectProviderArn": "arn:provider"}
    module = FakeModule(
        {
            "client_id_list": ["sts.amazonaws.com"],
            "purge_tags": True,
            "tags": None,
            "thumbprint_list": None,
            "url": "https://example.com/id",
        }
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=None),
        patch.object(plugin, "get_provider_by_arn", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    client.create_open_id_connect_provider.assert_called_once_with(
        ClientIDList=["sts.amazonaws.com"],
        Url="https://example.com/id",
        aws_retry=True,
    )


def test_omitted_lists_leave_an_existing_provider_unchanged():
    client = Mock()
    current = {
        "ClientIDList": ["client"],
        "OpenIDConnectProviderArn": "arn:provider",
        "ThumbprintList": ["a" * 40],
        "Url": "example.com/id",
    }
    module = FakeModule(
        {
            "client_id_list": None,
            "purge_tags": True,
            "tags": None,
            "thumbprint_list": None,
            "url": "https://example.com/id",
        }
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    assert client.mock_calls == []


def test_empty_client_id_list_removes_all_client_ids():
    client = Mock()
    current = {
        "ClientIDList": ["client-a", "client-b"],
        "OpenIDConnectProviderArn": "arn:provider",
        "ThumbprintList": ["a" * 40],
        "Url": "example.com/id",
    }
    module = FakeModule(
        {
            "client_id_list": [],
            "purge_tags": True,
            "tags": None,
            "thumbprint_list": None,
            "url": "https://example.com/id",
        }
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert raised.value.values["open_id_connect_provider"]["client_id_list"] == []
    assert client.remove_client_id_from_open_id_connect_provider.call_count == 2
    client.update_open_id_connect_provider_thumbprint.assert_not_called()


@pytest.mark.parametrize("current_count,new_count", [(100, 1), (98, 3)])
def test_oidc_can_replace_audience_at_capacity(current_count, new_count):
    audiences = {f"app-{i}" for i in range(current_count)}
    replacements = {f"replacement-{i}" for i in range(new_count)}
    desired = sorted((audiences - {"app-0"}) | replacements)
    current = {
        "OpenIDConnectProviderArn": "arn:aws:iam::123456789012:oidc-provider/example.org",
        "Url": "example.org",
        "ClientIDList": sorted(audiences),
        "ThumbprintList": [],
    }

    def add(**kwargs):
        if len(audiences) >= 100:
            raise ClientError(
                {"Error": {"Code": "LimitExceeded", "Message": "100 audience limit"}},
                "AddClientIDToOpenIDConnectProvider",
            )

        audiences.add(kwargs["ClientID"])

    def remove(**kwargs):
        audiences.remove(kwargs["ClientID"])

    client = Mock(
        add_client_id_to_open_id_connect_provider=Mock(side_effect=add),
        remove_client_id_from_open_id_connect_provider=Mock(side_effect=remove),
    )
    module = FakeModule(
        {
            "tags": None,
            "url": "https://example.org",
            "client_id_list": desired,
            "thumbprint_list": [],
            "purge_tags": True,
        }
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        patch.object(plugin, "get_provider_by_arn", return_value=dict(current, ClientIDList=desired)),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    assert audiences == set(desired)


def oidc_params(**overrides):
    params = {
        "client_id_list": None,
        "purge_tags": True,
        "tags": None,
        "thumbprint_list": None,
        "url": "https://example.com/id",
    }
    params.update(overrides)
    return params


def oidc_provider(**overrides):
    provider = {
        "ClientIDList": ["keep"],
        "OpenIDConnectProviderArn": "arn:provider",
        "ThumbprintList": ["old-thumbprint"],
        "Url": "example.com/id",
    }
    provider.update(overrides)
    return provider


@pytest.mark.parametrize(("client_id_list", "changed"), [(["keep", "new"], True), (None, False)])
def test_thumbprint_failure_reports_whether_client_ids_were_changed(client_id_list, changed):
    client = Mock()
    client.update_open_id_connect_provider_thumbprint.side_effect = ClientError(
        {"Error": {"Code": "ServiceFailure", "Message": "failed"}}, "UpdateOpenIDConnectProviderThumbprint"
    )
    module = FakeModule(oidc_params(client_id_list=client_id_list, thumbprint_list=["new-thumbprint"]))
    with (
        patch.object(plugin, "get_provider_by_url", return_value=oidc_provider()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Unable to update thumbprints for AWS IAM OIDC provider https://example.com/id"
    assert raised.value.values["changed"] is changed


def test_unsupported_tagging_fails_before_changing_client_ids():
    client = Mock()

    def require(module, client, service, methods, changed=False):
        if "tag_open_id_connect_provider" in methods:
            module.fail_json(changed=changed, msg="Unsupported tagging")

    module = FakeModule(oidc_params(client_id_list=["keep", "new"], tags={"Env": "test"}))
    with (
        patch.object(plugin, "get_provider_by_url", return_value=oidc_provider(Tags=[])),
        patch.object(plugin, "require_client_methods", side_effect=require),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.add_client_id_to_open_id_connect_provider.assert_not_called()


def test_read_failure_after_create_reports_changed():
    client = Mock()
    client.create_open_id_connect_provider.return_value = {"OpenIDConnectProviderArn": "arn:provider"}
    client.get_open_id_connect_provider.side_effect = ClientError(
        {"Error": {"Code": "ServiceFailure", "Message": "failed"}}, "GetOpenIDConnectProvider"
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(oidc_params(client_id_list=["keep"])))

    assert raised.value.values["msg"] == "Unable to get AWS IAM OIDC provider arn:provider"
    assert raised.value.values["changed"] is True
