from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import route53_delegation_set as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_absent_tolerates_set_disappearing_during_delete():
    client = Mock()
    client.delete_reusable_delegation_set.side_effect = plugin.ClientError(
        {"Error": {"Code": "NoSuchDelegationSet", "Message": "gone"}},
        "DeleteReusableDelegationSet",
    )
    module = FakeModule({"name": "main"})
    with (
        patch.object(
            plugin,
            "get_reusable_delegation_set",
            return_value={"Id": "delegation-set-1"},
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    # AWS reported the set already gone, so this run deleted nothing.
    assert raised.value.values["changed"] is False
    client.delete_reusable_delegation_set.assert_called_once()


def test_absent_reports_changed_after_a_delete():
    client = Mock()
    module = FakeModule({"name": "main"})
    with (
        patch.object(plugin, "get_reusable_delegation_set", return_value={"Id": "delegation-set-1"}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is True
    client.delete_reusable_delegation_set.assert_called_once_with(Id="delegation-set-1", aws_retry=True)


def test_absent_reports_unchanged_when_the_set_is_missing():
    client = Mock()
    module = FakeModule({"name": "main"})
    with (
        patch.object(plugin, "get_reusable_delegation_set", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values == {"changed": False, "name": "main", "state": "absent"}
    client.delete_reusable_delegation_set.assert_not_called()


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["name"]["required"] is True


def test_absent_with_a_long_name_converges():
    # A caller reference longer than CreateReusableDelegationSet accepts identifies no delegation set.
    client = Mock()
    module = FakeModule({"name": "n" * 129, "state": "absent"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"CallerReference": "other", "Id": "delegation-1"}]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"changed": False, "name": "n" * 129, "state": "absent"}
    client.delete_reusable_delegation_set.assert_not_called()


def test_check_mode_predicts_delegation_set():
    module = FakeModule({"name": "example"}, check_mode=True)
    with (
        patch.object(plugin, "get_reusable_delegation_set", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert raised.value.values["changed"]
    assert raised.value.values["delegation_set"] == {"caller_reference": "example"}


def test_lookup_uses_all_paginated_delegation_sets():
    client = Mock()
    module = FakeModule({"name": "example"})
    with patch.object(
        plugin,
        "query_list",
        return_value=[
            {"CallerReference": "other", "Id": "delegation-0"},
            {"CallerReference": "example", "Id": "delegation-1"},
        ],
    ) as query:
        result = plugin.get_reusable_delegation_set(client, module)

    assert result["Id"] == "delegation-1"
    query.assert_called_once()


def test_create_returns_the_created_set():
    client = Mock()
    client.create_reusable_delegation_set.return_value = {
        "DelegationSet": {"CallerReference": "example", "Id": "delegation-1", "NameServers": ["ns-1.example"]},
        "Location": "https://route53.amazonaws.com/2013-04-01/delegationset/delegation-1",
    }
    module = FakeModule({"name": "example"})
    with (
        patch.object(plugin, "get_reusable_delegation_set", return_value=None) as get,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    get.assert_called_once()
    assert raised.value.values["changed"]
    assert raised.value.values["delegation_set_id"] == "delegation-1"


def test_listing_requires_pagination_parameters():
    client = Mock()
    module = FakeModule({"name": "example", "state": "absent"})
    module.client = Mock(return_value=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "ensure_absent"),
    ):
        plugin.main()

    require_methods.assert_called_once_with(
        module,
        client,
        "Route53",
        {
            "list_reusable_delegation_sets": ("Marker", "MaxItems"),
            "delete_reusable_delegation_set": ("Id",),
        },
    )


def test_reused_caller_reference_fails_with_an_explanation():
    client = Mock()
    client.create_reusable_delegation_set.side_effect = plugin.ClientError(
        {"Error": {"Code": "DelegationSetAlreadyCreated", "Message": "already created"}},
        "CreateReusableDelegationSet",
    )
    module = FakeModule({"name": "main"})
    with (
        patch.object(plugin, "get_reusable_delegation_set", return_value=None),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == (
        "Unable to create AWS Route53 reusable delegation set main: the name was already used "
        "by a deleted delegation set and cannot be reused; choose a new name"
    )


def test_already_created_set_that_is_now_listed_is_used():
    client = Mock()
    client.create_reusable_delegation_set.side_effect = plugin.ClientError(
        {"Error": {"Code": "DelegationSetAlreadyCreated", "Message": "already created"}},
        "CreateReusableDelegationSet",
    )
    delegation_set = {"CallerReference": "main", "Id": "/delegationset/N1"}
    with (
        patch.object(plugin, "get_reusable_delegation_set", side_effect=[None, delegation_set]) as get,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule({"name": "main"}))

    assert get.call_count == 2
    assert raised.value.values["changed"] is True
    assert raised.value.values["delegation_set_id"] == "/delegationset/N1"
