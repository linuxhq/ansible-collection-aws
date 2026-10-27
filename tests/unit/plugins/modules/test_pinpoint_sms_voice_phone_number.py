from unittest.mock import Mock, call, patch

import pytest
from botocore.session import get_session

from ansible_collections.linuxhq.aws.plugins.module_utils import pinpoint_sms_voice
from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_number as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def model_client():
    """Return a mock client with the real botocore model, for check-mode predictions that read it."""
    return Mock(meta=get_session().create_client("pinpoint-sms-voice-v2", region_name="us-east-1").meta)


def pool_with_other_phone_number():
    """A ListPoolOriginationIdentities result where phone-1 is not the last phone number."""
    return {
        "OriginationIdentities": [
            {"OriginationIdentity": "phone-1", "PhoneNumber": "+12065550100"},
            {"OriginationIdentity": "phone-2", "PhoneNumber": "+12065550101"},
        ]
    }


def test_module_contract():
    options = assert_module_contract(plugin)
    assert len(options["required_if"]) == 2


def test_accepts_four_capabilities():
    client = model_client()
    module = FakeModule(
        {
            "client_token": None,
            "deletion_protection_enabled": False,
            "international_sending_enabled": None,
            "number_capabilities": ["MMS", "RCS", "SMS", "VOICE"],
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_type": "LONG_CODE",
            "opt_out_list_name": None,
            "pool_id": None,
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
            "wait_delay": 5,
            "wait_timeout": 300,
        },
        check_mode=True,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    require.assert_called_once_with(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {
            "describe_phone_numbers": (
                "MaxResults",
                "NextToken",
                "PhoneNumberIds",
                "Filters",
                "Owner",
            )
        },
    )
    client.request_phone_number.assert_not_called()


def test_capability_limit_counts_unique_values():
    client = model_client()
    module = FakeModule(
        {
            "client_token": None,
            "deletion_protection_enabled": False,
            "international_sending_enabled": None,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_capabilities": ["SMS"] * 5,
            "number_type": "LONG_CODE",
            "opt_out_list_name": None,
            "pool_id": None,
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
            "wait_delay": 5,
            "wait_timeout": 300,
        },
        check_mode=True,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()


def test_simulator_numbers_require_transactional_messages():
    module = FakeModule(
        {
            "iso_country_code": "US",
            "message_type": "PROMOTIONAL",
            "number_capabilities": ["SMS"],
            "number_type": "SIMULATOR",
            "state": "present",
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "must be TRANSACTIONAL" in raised.value.values["msg"]


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("value", ["", "  "])
@pytest.mark.parametrize("option", ["opt_out_list_name", "pool_id", "registration_id"])
def test_present_rejects_empty_identifiers_before_any_aws_call(option, value, check_mode):
    # AWS rejects each of them empty or blank, so check mode must not predict a request or an update with one.
    client = Mock()
    module = FakeModule(
        dict(phone_number_params(**{option: value}), wait_delay=5, wait_timeout=300),
        check_mode=check_mode,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(module, "client") as connect,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == f"{option} must not be empty"
    connect.assert_not_called()
    assert client.mock_calls == []


def test_absent_ignores_empty_identifiers_used_only_with_present():
    client = Mock()
    module = FakeModule(
        dict(
            phone_number_params(
                opt_out_list_name="",
                phone_number_id="phone-1",
                pool_id="",
                registration_id="",
                state="absent",
            ),
            wait_delay=5,
            wait_timeout=300,
        ),
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_absent") as ensure_absent,
    ):
        plugin.main()

    ensure_absent.assert_called_once_with(client, module)


def test_existing_number_matches_capabilities_without_order():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "international_sending_enabled": None,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_capabilities": ["SMS", "VOICE"],
            "number_type": "LONG_CODE",
            "opt_out_list_name": None,
            "pool_id": None,
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "DeletionProtectionEnabled": False,
        "IsoCountryCode": "US",
        "MessageType": "TRANSACTIONAL",
        "NumberCapabilities": ["VOICE", "SMS"],
        "NumberType": "LONG_CODE",
        "PhoneNumberId": "phone-1",
        "Status": "ACTIVE",
    }
    with (
        patch.object(plugin, "query_list", return_value=[current]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    assert raised.value.values["phone_number_id"] == "phone-1"
    client.request_phone_number.assert_not_called()


def test_existing_number_rejects_malformed_response():
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "international_sending_enabled": None,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_capabilities": ["SMS"],
            "number_type": "LONG_CODE",
            "opt_out_list_name": None,
            "pool_id": None,
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        }
    )
    with (
        patch.object(plugin, "query_list", return_value=[{"Status": "ACTIVE"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert "malformed" in raised.value.values["msg"]


def test_existing_number_matches_pool_and_opt_out_list_arns():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "international_sending_enabled": None,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_capabilities": ["SMS"],
            "number_type": "LONG_CODE",
            "opt_out_list_name": "arn:aws:sms-voice:us-east-1:1:opt-out-list/list-1",
            "pool_id": "arn:aws:sms-voice:us-east-1:1:pool/pool-1",
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "DeletionProtectionEnabled": False,
        "IsoCountryCode": "US",
        "MessageType": "TRANSACTIONAL",
        "NumberCapabilities": ["SMS"],
        "NumberType": "LONG_CODE",
        "OptOutListName": "list-1",
        "PhoneNumberId": "phone-1",
        "PoolId": "pool-1",
        "Status": "ACTIVE",
    }
    with (
        patch.object(plugin, "query_list", return_value=[current]) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    filter_names = {item["Name"] for item in query.call_args.kwargs["Filters"]}
    assert "opt-out-list-name" not in filter_names
    assert "deletion-protection-enabled" not in filter_names
    assert not raised.value.values["changed"]
    client.request_phone_number.assert_not_called()


def test_check_mode_does_not_wait_for_existing_number():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "international_sending_enabled": None,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_capabilities": ["SMS"],
            "number_type": "LONG_CODE",
            "opt_out_list_name": None,
            "pool_id": None,
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": True,
        },
        check_mode=True,
    )
    current = {
        "DeletionProtectionEnabled": False,
        "IsoCountryCode": "US",
        "MessageType": "TRANSACTIONAL",
        "NumberCapabilities": ["SMS"],
        "NumberType": "LONG_CODE",
        "PhoneNumberId": "phone-1",
        "Status": "PENDING",
    }
    with (
        patch.object(plugin, "query_list", return_value=[current]),
        patch.object(plugin, "wait_for_phone_number_active") as wait_for_active,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    wait_for_active.assert_not_called()


def test_check_mode_projects_deduplicated_request_without_client_token():
    client = model_client()
    module = FakeModule(
        {
            "client_token": "secret-token",
            "deletion_protection_enabled": True,
            "international_sending_enabled": False,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "number_capabilities": ["VOICE", "SMS", "SMS"],
            "number_type": "LONG_CODE",
            "opt_out_list_name": None,
            "pool_id": None,
            "registration_id": None,
            "phone_number_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    phone_number = raised.value.values["phone_number"]
    assert raised.value.values["changed"]
    assert phone_number["number_capabilities"] == ["SMS", "VOICE"]
    assert "client_token" not in phone_number
    client.request_phone_number.assert_not_called()


def test_deleted_number_stops_activation_wait():
    module = FakeModule(
        {
            "tags": None,
            "wait_delay": 1,
            "wait_timeout": 10,
        }
    )
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(
            plugin,
            "get_phone_number",
            return_value={"PhoneNumberId": "phone-1", "Status": "DELETED"},
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_phone_number_active(Mock(), module, "phone-1")

    assert raised.value.values["status"] == "DELETED"


@pytest.mark.parametrize("changed", [False, True])
def test_present_activation_wait_fails_when_a_seen_number_disappears(changed):
    module = FakeModule({"state": "present", "tags": None, "wait_delay": 1, "wait_timeout": 10})
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1, 1, 1]),
        patch.object(plugin.time, "sleep") as sleep,
        patch.object(plugin, "get_phone_number", side_effect=[{"PhoneNumberId": "phone-1", "Status": "PENDING"}, None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_phone_number_active(Mock(), module, "phone-1", changed=changed)

    assert raised.value.values["changed"] is changed
    assert raised.value.values["msg"] == (
        "AWS End User Messaging SMS phone number phone-1 was released while waiting for it to become active"
    )
    sleep.assert_called_once()


def test_present_activation_wait_polls_until_a_new_number_is_visible():
    module = FakeModule({"state": "present", "tags": None, "wait_delay": 1, "wait_timeout": 10})
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1, 1, 1]),
        patch.object(plugin.time, "sleep"),
        patch.object(plugin, "get_phone_number", side_effect=[None, {"PhoneNumberId": "phone-1", "Status": "ACTIVE"}]),
    ):
        result = plugin.wait_for_phone_number_active(Mock(), module, "phone-1")

    assert result["Status"] == "ACTIVE"


def test_absent_activation_wait_does_not_fetch_tags():
    client = Mock()
    module = FakeModule(
        {
            "state": "absent",
            "tags": {"Name": "ignored"},
            "wait_delay": 1,
            "wait_timeout": 10,
        }
    )
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(
            plugin,
            "get_phone_number",
            return_value={
                "PhoneNumberArn": "arn:phone-1",
                "PhoneNumberId": "phone-1",
                "Status": "ACTIVE",
            },
        ),
    ):
        plugin.wait_for_phone_number_active(client, module, "phone-1")

    client.list_tags_for_resource.assert_not_called()


def test_absent_activation_wait_accepts_external_deletion():
    module = FakeModule(
        {
            "state": "absent",
            "tags": None,
            "wait_delay": 1,
            "wait_timeout": 10,
        }
    )
    deleted = {"PhoneNumberId": "phone-1", "Status": "DELETED"}
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(plugin, "get_phone_number", return_value=deleted),
    ):
        result = plugin.wait_for_phone_number_active(Mock(), module, "phone-1")

    assert result == deleted


def test_absent_activation_wait_accepts_disappearing_number():
    module = FakeModule(
        {
            "state": "absent",
            "tags": None,
            "wait_delay": 1,
            "wait_timeout": 10,
        }
    )
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(plugin, "get_phone_number", return_value=None),
    ):
        result = plugin.wait_for_phone_number_active(Mock(), module, "phone-1")

    assert result == {}


def test_phone_number_tags_rejects_malformed_response():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": "invalid"}
    module = FakeModule({})

    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.phone_number_tags(client, module, {"PhoneNumberArn": "arn:phone-1"})

    assert "malformed tags" in raised.value.values["msg"]


@pytest.mark.parametrize("missing_ok", [False, True])
def test_phone_number_tags_reports_a_released_number_only_when_missing_is_allowed(missing_ok):
    client = Mock()
    client.list_tags_for_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "ListTagsForResource",
    )
    with patch.object(plugin, "require_client_methods"):
        if missing_ok:
            assert (
                plugin.phone_number_tags(client, FakeModule({}), {"PhoneNumberArn": "arn:phone-1"}, missing_ok=True)
                is None
            )
        else:
            with pytest.raises(ModuleFail):
                plugin.phone_number_tags(client, FakeModule({}), {"PhoneNumberArn": "arn:phone-1"})


def test_name_matching_skips_a_candidate_released_before_its_tags_are_listed():
    client = Mock()

    def list_tags(ResourceArn, aws_retry):
        if ResourceArn == "arn:phone-2":
            raise plugin.ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
                "ListTagsForResource",
            )

        return {"Tags": [{"Key": "Name", "Value": "sms"}]}

    client.list_tags_for_resource.side_effect = list_tags
    module = FakeModule(phone_number_params(tags={"Name": "sms"}), check_mode=True)
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[
                existing_number(PhoneNumberArn="arn:phone-2", PhoneNumberId="phone-2"),
                existing_number(PhoneNumberArn="arn:phone-1"),
            ],
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    assert raised.value.values["phone_number_id"] == "phone-1"
    client.request_phone_number.assert_not_called()


def test_get_phone_number_rejects_malformed_response():
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_phone_number(Mock(), FakeModule({}), "phone-1")

    assert "malformed" in raised.value.values["msg"]


def test_get_phone_number_rejects_wrong_phone_number():
    response = {"PhoneNumbers": [{"PhoneNumberId": "phone-2", "Status": "ACTIVE"}]}
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=response),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_phone_number(Mock(), FakeModule({}), "phone-1")

    assert "wrong" in raised.value.values["msg"]


PHONE_NUMBER_ARN = "arn:aws:sms-voice:us-east-1:111111111111:phone-number/phone-1"


def test_get_phone_number_accepts_an_arn():
    response = {"PhoneNumbers": [{"PhoneNumberId": "phone-1", "Status": "ACTIVE"}]}
    with patch.object(plugin, "paginated_query_with_retries", return_value=response) as query:
        result = plugin.get_phone_number(Mock(), FakeModule({}), PHONE_NUMBER_ARN)

    assert query.call_args.kwargs["PhoneNumberIds"] == [PHONE_NUMBER_ARN]
    assert result["PhoneNumberId"] == "phone-1"


def test_get_phone_number_rejects_wrong_phone_number_for_an_arn():
    response = {"PhoneNumbers": [{"PhoneNumberId": "phone-2", "Status": "ACTIVE"}]}
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=response),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_phone_number(Mock(), FakeModule({}), PHONE_NUMBER_ARN)

    assert "wrong" in raised.value.values["msg"]


