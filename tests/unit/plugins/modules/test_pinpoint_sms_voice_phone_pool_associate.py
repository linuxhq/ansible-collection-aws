from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_pool_associate as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["pool_id"]["required"] is True
    assert "required" not in options["argument_spec"]["iso_country_code"]


def test_list_capability_includes_pagination_parameters():
    module = FakeModule(
        {
            "client_token": None,
            "iso_country_code": None,
            "origination_identity": "sender-1",
            "pool_id": "pool-1",
            "state": "present",
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    assert require.call_args.args[3]["list_pool_origination_identities"] == ("PoolId", "MaxResults", "NextToken")


def test_association_matches_id_or_arn():
    module = SimpleNamespace(params={"iso_country_code": "US", "origination_identity": "arn:phone"})
    associations = [
        {
            "IsoCountryCode": "US",
            "OriginationIdentity": "phone-1",
            "OriginationIdentityArn": "arn:phone",
        }
    ]
    assert plugin.current_association(module, associations) == associations[0]


def test_association_request_omits_empty_client_token():
    module = SimpleNamespace(
        params={
            "client_token": None,
            "iso_country_code": "US",
            "origination_identity": "phone-1",
            "pool_id": "pool-1",
        }
    )
    assert plugin.association_request(module) == {
        "IsoCountryCode": "US",
        "OriginationIdentity": "phone-1",
        "PoolId": "pool-1",
    }


def test_country_code_is_optional_for_non_country_specific_identities():
    module = SimpleNamespace(
        params={
            "client_token": None,
            "iso_country_code": None,
            "origination_identity": "sender-1",
            "pool_id": "pool-1",
        }
    )
    association = {
        "IsoCountryCode": "US",
        "OriginationIdentity": "sender-1",
    }
    assert plugin.current_association(module, [association]) == association
    assert plugin.association_request(module) == {
        "OriginationIdentity": "sender-1",
        "PoolId": "pool-1",
    }


def test_current_associations_rejects_malformed_response():
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.current_associations(Mock(), FakeModule({"pool_id": "pool-1"}))

    assert "malformed" in raised.value.values["msg"]


def test_present_rejects_wrong_association_response():
    client = Mock()
    client.associate_origination_identity.return_value = {
        "OriginationIdentity": "sender-2",
        "PoolId": "pool-1",
    }
    module = FakeModule(
        {
            "client_token": None,
            "iso_country_code": None,
            "origination_identity": "sender-1",
            "pool_id": "pool-1",
            "state": "present",
        }
    )
    with (
        patch.object(plugin, "current_associations", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert "wrong" in raised.value.values["msg"]


def test_absent_does_not_return_association_that_disappeared():
    client = Mock()
    client.disassociate_origination_identity.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DisassociateOriginationIdentity",
    )
    module = FakeModule(
        {
            "client_token": None,
            "iso_country_code": None,
            "origination_identity": "sender-1",
            "pool_id": "pool-1",
            "state": "absent",
        }
    )
    with (
        patch.object(
            plugin,
            "current_associations",
            return_value=[{"OriginationIdentity": "sender-1"}],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["association"] == {}


def test_rejects_lowercase_country_code():
    module = FakeModule({"iso_country_code": "us", "state": "present"})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "uppercase" in raised.value.values["msg"]


def pool_not_found():
    return plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "ListPoolOriginationIdentities",
    )


@pytest.mark.parametrize("check_mode", [False, True])
def test_present_fails_when_pool_does_not_exist(check_mode):
    client = Mock()
    module = FakeModule(
        {
            "client_token": None,
            "iso_country_code": None,
            "origination_identity": "sender-1",
            "pool_id": "pool-missing",
            "state": "present",
        },
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "paginated_query_with_retries", side_effect=pool_not_found()),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Pinpoint SMS Voice V2 pool pool-missing does not exist"
    client.associate_origination_identity.assert_not_called()


def test_absent_reports_no_change_when_pool_does_not_exist():
    client = Mock()
    module = FakeModule(
        {
            "client_token": None,
            "iso_country_code": None,
            "origination_identity": "sender-1",
            "pool_id": "pool-missing",
            "state": "absent",
        }
    )
    with (
        patch.object(plugin, "paginated_query_with_retries", side_effect=pool_not_found()),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    client.disassociate_origination_identity.assert_not_called()
