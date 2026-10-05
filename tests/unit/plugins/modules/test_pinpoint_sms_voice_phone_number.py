from unittest.mock import Mock, call, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_number as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert len(options["required_if"]) == 2


def test_accepts_four_capabilities():
    client = Mock()
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
                "Filters",
                "Owner",
            )
        },
    )
    client.request_phone_number.assert_not_called()


def test_capability_limit_counts_unique_values():
    client = Mock()
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
    client = Mock()
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
        call(client, module, "phone-1"),
        call(client, module, "phone-1"),
    ]
    client.release_phone_number.assert_called_once_with(PhoneNumberId="phone-1", aws_retry=True)
    assert raised.value.values["changed"]


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
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
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

    assert raised.value.values["changed"]
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
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
    assert "phone_number" not in raised.value.values
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
