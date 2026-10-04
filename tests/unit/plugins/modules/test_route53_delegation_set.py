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

    assert raised.value.values["changed"]


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["name"]["required"] is True


def test_absent_rejects_empty_name():
    module = FakeModule({"name": "", "state": "absent"})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "name must be 1 to 128 characters"


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


def test_lookup_rejects_malformed_delegation_sets():
    module = FakeModule({"name": "example"})
    for delegation_sets in ([None], [{"CallerReference": "example"}]):
        with (
            patch.object(plugin, "query_list", return_value=delegation_sets),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.get_reusable_delegation_set(Mock(), module)

        assert (
            raised.value.values["msg"]
            == "Unable to list AWS Route53 reusable delegation sets: AWS returned an invalid response"
        )


def test_create_uses_lookup_when_response_is_malformed():
    client = Mock()
    client.create_reusable_delegation_set.return_value = None
    module = FakeModule({"name": "example"})
    with (
        patch.object(
            plugin,
            "get_reusable_delegation_set",
            side_effect=[None, {"CallerReference": "example", "Id": "delegation-1"}],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

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