def test_absent_removes_pool_and_deletion_protection_before_release():
    client = Mock()
    client.update_phone_number.return_value = {
        "DeletionProtectionEnabled": False,
        "PhoneNumberId": "phone-1",
        "Status": "UPDATING",
    }
    client.release_phone_number.return_value = {
        "PhoneNumberId": "phone-1",
        "Status": "DELETED",
    }
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})

    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value={
                "DeletionProtectionEnabled": True,
                "PhoneNumberId": "phone-1",
                "PoolId": "pool-1",
                "Status": "ACTIVE",
            },
        ),
        patch.object(
            plugin,
            "wait_for_phone_number_active",
            return_value={
                "DeletionProtectionEnabled": True,
                "PhoneNumberId": "phone-1",
                "Status": "ACTIVE",
            },
        ) as wait_for_phone_number_active,
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    client.disassociate_origination_identity.assert_called_once_with(
        PoolId="pool-1",
        OriginationIdentity="phone-1",
        aws_retry=True,
    )
    client.update_phone_number.assert_called_once_with(
        PhoneNumberId="phone-1",
        DeletionProtectionEnabled=False,
        aws_retry=True,
    )
    assert wait_for_phone_number_active.call_args_list == [
        call(client, module, "phone-1", changed=True),
        call(client, module, "phone-1", changed=True),
    ]
    client.release_phone_number.assert_called_once_with(PhoneNumberId="phone-1", aws_retry=True)
    assert raised.value.values["changed"]


