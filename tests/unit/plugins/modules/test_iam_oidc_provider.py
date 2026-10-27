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

    assert raised.value.values["changed"] is False


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


@pytest.mark.parametrize(
    ("client_id_list", "expected_client_ids"),
    [(["a", "b"], ["b", "a"]), (["a", "c"], ["a", "c"])],
    ids=["tags-only", "client-ids"],
)
def test_check_mode_on_an_existing_provider_matches_the_real_run(client_id_list, expected_client_ids):
    results = {}
    for check_mode in (False, True):
        module = FakeModule(
            {
                "client_id_list": client_id_list,
                "purge_tags": True,
                "tags": {"New": "x"},
                "thumbprint_list": ["a" * 40],
                "url": "https://example.com/id",
            },
            check_mode=check_mode,
        )
        current = {
            "ClientIDList": ["b", "a"],
            "OpenIDConnectProviderArn": "arn:provider",
            "Tags": [],
            "ThumbprintList": ["A" * 40],
            "Url": "Example.com/id/",
        }
        with (
            patch.object(plugin, "get_provider_by_url", return_value=current),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        results[check_mode] = raised.value.values

    assert results[True] == results[False]
    provider = results[True]["open_id_connect_provider"]
    assert provider["client_id_list"] == expected_client_ids
    assert provider["tags"] == {"New": "x"}
    assert provider["url"] == "Example.com/id/"


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


@pytest.mark.parametrize("check_mode", [False, True])
def test_tag_limit_without_purge_fails_before_any_change(check_mode):
    client = Mock()
    existing = [{"Key": f"old{index}", "Value": ""} for index in range(45)]
    new_tags = {f"new{index}": "" for index in range(10)}
    module = FakeModule(
        oidc_params(client_id_list=["keep", "new"], purge_tags=False, tags=new_tags), check_mode=check_mode
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=oidc_provider(Tags=existing)),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "The resulting OIDC provider tags must contain at most 50 entries"
    assert raised.value.values.get("changed", False) is False
    client.add_client_id_to_open_id_connect_provider.assert_not_called()
    client.tag_open_id_connect_provider.assert_not_called()


def test_aws_reserved_tags_do_not_count_against_the_tag_limit():
    client = Mock()
    existing = [{"Key": f"aws:reserved{index}", "Value": ""} for index in range(10)]
    existing += [{"Key": f"old{index}", "Value": ""} for index in range(40)]
    new_tags = {f"new{index}": "" for index in range(10)}
    module = FakeModule(oidc_params(purge_tags=False, tags=new_tags), check_mode=True)
    with (
        patch.object(plugin, "get_provider_by_url", return_value=oidc_provider(Tags=existing)),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True


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


@pytest.mark.parametrize("tags", [None, {}, {"Name": "x"}], ids=["no-tags", "empty-tags", "tags"])
@pytest.mark.parametrize("client_id_list", [None, ["sts.amazonaws.com"]], ids=["no-client-ids", "client-ids"])
def test_check_mode_create_matches_the_real_create(client_id_list, tags):
    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.create_open_id_connect_provider.return_value = {"OpenIDConnectProviderArn": "arn:provider"}
        # IAM reports an empty ClientIDList and Tags list for a provider created without them.
        client.get_open_id_connect_provider.return_value = {
            "ClientIDList": client_id_list or [],
            "CreateDate": "2026-10-26T00:00:00+00:00",
            "Tags": [{"Key": key, "Value": value} for key, value in (tags or {}).items()],
            "ThumbprintList": ["a" * 40],
            "Url": "example.com/id",
        }
        module = FakeModule(
            oidc_params(client_id_list=client_id_list, tags=tags, thumbprint_list=["A" * 40]),
            check_mode=check_mode,
        )
        with (
            patch.object(plugin, "get_provider_by_url", return_value=None),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        results[check_mode] = raised.value.values

    real = results[False]
    assert real.pop("open_id_connect_provider_arn") == "arn:provider"
    assert real["open_id_connect_provider"].pop("open_id_connect_provider_arn") == "arn:provider"
    assert real["open_id_connect_provider"].pop("create_date")
    assert results[True] == real
    assert real["open_id_connect_provider"]["client_id_list"] == (client_id_list or [])
    assert real["open_id_connect_provider"]["tags"] == (tags or {})


def test_create_fallback_reports_the_provider_as_iam_creates_it():
    client = Mock()
    client.create_open_id_connect_provider.return_value = {"OpenIDConnectProviderArn": "arn:provider"}
    with (
        patch.object(plugin, "get_provider_by_url", return_value=None),
        patch.object(plugin, "get_provider_by_arn", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(oidc_params(thumbprint_list=["a" * 40])))

    assert raised.value.values["open_id_connect_provider"] == {
        "client_id_list": [],
        "open_id_connect_provider_arn": "arn:provider",
        "tags": {},
        "thumbprint_list": ["a" * 40],
        "url": "example.com/id",
    }


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("client_id_list", "thumbprint_list", "expected"),
    [
        (
            ["a", "b", "c"],
            ["A" * 40, "F" * 40],
            {"client_id_list": ["b", "a", "c"], "thumbprint_list": ["f" * 40, "a" * 40]},
        ),
        (["a", "b"], ["c" * 40], {"client_id_list": ["b", "a"], "thumbprint_list": ["c" * 40]}),
    ],
    ids=["client-ids-written", "thumbprints-written"],
)
def test_update_returns_an_unwritten_list_as_iam_keeps_it(check_mode, client_id_list, thumbprint_list, expected):
    # IAM keeps the order of a list that no call writes, so that list is returned as IAM reported it. Written client
    # IDs are returned as IAM keeps them: the remaining IDs in their order, then the added ones.
    client = Mock()
    current = oidc_provider(ClientIDList=["b", "a"], Tags=[], ThumbprintList=["f" * 40, "a" * 40])
    module = FakeModule(
        oidc_params(client_id_list=client_id_list, thumbprint_list=thumbprint_list), check_mode=check_mode
    )
    with (
        patch.object(plugin, "get_provider_by_url", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    provider = raised.value.values["open_id_connect_provider"]
    assert raised.value.values["changed"] is True
    assert {key: provider[key] for key in expected} == expected
    assert client.add_client_id_to_open_id_connect_provider.called is (not check_mode and "c" in client_id_list)
    assert client.update_open_id_connect_provider_thumbprint.called is (not check_mode and "c" * 40 in thumbprint_list)


APPS = [f"app-{index:02}" for index in range(100)]


@pytest.mark.parametrize(
    ("current_client_ids", "client_id_list"),
    [
        (["z"], ["a", "z"]),
        (["z", "a"], ["0", "a"]),
        (["sts.amazonaws.com", "old", "api"], ["web", "api", "sts.amazonaws.com", "cli"]),
        (APPS[::-1], [app for app in APPS if app not in ("app-10", "app-50")] + ["new-b", "new-a"]),
        (APPS[98::-1], [app for app in APPS[:99] if app not in ("app-10", "app-50")] + ["new-b", "new-a"]),
    ],
    ids=["add", "replace", "add-and-remove", "at-capacity", "near-capacity"],
)
def test_written_client_ids_are_returned_in_the_order_iam_keeps(current_client_ids, client_id_list):
    # Live IAM removes a client ID in place and appends an added one, for example [z] + add a -> [z, a].
    stored = list(current_client_ids)

    def add(**kwargs):
        assert len(stored) < 100
        stored.append(kwargs["ClientID"])

    def remove(**kwargs):
        stored.remove(kwargs["ClientID"])

    current = oidc_provider(ClientIDList=current_client_ids, Tags=[])
    results = {}
    for check_mode in (True, False):
        client = Mock(
            add_client_id_to_open_id_connect_provider=Mock(side_effect=add),
            remove_client_id_from_open_id_connect_provider=Mock(side_effect=remove),
        )
        with (
            patch.object(plugin, "get_provider_by_url", return_value=current),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, FakeModule(oidc_params(client_id_list=client_id_list), check_mode=check_mode))

        results[check_mode] = raised.value.values

    assert sorted(stored) == sorted(client_id_list)
    assert stored != sorted(stored)
    assert results[False]["open_id_connect_provider"]["client_id_list"] == stored
    assert results[True] == results[False]
