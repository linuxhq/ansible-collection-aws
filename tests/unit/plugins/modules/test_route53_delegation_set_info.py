from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import route53_delegation_set_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["id"]["type"] == "str"


def test_id_uses_get_reusable_delegation_set():
    client = Mock(get_reusable_delegation_set=Mock(return_value={"DelegationSet": {"Id": "delegation-1"}}))
    module = FakeModule({"id": "delegation-1"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require_methods.assert_called_once_with(
        module,
        client,
        "Route53",
        {"get_reusable_delegation_set": ("Id",)},
    )
    client.get_reusable_delegation_set.assert_called_once_with(Id="delegation-1", aws_retry=True)


def test_listing_uses_shared_pagination():
    client = Mock()
    module = FakeModule({"id": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"Id": "delegation-1"}],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["delegation_sets"] == [{"id": "delegation-1"}]
    query.assert_called_once()


def test_listing_requires_pagination_parameters():
    client = Mock()
    module = FakeModule({"id": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require_methods.assert_called_once_with(
        module,
        client,
        "Route53",
        {"list_reusable_delegation_sets": ("Marker", "MaxItems")},
    )


def test_get_rejects_malformed_or_wrong_delegation_set():
    responses = (
        None,
        {},
        {"DelegationSet": None},
        {"DelegationSet": {"Id": "delegation-2"}},
    )
    for response in responses:
        client = Mock(get_reusable_delegation_set=Mock(return_value=response))
        module = FakeModule({"id": "delegation-1"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleFail),
        ):
            plugin.main()


def test_get_accepts_full_path_for_bare_response_id():
    client = Mock(get_reusable_delegation_set=Mock(return_value={"DelegationSet": {"Id": "delegation-1"}}))
    module = FakeModule({"id": "/delegationset/delegation-1"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["delegation_sets"] == [{"id": "delegation-1"}]


def test_listing_rejects_malformed_delegation_set():
    module = FakeModule({"id": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert (
        raised.value.values["msg"]
        == "Unable to list AWS Route53 reusable delegation sets: AWS returned an invalid response"
    )