def test_absent_disassociates_with_the_phone_number_country():
    """Older botocore models require IsoCountryCode, so the number's own country is sent and gated."""
    client = Mock()
    client.release_phone_number.return_value = {"PhoneNumberId": "phone-1", "Status": "DELETED"}
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(
            plugin, "get_phone_number", return_value=existing_number(DeletionProtectionEnabled=False, PoolId="pool-1")
        ),
        patch.object(
            plugin, "wait_for_phone_number_active", return_value=existing_number(DeletionProtectionEnabled=False)
        ),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert sorted(require.call_args_list[-1].args[3]["disassociate_origination_identity"]) == [
        "IsoCountryCode",
        "OriginationIdentity",
        "PoolId",
    ]
    client.disassociate_origination_identity.assert_called_once_with(
        IsoCountryCode="US",
        OriginationIdentity="phone-1",
        PoolId="pool-1",
        aws_retry=True,
    )
    client.release_phone_number.assert_called_once_with(PhoneNumberId="phone-1", aws_retry=True)
    assert raised.value.values["changed"] is True


def test_absent_tolerates_disappearing_prerequisites():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeletePhoneNumber",
    )
    client = Mock()
    client.disassociate_origination_identity.side_effect = missing
    client.update_phone_number.side_effect = missing
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent"})

    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value={
                "DeletionProtectionEnabled": True,
                "PhoneNumberId": "phone-1",
                "PoolId": "pool-1",
                "Status": "ACTIVE",
            },
        ),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    client.release_phone_number.assert_not_called()


def test_absent_does_not_return_stale_data_when_release_races_with_deletion():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "ReleasePhoneNumber",
    )
    client = Mock()
    client.release_phone_number.side_effect = missing
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})

    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value={"PhoneNumberId": "phone-1", "Status": "ACTIVE"},
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert "phone_number" not in raised.value.values


def not_found(operation):
    return plugin.ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}}, operation)


def test_absent_deletion_protection_race_after_disassociation_reports_changed():
    client = Mock()
    client.update_phone_number.side_effect = not_found("UpdatePhoneNumber")
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PoolId="pool-1")),
        patch.object(plugin, "wait_for_phone_number_active", return_value=existing_number()),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is True
    assert "phone_number" not in raised.value.values
    client.release_phone_number.assert_not_called()


@pytest.mark.parametrize(
    ("deletion_protection_enabled", "pool_id", "changed"),
    [(False, None, False), (False, "pool-1", True), (True, None, True)],
)
def test_absent_release_race_reports_whether_the_number_was_changed(deletion_protection_enabled, pool_id, changed):
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False)
    client.release_phone_number.side_effect = not_found("ReleasePhoneNumber")
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value=existing_number(DeletionProtectionEnabled=deletion_protection_enabled, PoolId=pool_id),
        ),
        patch.object(
            plugin,
            "wait_for_phone_number_active",
            return_value=existing_number(DeletionProtectionEnabled=deletion_protection_enabled),
        ),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is changed
    assert "phone_number" not in raised.value.values


def test_explicit_number_tags_preserve_resource_identity():
    for purge in (False, True):
        for check in (False, True):
            client = Mock()
            current = {
                "PhoneNumberId": "phone-1",
                "PhoneNumberArn": "arn:phone-1",
                "Status": "ACTIVE",
                "IsoCountryCode": "US",
                "MessageType": "TRANSACTIONAL",
                "NumberType": "SIMULATOR",
                "NumberCapabilities": ["SMS"],
                "DeletionProtectionEnabled": False,
            }
            module = FakeModule(
                {
                    "phone_number_id": "phone-1",
                    "purge_tags": purge,
                    "tags": {"Keep": "updated"},
                    "deletion_protection_enabled": False,
                    "international_sending_enabled": None,
                    "iso_country_code": "US",
                    "message_type": "TRANSACTIONAL",
                    "number_capabilities": ["SMS"],
                    "number_type": "SIMULATOR",
                    "opt_out_list_name": None,
                    "pool_id": None,
                    "registration_id": None,
                    "wait": True,
                    "state": "present",
                },
                check_mode=check,
            )
            with (
                patch.object(plugin, "get_phone_number", return_value=current),
                patch.object(plugin, "phone_number_tags", return_value={"Keep": "old", "Extra": "preserved"}),
                patch.object(plugin, "require_client_methods"),
                pytest.raises(ModuleExit) as raised,
            ):
                plugin.ensure_present(client, module)

            values = raised.value.values
            assert values["changed"]
            assert values["phone_number"]["phone_number_id"] == "phone-1"
            expected = {"Keep": "updated"}
            if not purge:
                expected["Extra"] = "preserved"

            assert values["phone_number"]["tags"] == expected
            assert client.tag_resource.call_count == (0 if check else 1)
            assert client.untag_resource.call_count == (1 if purge and not check else 0)
            client.request_phone_number.assert_not_called()
            client.release_phone_number.assert_not_called()


def phone_number_params(**overrides):
    params = {
        "client_token": None,
        "deletion_protection_enabled": None,
        "international_sending_enabled": None,
        "iso_country_code": "US",
        "message_type": "TRANSACTIONAL",
        "number_capabilities": ["SMS"],
        "number_type": "LONG_CODE",
        "opt_out_list_name": None,
        "pool_id": None,
        "registration_id": None,
        "phone_number_id": None,
        "purge_tags": True,
        "state": "present",
        "tags": None,
        "wait": False,
    }
    params.update(overrides)
    return params


