from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

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


def test_missing_id_returns_empty_list():
    client = Mock(
        get_reusable_delegation_set=Mock(
            side_effect=ClientError(
                {"Error": {"Code": "NoSuchDelegationSet", "Message": "missing"}},
                "GetReusableDelegationSet",
            )
        )
    )
    module = FakeModule({"id": "delegation-1"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"changed": False, "delegation_sets": []}
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


@pytest.mark.parametrize("delegation_set_id", ["/delegationset/", "delegation-1/"])
def test_id_without_a_delegation_set_id_fails_before_any_aws_call(delegation_set_id):
    # Live: GetReusableDelegationSet(Id="/delegationset/") returns no DelegationSet and no error.
    client = Mock(get_reusable_delegation_set=Mock(return_value={}))
    module = FakeModule({"id": delegation_set_id}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": (
            f"Unable to get AWS Route53 reusable delegation set {delegation_set_id}: "
            "id must end with a delegation set ID"
        )
    }
    client.get_reusable_delegation_set.assert_not_called()


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