def existing_number(**overrides):
    number = {
        "DeletionProtectionEnabled": True,
        "InternationalSendingEnabled": False,
        "IsoCountryCode": "US",
        "MessageType": "TRANSACTIONAL",
        "NumberCapabilities": ["SMS"],
        "NumberType": "LONG_CODE",
        "OptOutListName": "default",
        "PhoneNumberId": "phone-1",
        "Status": "ACTIVE",
    }
    number.update(overrides)
    return number


@pytest.mark.parametrize("check_mode", [False, True])
def test_changed_settings_update_the_matched_number_instead_of_requesting_another(check_mode):
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False, OptOutListName="list-1")
    module = FakeModule(
        phone_number_params(
            deletion_protection_enabled=False,
            opt_out_list_name="arn:aws:sms-voice:us-east-1:1:opt-out-list/list-1",
        ),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "query_list", return_value=[existing_number()]),
        patch.object(plugin, "require_client_methods") as require_methods,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    assert result.value.values["phone_number"]["deletion_protection_enabled"] is False
    assert result.value.values["phone_number"]["opt_out_list_name"] == "list-1"
    client.request_phone_number.assert_not_called()
    if check_mode:
        client.update_phone_number.assert_not_called()
    else:
        client.update_phone_number.assert_called_once_with(
            PhoneNumberId="phone-1",
            DeletionProtectionEnabled=False,
            OptOutListName="arn:aws:sms-voice:us-east-1:1:opt-out-list/list-1",
            aws_retry=True,
        )
        assert require_methods.call_args.args[3] == {
            "update_phone_number": ("PhoneNumberId", "DeletionProtectionEnabled", "OptOutListName")
        }


def test_omitted_settings_leave_the_matched_number_unchanged():
    client = Mock()
    module = FakeModule(phone_number_params())
    with (
        patch.object(plugin, "query_list", return_value=[existing_number()]),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is False
    client.update_phone_number.assert_not_called()
    client.request_phone_number.assert_not_called()


def test_new_number_request_omits_unset_settings():
    client = Mock()
    client.request_phone_number.return_value = existing_number(DeletionProtectionEnabled=False, Status="PENDING")
    module = FakeModule(phone_number_params())
    with (
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    request = client.request_phone_number.call_args.kwargs
    assert "DeletionProtectionEnabled" not in request
    assert "InternationalSendingEnabled" not in request
    assert "OptOutListName" not in request


REGISTRATION_ARN = "arn:aws:sms-voice:us-east-1:111111111111:registration/registration-1"


@pytest.mark.parametrize("phone_number_id", [None, "phone-1"])
def test_registration_arn_matches_a_number_with_the_registration_id(phone_number_id):
    client = Mock()
    module = FakeModule(phone_number_params(phone_number_id=phone_number_id, registration_id=REGISTRATION_ARN))
    number = existing_number(RegistrationId="registration-1")
    with (
        patch.object(plugin, "query_list", return_value=[number]),
        patch.object(plugin, "get_phone_number", return_value=number),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is False
    assert result.value.values["phone_number"]["phone_number_id"] == "phone-1"
    client.request_phone_number.assert_not_called()


def test_registration_arn_mismatch_requests_a_number_with_the_given_value():
    client = Mock()
    client.request_phone_number.return_value = existing_number(PhoneNumberId="phone-2", Status="PENDING")
    module = FakeModule(phone_number_params(registration_id=REGISTRATION_ARN))
    with (
        patch.object(plugin, "query_list", return_value=[existing_number(RegistrationId="registration-2")]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    client.request_phone_number.assert_called_once()
    assert client.request_phone_number.call_args.kwargs["RegistrationId"] == REGISTRATION_ARN


def test_absent_waits_for_disassociation_before_release():
    client = Mock()
    client.release_phone_number.return_value = {"PhoneNumberId": "phone-1", "Status": "DELETED"}
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    events = Mock()
    events.attach_mock(client.disassociate_origination_identity, "disassociate")
    events.attach_mock(client.release_phone_number, "release")
    events.wait.return_value = {"PhoneNumberId": "phone-1", "Status": "ACTIVE"}

    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value={"PhoneNumberId": "phone-1", "PoolId": "pool-1", "Status": "ACTIVE"},
        ),
        patch.object(plugin, "wait_for_phone_number_active", events.wait),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert [name for name, args, kwargs in events.mock_calls] == ["disassociate", "wait", "release"]
    client.update_phone_number.assert_not_called()
    assert raised.value.values["changed"]


def test_absent_stops_when_number_disappears_after_disassociation():
    client = Mock()
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})

    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value={"PhoneNumberId": "phone-1", "PoolId": "pool-1", "Status": "ACTIVE"},
        ),
        patch.object(plugin, "wait_for_phone_number_active", return_value={}),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
    assert "phone_number" not in raised.value.values
    client.release_phone_number.assert_not_called()


@pytest.mark.parametrize("waited", [{}, {"PhoneNumberId": "phone-1", "Status": "DELETED"}])
def test_absent_stops_when_wait_observes_external_deletion(waited):
    client = Mock()
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})

    with (
        patch.object(
            plugin,
            "get_phone_number",
            return_value={
                "DeletionProtectionEnabled": True,
                "PhoneNumberId": "phone-1",
                "PoolId": "pool-1",
                "Status": "PENDING",
            },
        ),
        patch.object(plugin, "wait_for_phone_number_active", return_value=waited),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert "phone_number" not in raised.value.values
    require.assert_not_called()
    client.disassociate_origination_identity.assert_not_called()
    client.update_phone_number.assert_not_called()
    client.release_phone_number.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_pooled_number_setting_changes_fail_before_mutation(check_mode):
    client = Mock()
    module = FakeModule(
        phone_number_params(deletion_protection_enabled=False, opt_out_list_name="list-1", tags={"Name": "x"}),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "query_list", return_value=[existing_number(PoolId="pool-1")]),
        patch.object(plugin, "phone_number_tags", return_value={"Name": "x"}),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    message = "Unable to update deletion_protection_enabled, opt_out_list_name for Pinpoint SMS Voice V2 phone number phone-1 in pool pool-1"
    assert raised.value.values["msg"] == message
    client.update_phone_number.assert_not_called()
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


def test_pooled_number_without_setting_changes_is_unchanged():
    client = Mock()
    module = FakeModule(phone_number_params(deletion_protection_enabled=True))
    with (
        patch.object(plugin, "query_list", return_value=[existing_number(PoolId="pool-1")]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.update_phone_number.assert_not_called()


def test_missing_explicit_number_reports_the_module_message():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribePhoneNumbers",
    )
    client = Mock()
    module = FakeModule(phone_number_params(phone_number_id="phone-missing"))
    with (
        patch.object(plugin, "paginated_query_with_retries", side_effect=missing) as query,
        patch.object(plugin, "query_list") as query_list,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == (
        "The specified phone number was not found or does not match the requested attributes"
    )
    assert query.call_args.kwargs == {"PhoneNumberIds": ["phone-missing"]}
    query_list.assert_not_called()
    client.request_phone_number.assert_not_called()


@pytest.mark.parametrize("status", ["ACTIVE", "PENDING"])
def test_tag_matched_number_lists_tags_once(status):
    client = Mock()
    module = FakeModule(
        phone_number_params(
            tags={"Name": "x"},
            wait=True,
            wait_delay=1,
            wait_timeout=10,
        )
    )
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[existing_number(PhoneNumberArn="arn:phone-1", Status=status)],
        ),
        patch.object(
            plugin,
            "get_phone_number",
            return_value=existing_number(PhoneNumberArn="arn:phone-1"),
        ),
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(plugin, "phone_number_tags", return_value={"Name": "x"}) as list_tags,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    list_tags.assert_called_once()
    assert raised.value.values["changed"] is False
    assert raised.value.values["phone_number"]["tags"] == {"Name": "x"}


def client_error(operation):
    return plugin.ClientError({"Error": {"Code": "InternalServerException", "Message": "failed"}}, operation)


@pytest.mark.parametrize(("deletion_protection_enabled", "changed"), [(False, True), (None, False)])
def test_tag_failure_reports_whether_the_number_was_updated(deletion_protection_enabled, changed):
    number = existing_number(PhoneNumberArn="arn:phone")
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False)
    client.tag_resource.side_effect = client_error("TagResource")
    module = FakeModule(
        phone_number_params(
            deletion_protection_enabled=deletion_protection_enabled,
            phone_number_id="phone-1",
            tags={"Env": "test"},
        )
    )
    with (
        patch.object(plugin, "get_phone_number", return_value=number),
        patch.object(plugin, "phone_number_tags", return_value={}),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Unable to tag phone number arn:phone"
    assert raised.value.values["changed"] is changed
    assert client.update_phone_number.called is changed


def test_unsupported_tagging_fails_before_updating_settings():
    client = Mock()

    def require(module, client, service, methods, changed=False):
        if "tag_resource" in methods:
            module.fail_json(changed=changed, msg="Unsupported tagging")

    module = FakeModule(
        phone_number_params(deletion_protection_enabled=False, phone_number_id="phone-1", tags={"Env": "test"})
    )
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PhoneNumberArn="arn:phone")),
        patch.object(plugin, "phone_number_tags", return_value={}),
        patch.object(plugin, "require_client_methods", side_effect=require),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.update_phone_number.assert_not_called()


def test_wait_timeout_after_request_reports_changed():
    client = Mock()
    client.request_phone_number.return_value = existing_number(Status="PENDING")
    module = FakeModule(phone_number_params(wait=True, wait_delay=1, wait_timeout=1))
    with (
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_phone_number", return_value=existing_number(Status="PENDING")),
        patch.object(plugin.time, "sleep"),
        patch.object(plugin.time, "monotonic", side_effect=[0, 0, 0, 2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"].startswith(
        "Timed out waiting for AWS End User Messaging SMS phone number phone-1"
    )


@pytest.mark.parametrize(("pool_id", "changed"), [("pool-1", True), (None, False)])
def test_release_failure_reports_whether_the_number_was_disassociated(pool_id, changed):
    client = Mock()
    client.release_phone_number.side_effect = client_error("ReleasePhoneNumber")
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(
            plugin, "get_phone_number", return_value=existing_number(DeletionProtectionEnabled=False, PoolId=pool_id)
        ),
        patch.object(
            plugin, "wait_for_phone_number_active", return_value=existing_number(DeletionProtectionEnabled=False)
        ),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is changed
    assert client.disassociate_origination_identity.called is changed


def test_unsupported_release_fails_before_disassociating():
    client = Mock()

    def require(module, client, service, methods, changed=False):
        if "release_phone_number" in methods:
            module.fail_json(changed=changed, msg="Unsupported release")

    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PoolId="pool-1")),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods", side_effect=require),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    client.disassociate_origination_identity.assert_not_called()


def named_tags(phone_number):
    return {
        "arn:phone-1": {"Name": "sms", "Env": "old"},
        "arn:phone-2": {"Name": "other"},
    }[phone_number["PhoneNumberArn"]]


@pytest.mark.parametrize(
    ("tags", "purge_tags", "tags_to_set", "tag_keys_to_unset"),
    [
        ({"Name": "sms", "Env": "new"}, True, {"Env": "new"}, []),
        ({"Name": "sms", "Env": "old", "Team": "ops"}, True, {"Team": "ops"}, []),
        ({"Name": "sms"}, True, {}, ["Env"]),
        ({"Name": "sms", "Team": "ops"}, False, {"Team": "ops"}, []),
    ],
)
def test_name_matched_number_converges_tags_instead_of_requesting(tags, purge_tags, tags_to_set, tag_keys_to_unset):
    client = Mock()
    module = FakeModule(phone_number_params(purge_tags=purge_tags, tags=tags))
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[
                existing_number(PhoneNumberArn="arn:phone-2", PhoneNumberId="phone-2"),
                existing_number(PhoneNumberArn="arn:phone-1"),
            ],
        ),
        patch.object(
            plugin, "phone_number_tags", side_effect=lambda client, module, number, **kwargs: named_tags(number)
        ),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "reconcile_arn_tags") as reconcile,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    expected = dict(named_tags({"PhoneNumberArn": "arn:phone-1"}), **tags_to_set)
    for key in tag_keys_to_unset:
        expected.pop(key)

    assert raised.value.values["changed"] is True
    assert raised.value.values["phone_number_id"] == "phone-1"
    assert raised.value.values["phone_number"]["tags"] == expected
    reconcile.assert_called_once_with(
        module, client, "arn:phone-1", tags_to_set, tag_keys_to_unset, "phone number", changed=False
    )
    client.request_phone_number.assert_not_called()


def test_number_without_the_requested_name_is_not_adopted():
    client = model_client()
    module = FakeModule(phone_number_params(tags={"Name": "missing"}), check_mode=True)
    with (
        patch.object(plugin, "query_list", return_value=[existing_number(PhoneNumberArn="arn:phone-1")]),
        patch.object(
            plugin, "phone_number_tags", side_effect=lambda client, module, number, **kwargs: named_tags(number)
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert "phone_number_id" not in raised.value.values
    assert raised.value.values["phone_number"]["tags"] == {"Name": "missing"}


def test_ambiguous_name_match_fails_before_mutation():
    client = Mock()
    module = FakeModule(phone_number_params(tags={"Name": "sms", "Env": "new"}))
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[
                existing_number(PhoneNumberArn="arn:phone-2", PhoneNumberId="phone-2"),
                existing_number(PhoneNumberArn="arn:phone-1"),
            ],
        ),
        patch.object(plugin, "phone_number_tags", return_value={"Name": "sms"}),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == (
        "Multiple Pinpoint SMS Voice V2 phone numbers matched name sms: phone-1, phone-2"
    )
    assert not raised.value.values.get("changed")
    client.request_phone_number.assert_not_called()
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


def test_tags_without_name_adopt_the_only_fixed_attribute_match():
    client = Mock()
    module = FakeModule(phone_number_params(tags={"Env": "new"}), check_mode=True)
    with (
        patch.object(plugin, "query_list", return_value=[existing_number(PhoneNumberArn="arn:phone-1")]),
        patch.object(
            plugin, "phone_number_tags", side_effect=lambda client, module, number, **kwargs: named_tags(number)
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["phone_number_id"] == "phone-1"
    assert raised.value.values["phone_number"]["tags"] == {"Env": "new"}
    client.request_phone_number.assert_not_called()


def test_tags_without_name_fail_when_several_numbers_match():
    client = Mock()
    module = FakeModule(phone_number_params(tags={"Env": "new"}))
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[
                existing_number(PhoneNumberArn="arn:phone-1"),
                existing_number(PhoneNumberArn="arn:phone-2", PhoneNumberId="phone-2"),
            ],
        ),
        patch.object(
            plugin, "phone_number_tags", side_effect=lambda client, module, number, **kwargs: named_tags(number)
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"].startswith("Multiple Pinpoint SMS Voice V2 phone numbers matched the requested")
    assert raised.value.values["msg"].endswith("phone-1, phone-2")
    assert client.mock_calls == []


def test_check_mode_projects_the_opt_out_list_name_from_an_arn():
    client = Mock()
    module = FakeModule(
        phone_number_params(opt_out_list_name="arn:aws:sms-voice:us-east-1:1:opt-out-list/list-1"),
        check_mode=True,
    )
    with (
        patch.object(plugin, "query_list", return_value=[existing_number()]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["phone_number"]["opt_out_list_name"] == "list-1"
    client.update_phone_number.assert_not_called()


@pytest.mark.parametrize("status", ["ASSOCIATING", "DISASSOCIATING", "PENDING"])
def test_changes_wait_for_an_active_number_even_without_wait(status):
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False)
    module = FakeModule(phone_number_params(deletion_protection_enabled=False, tags={"Name": "sms"}))
    events = Mock()
    events.attach_mock(client.update_phone_number, "update")
    events.attach_mock(client.tag_resource, "tag")
    events.wait.return_value = existing_number(PhoneNumberArn="arn:phone-1", Tags=[{"Key": "Name", "Value": "sms"}])
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[existing_number(PhoneNumberArn="arn:phone-1", Status=status)],
        ),
        patch.object(plugin, "phone_number_tags", return_value={"Name": "sms"}),
        patch.object(plugin, "wait_for_phone_number_active", events.wait),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert [name for name, args, kwargs in events.mock_calls] == ["wait", "update"]
    assert raised.value.values["changed"] is True


def test_number_given_by_arn_is_waited_on_and_updated_by_that_arn():
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False)
    module = FakeModule(phone_number_params(deletion_protection_enabled=False, phone_number_id=PHONE_NUMBER_ARN))
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(Status="PENDING")),
        patch.object(plugin, "wait_for_phone_number_active", return_value=existing_number()) as wait,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait.assert_called_once_with(client, module, PHONE_NUMBER_ARN, tags=None)
    client.update_phone_number.assert_called_once_with(
        PhoneNumberId=PHONE_NUMBER_ARN,
        DeletionProtectionEnabled=False,
        aws_retry=True,
    )
    assert raised.value.values["changed"] is True
    assert raised.value.values["phone_number"]["deletion_protection_enabled"] is False


def test_unchanged_number_does_not_wait_without_wait():
    client = Mock()
    module = FakeModule(phone_number_params(tags={"Name": "sms"}))
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[existing_number(PhoneNumberArn="arn:phone-1", Status="PENDING")],
        ),
        patch.object(plugin, "phone_number_tags", return_value={"Name": "sms"}),
        patch.object(plugin, "wait_for_phone_number_active") as wait_for_active,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    wait_for_active.assert_not_called()


def test_present_validates_wait_bounds_without_wait():
    module = FakeModule(phone_number_params(wait_delay=0, wait_timeout=300))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "wait_delay must be 1 or greater"


@pytest.mark.parametrize("changed", [False, True])
def test_phone_number_tags_reports_malformed_tags_with_changed(changed):
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Name"}]}
    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.phone_number_tags(client, FakeModule({}), {"PhoneNumberArn": "arn:phone-1"}, changed=changed)

    assert (
        raised.value.values["msg"] == "AWS returned malformed tags for Pinpoint SMS Voice V2 phone number arn:phone-1"
    )
    assert raised.value.values["changed"] is changed


def pool_listing(*originations):
    return {"OriginationIdentities": list(originations)}


LAST_PHONE_NUMBER_POOL = pool_listing(
    {
        "OriginationIdentity": "phone-1",
        "OriginationIdentityArn": "arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-1",
    },
    {
        "OriginationIdentity": "sender-1",
        "OriginationIdentityArn": "arn:aws:sms-voice:us-east-1:123456789012:sender-id/sender-1/US",
    },
)


def pool_query(pool_listing_result, pools_result):
    def query(client, method, **kwargs):
        if method == "list_pool_origination_identities":
            assert kwargs == {"PoolId": "pool-1"}
            return pool_listing_result

        assert method == "describe_pools"
        assert kwargs == {"PoolIds": ["pool-1"]}
        return pools_result

    return query


@pytest.mark.parametrize("check_mode", [False, True])
def test_absent_fails_without_mutation_for_last_phone_number_in_pool(check_mode):
    client = Mock()
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None}, check_mode=check_mode)
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PoolId="pool-1")),
        patch.object(plugin, "paginated_query_with_retries", side_effect=pool_query(LAST_PHONE_NUMBER_POOL, None)),
        patch.object(
            pinpoint_sms_voice,
            "paginated_query_with_retries",
            side_effect=pool_query(None, {"Pools": [{"PoolId": "pool-1", "Status": "ACTIVE"}]}),
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert "pool-1" in raised.value.values["msg"]
    assert "linuxhq.aws.pinpoint_sms_voice_phone_pool" in raised.value.values["msg"]
    client.disassociate_origination_identity.assert_not_called()
    client.update_phone_number.assert_not_called()
    client.release_phone_number.assert_not_called()
    client.delete_pool.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_absent_proceeds_when_other_phone_numbers_remain_in_pool(check_mode):
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False)
    client.release_phone_number.return_value = {"PhoneNumberId": "phone-1", "Status": "DELETED"}
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None}, check_mode=check_mode)
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PoolId="pool-1")),
        patch.object(plugin, "wait_for_phone_number_active", return_value=existing_number()),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=pool_query(pool_with_other_phone_number(), None),
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is True
    assert client.disassociate_origination_identity.called is not check_mode
    assert client.release_phone_number.called is not check_mode


@pytest.mark.parametrize(
    "pools_result",
    [{"Pools": [{"PoolId": "pool-1", "Status": "DELETING"}]}, {"Pools": []}],
    ids=["deleting", "gone"],
)
def test_absent_releases_last_phone_number_of_a_pool_being_deleted(pools_result):
    client = Mock()
    client.release_phone_number.return_value = {"PhoneNumberId": "phone-1", "Status": "DELETED"}
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(
            plugin, "get_phone_number", return_value=existing_number(DeletionProtectionEnabled=False, PoolId="pool-1")
        ),
        patch.object(
            plugin, "wait_for_phone_number_active", return_value=existing_number(DeletionProtectionEnabled=False)
        ),
        patch.object(plugin, "paginated_query_with_retries", side_effect=pool_query(LAST_PHONE_NUMBER_POOL, None)),
        patch.object(pinpoint_sms_voice, "paginated_query_with_retries", side_effect=pool_query(None, pools_result)),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is True
    client.release_phone_number.assert_called_once_with(PhoneNumberId="phone-1", aws_retry=True)


def test_absent_maps_last_phone_number_conflict_to_clear_failure():
    client = Mock()
    client.disassociate_origination_identity.side_effect = plugin.ClientError(
        {
            "Error": {"Code": "ConflictException", "Message": "conflict"},
            "Reason": "LAST_PHONE_NUMBER",
            "ResourceId": "pool-1",
        },
        "DisassociateOriginationIdentity",
    )
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PoolId="pool-1")),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert raised.value.values["msg"] == plugin.last_phone_number_message("phone-1", "pool-1")
    client.release_phone_number.assert_not_called()


def test_absent_reports_other_disassociate_conflicts_from_aws():
    client = Mock()
    client.disassociate_origination_identity.side_effect = plugin.ClientError(
        {"Error": {"Code": "ConflictException", "Message": "conflict"}, "Reason": "RESOURCE_NOT_ACTIVE"},
        "DisassociateOriginationIdentity",
    )
    module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})
    with (
        patch.object(plugin, "get_phone_number", return_value=existing_number(PoolId="pool-1")),
        patch.object(plugin, "paginated_query_with_retries", return_value=pool_with_other_phone_number()),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["msg"] == (
        "Unable to disassociate Pinpoint SMS Voice V2 phone number phone-1 from pool pool-1"
    )
    client.release_phone_number.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_new_number_with_arns_returns_ids_and_names_in_every_mode(check_mode):
    client = model_client()
    client.request_phone_number.return_value = existing_number(
        OptOutListName="list-1",
        PoolId="pool-1",
        RegistrationId="registration-1",
        Status="PENDING",
    )
    module = FakeModule(
        phone_number_params(
            opt_out_list_name="arn:aws:sms-voice:us-east-1:111111111111:opt-out-list/list-1",
            pool_id="arn:aws:sms-voice:us-east-1:111111111111:pool/pool-1",
            registration_id=REGISTRATION_ARN,
        ),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    phone_number = result.value.values["phone_number"]
    assert result.value.values["changed"] is True
    assert phone_number["opt_out_list_name"] == "list-1"
    assert phone_number["pool_id"] == "pool-1"
    assert phone_number["registration_id"] == "registration-1"
    if check_mode:
        client.request_phone_number.assert_not_called()
    else:
        assert client.request_phone_number.call_args.kwargs["PoolId"] == (
            "arn:aws:sms-voice:us-east-1:111111111111:pool/pool-1"
        )


@pytest.mark.parametrize("check_mode", [False, True])
def test_resulting_tag_limit_fails_before_updating_settings(check_mode):
    client = Mock()
    existing_tags = {f"old{index}": "" for index in range(200)}
    existing_tags["aws:reserved"] = ""
    module = FakeModule(
        phone_number_params(deletion_protection_enabled=False, purge_tags=False, tags={"Env": "test"}),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "query_list", return_value=[existing_number(PhoneNumberArn=PHONE_NUMBER_ARN)]),
        patch.object(plugin, "phone_number_tags", return_value=existing_tags),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == (
        "The resulting Pinpoint SMS Voice V2 phone number tags must contain at most 200 entries"
    )
    assert raised.value.values.get("changed", False) is False
    client.update_phone_number.assert_not_called()
    client.tag_resource.assert_not_called()


def settled_number(client, module, phone_number_id, tags=None, changed=False):
    """Stand in for wait_for_phone_number_active: the number becomes ACTIVE, with the tags it was given."""
    number = existing_number(PhoneNumberArn=PHONE_NUMBER_ARN)
    if tags is not None:
        number["Tags"] = tags

    return number


def run_present_on_transitional_number(check_mode, status, **overrides):
    client = Mock()
    client.update_phone_number.return_value = existing_number(DeletionProtectionEnabled=False)
    module = FakeModule(phone_number_params(wait_delay=1, wait_timeout=1, **overrides), check_mode=check_mode)
    with (
        patch.object(
            plugin, "query_list", return_value=[existing_number(PhoneNumberArn=PHONE_NUMBER_ARN, Status=status)]
        ),
        patch.object(plugin, "phone_number_tags", return_value={"Name": "sms"}),
        patch.object(plugin, "wait_for_phone_number_active", side_effect=settled_number) as wait,
        patch.object(plugin, "reconcile_arn_tags"),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    return raised.value.values, wait.called


@pytest.mark.parametrize("status", ["ASSOCIATING", "DISASSOCIATING", "PENDING"])
@pytest.mark.parametrize(
    "overrides",
    [
        {"wait": True},
        {"deletion_protection_enabled": False, "wait": False},
        {"tags": {"Env": "test", "Name": "sms"}, "wait": False},
        {"deletion_protection_enabled": False, "tags": {"Env": "test", "Name": "sms"}, "wait": True},
    ],
    ids=["unchanged-wait", "update-no-wait", "tags-no-wait", "update-tags-wait"],
)
def test_check_mode_predicts_the_active_number_a_real_run_waits_for(status, overrides):
    real, real_waited = run_present_on_transitional_number(False, status, **overrides)
    check, check_waited = run_present_on_transitional_number(True, status, **overrides)

    assert real_waited is True
    assert check_waited is False
    assert real["phone_number"]["status"] == "ACTIVE"
    assert check == real


def test_unchanged_transitional_number_without_wait_keeps_the_observed_status():
    # Without a change, wait=false does not wait, so both modes return the observed status.
    for check_mode in (False, True):
        result, waited = run_present_on_transitional_number(check_mode, "PENDING")
        assert waited is False
        assert result["changed"] is False
        assert result["phone_number"]["status"] == "PENDING"


DESCRIBED_NUMBER = {
    "CreatedTimestamp": "2026-10-27T12:16:28-07:00",
    "DeletionProtectionEnabled": False,
    "InternationalSendingEnabled": False,
    "IsoCountryCode": "US",
    "MessageType": "TRANSACTIONAL",
    "MessagingLimits": {"RateLimits": {"SMS": 1}},
    "MonthlyLeasingPrice": "1.00",
    "NumberCapabilities": ["SMS"],
    "NumberType": "SIMULATOR",
    "OptOutListName": "Default",
    "PhoneNumber": "+19015550195",
    "PhoneNumberArn": PHONE_NUMBER_ARN,
    "PhoneNumberId": "phone-1",
    "SelfManagedOptOutsEnabled": False,
    "Status": "ACTIVE",
    "TwoWayEnabled": False,
}
# Live, ReleasePhoneNumber returns DELETED without these DescribePhoneNumbers fields, and its model has no PoolId.
RELEASED_NUMBER = dict(
    {
        key: value
        for key, value in DESCRIBED_NUMBER.items()
        if key not in ("DeletionProtectionEnabled", "InternationalSendingEnabled", "MessagingLimits")
    },
    Status="DELETED",
)


@pytest.mark.parametrize("deletion_protection_enabled", [False, True])
@pytest.mark.parametrize("pool_id", [None, "pool-1"], ids=["unpooled", "pooled"])
def test_absent_check_mode_predicts_the_release_response(pool_id, deletion_protection_enabled):
    described = dict(DESCRIBED_NUMBER, DeletionProtectionEnabled=deletion_protection_enabled)
    if pool_id:
        described["PoolId"] = pool_id

    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.update_phone_number.return_value = dict(DESCRIBED_NUMBER)
        client.release_phone_number.return_value = dict(RELEASED_NUMBER)
        module = FakeModule(
            phone_number_params(phone_number_id="phone-1", state="absent", wait_delay=1, wait_timeout=1),
            check_mode=check_mode,
        )
        with (
            patch.object(plugin, "get_phone_number", return_value=dict(described)),
            # Disassociating the number removes only its pool.
            patch.object(
                plugin,
                "wait_for_phone_number_active",
                return_value={key: value for key, value in described.items() if key != "PoolId"},
            ),
            patch.object(
                plugin, "paginated_query_with_retries", side_effect=pool_query(pool_with_other_phone_number(), None)
            ),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        assert client.release_phone_number.called is not check_mode
        assert client.disassociate_origination_identity.called is bool(pool_id and not check_mode)
        assert client.update_phone_number.called is (deletion_protection_enabled and not check_mode)
        results[check_mode] = raised.value.values

    assert results[True] == results[False]
    assert results[True]["phone_number"]["status"] == "DELETED"
    assert "pool_id" not in results[True]["phone_number"]


# Live, RequestPhoneNumber returned these for an untagged SIMULATOR request, without a Tags key. A number requested
# into a pool took the pool's opt-out list, here a non-default one, instead of "Default".
LIVE_REQUESTED_NUMBERS = {
    "unpooled": {
        "CreatedTimestamp": "2026-10-27T15:16:47-07:00",
        "DeletionProtectionEnabled": False,
        "InternationalSendingEnabled": False,
        "IsoCountryCode": "US",
        "MessageType": "TRANSACTIONAL",
        "MonthlyLeasingPrice": "1.00",
        "NumberCapabilities": ["SMS"],
        "NumberType": "SIMULATOR",
        "OptOutListName": "Default",
        "PhoneNumber": "+14255556430",
        "PhoneNumberArn": PHONE_NUMBER_ARN,
        "PhoneNumberId": "phone-1",
        "SelfManagedOptOutsEnabled": False,
        "Status": "PENDING",
        "TwoWayEnabled": False,
    },
}
LIVE_REQUESTED_NUMBERS["pooled"] = dict(LIVE_REQUESTED_NUMBERS["unpooled"], OptOutListName="list-1", PoolId="pool-1")
# AWS assigns these to a new number, so check mode cannot predict them.
ASSIGNED_NUMBER_FIELDS = {
    "created_timestamp",
    "monthly_leasing_price",
    "phone_number",
    "phone_number_arn",
    "phone_number_id",
}
# A number requested into a pool takes these from the pool.
POOL_SHARED_NUMBER_FIELDS = {"opt_out_list_name", "self_managed_opt_outs_enabled", "two_way_enabled"}
# Members that botocore 1.36.10 does not model in RequestPhoneNumberResult or PhoneNumberInformation.
LEGACY_UNMODELED_MEMBERS = ("InternationalSendingEnabled", "MessagingLimits")


def model_members(shape, legacy):
    members = get_session().get_service_model("pinpoint-sms-voice-v2").shape_for(shape).members
    return {member: value for member, value in members.items() if not (legacy and member in LEGACY_UNMODELED_MEMBERS)}


def request_new_number(check_mode, legacy, pool_id, wait):
    """Request an untagged number and return the result; botocore drops the response members its model lacks."""
    client = Mock()
    client.meta.service_model.shape_for.side_effect = lambda shape: Mock(members=model_members(shape, legacy))
    requested = LIVE_REQUESTED_NUMBERS["pooled" if pool_id else "unpooled"]
    response_members = model_members("RequestPhoneNumberResult", legacy)
    client.request_phone_number.return_value = {
        key: value for key, value in requested.items() if key in response_members
    }
    described = dict(requested, MessagingLimits={"RateLimits": {"SMS": 1}}, Status="ACTIVE")
    described_members = model_members("PhoneNumberInformation", legacy)
    module = FakeModule(
        phone_number_params(number_type="SIMULATOR", pool_id=pool_id, wait=wait, wait_delay=1, wait_timeout=1),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "wait_for_phone_number_active",
            return_value={key: value for key, value in described.items() if key in described_members},
        ) as wait_for_active,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert client.request_phone_number.called is not check_mode
    assert wait_for_active.called is (wait and not check_mode)
    if check_mode:
        # The prediction follows the model of the response that the real run returns.
        client.meta.service_model.shape_for.assert_called_once_with(
            "PhoneNumberInformation" if wait else "RequestPhoneNumberResult"
        )

    return raised.value.values["phone_number"]


@pytest.mark.parametrize("legacy", [False, True], ids=["current-botocore", "botocore-1.36"])
@pytest.mark.parametrize("pool_id", [None, "pool-1"], ids=["unpooled", "pooled"])
@pytest.mark.parametrize("wait", [False, True])
def test_check_mode_new_number_predicts_what_a_real_request_returns(wait, pool_id, legacy):
    real = request_new_number(False, legacy, pool_id, wait)
    predicted = request_new_number(True, legacy, pool_id, wait)

    # Every predicted value is the real one, and only values AWS assigns or the pool shares are left out.
    assert {key: real.get(key) for key in predicted} == predicted
    unpredicted = ASSIGNED_NUMBER_FIELDS | (POOL_SHARED_NUMBER_FIELDS if pool_id else set())
    if wait and not legacy:
        unpredicted.add("messaging_limits")

    assert set(real) - set(predicted) == unpredicted
    assert predicted["status"] == ("ACTIVE" if wait else "PENDING")
    assert predicted["deletion_protection_enabled"] is False
    assert ("international_sending_enabled" in predicted) is not legacy
