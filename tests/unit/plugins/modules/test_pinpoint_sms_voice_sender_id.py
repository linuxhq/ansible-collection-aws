from unittest.mock import Mock, call, patch

import pytest
from botocore.session import get_session

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_sender_id as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_documents_shape,
    assert_module_contract,
    documented_returns,
)

ARN = "arn:aws:sms-voice:us-east-1:123456789012:sender-id/EXAMPLE/DE"


def model_client():
    """Return a mock client with the real botocore model, for check-mode predictions that read it.

    The model is loaded without creating a client, so no credential lookup runs.
    """
    client = Mock()
    client.meta.service_model = get_session().get_service_model("pinpoint-sms-voice-v2")
    return client


def params(**overrides):
    values = {
        "deletion_protection_enabled": None,
        "iso_country_code": "DE",
        "message_types": ["TRANSACTIONAL"],
        "purge_tags": True,
        "sender_id": "EXAMPLE",
        "state": "present",
        "tags": None,
    }
    values.update(overrides)
    return values


def described(**overrides):
    sender_id = {
        "DeletionProtectionEnabled": False,
        "IsoCountryCode": "DE",
        "MessageTypes": ["TRANSACTIONAL"],
        "MonthlyLeasingPrice": "0.00",
        "Registered": False,
        "SenderId": "EXAMPLE",
        "SenderIdArn": ARN,
    }
    sender_id.update(overrides)
    return sender_id


def client_error(code, operation, reason=None):
    response = {"Error": {"Code": code, "Message": code}}
    if reason:
        response["Reason"] = reason

    return plugin.ClientError(response, operation)


def run(module, describe=None, tags=None):
    """Run main with DescribeSenderIds answering describe and ListTagsForResource answering tags."""
    if isinstance(describe, Exception):
        query = {"side_effect": describe}
    else:
        query = {"return_value": {"SenderIds": [describe] if describe else []}}

    module._client.list_tags_for_resource.return_value = {"Tags": tags or []}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "paginated_query_with_retries", **query) as paginate,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require, paginate


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["sender_id"]["required"] is True
    assert options["argument_spec"]["iso_country_code"]["required"] is True
    assert "default" not in options["argument_spec"]["deletion_protection_enabled"]
    assert "default" not in options["argument_spec"]["tags"]
    assert options["argument_spec"]["purge_tags"]["default"] is True


def test_message_type_choices_follow_the_sdk_model():
    model = get_session().get_service_model("pinpoint-sms-voice-v2").shape_for("MessageType")
    assert sorted(assert_module_contract(plugin)["argument_spec"]["message_types"]["choices"]) == sorted(model.enum)


@pytest.mark.parametrize(
    "shape_name",
    ["SenderIdInformation", "RequestSenderIdResult", "UpdateSenderIdResult", "ReleaseSenderIdResult"],
)
def test_documented_returns_cover_the_sdk_shape(shape_name):
    assert_documents_shape(documented_returns(plugin)["sender_id"]["contains"], "pinpoint-sms-voice-v2", shape_name)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"sender_id": None}, "sender_id must contain 1 to 11 letters, numbers, hyphens, or underscores"),
        ({"sender_id": "TWELVECHARSX"}, "sender_id must contain 1 to 11 letters, numbers, hyphens, or underscores"),
        ({"sender_id": "BAD ID"}, "sender_id must contain 1 to 11 letters, numbers, hyphens, or underscores"),
        ({"iso_country_code": None}, "iso_country_code must be exactly two uppercase letters"),
        ({"iso_country_code": "de"}, "iso_country_code must be exactly two uppercase letters"),
        ({"message_types": []}, "message_types must not be empty"),
        ({"tags": {"aws:team": "x"}}, "tag keys beginning with aws: are reserved and cannot be set"),
        (
            {"tags": {"Team": "R&D"}},
            "tag keys and values must contain only letters, numbers, spaces, and _ . : / = + - @",
        ),
    ],
)
@pytest.mark.parametrize("check_mode", [False, True])
def test_invalid_input_fails_before_any_aws_call(overrides, message, check_mode):
    module = FakeModule(params(**overrides), check_mode=check_mode, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(module, "client") as connect,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": message}
    connect.assert_not_called()


def test_absent_ignores_present_only_inputs():
    client = model_client()
    module = FakeModule(params(message_types=[], state="absent", tags={"aws:x": "y"}), client=client)
    result, _require, _paginate = run(module, describe=None)

    assert isinstance(result, ModuleExit)
    assert result.values == {"changed": False, "state": "absent"}


@pytest.mark.parametrize("check_mode", [False, True])
def test_create(check_mode):
    client = model_client()
    client.request_sender_id.return_value = dict(
        described(DeletionProtectionEnabled=True, Tags=[{"Key": "Team", "Value": "Ops"}]),
        ResponseMetadata={},
    )
    module = FakeModule(
        params(deletion_protection_enabled=True, tags={"Team": "Ops"}), check_mode=check_mode, client=client
    )
    result, require, paginate = run(module, describe=client_error("ResourceNotFoundException", "DescribeSenderIds"))

    assert paginate.call_args == call(
        client, "describe_sender_ids", SenderIds=[{"IsoCountryCode": "DE", "SenderId": "EXAMPLE"}]
    )
    assert result.values["changed"] is True
    sender_id = result.values["sender_id"]
    assert sender_id["sender_id"] == "EXAMPLE"
    assert sender_id["iso_country_code"] == "DE"
    assert sender_id["message_types"] == ["TRANSACTIONAL"]
    assert sender_id["deletion_protection_enabled"] is True
    assert sender_id["tags"] == {"Team": "Ops"}
    request = {
        "DeletionProtectionEnabled": True,
        "IsoCountryCode": "DE",
        "MessageTypes": ["TRANSACTIONAL"],
        "SenderId": "EXAMPLE",
        "Tags": [{"Key": "Team", "Value": "Ops"}],
    }
    if check_mode:
        client.request_sender_id.assert_not_called()
        assert "sender_id_arn" not in sender_id
    else:
        client.request_sender_id.assert_called_once_with(**request, aws_retry=True)
        assert require.call_args == call(module, client, "Pinpoint SMS Voice V2", {"request_sender_id": tuple(request)})
        assert sender_id["sender_id_arn"] == ARN


@pytest.mark.parametrize("check_mode", [False, True])
def test_create_omits_unset_options(check_mode):
    client = model_client()
    client.request_sender_id.return_value = described(MessageTypes=["PROMOTIONAL", "TRANSACTIONAL"])
    module = FakeModule(params(message_types=None, tags={}), check_mode=check_mode, client=client)
    result, _require, _paginate = run(module, describe=None)

    assert result.values["changed"] is True
    # AWS disables deletion protection when the request omits it, and an empty tags option sends no tags.
    assert result.values["sender_id"]["deletion_protection_enabled"] is False
    assert result.values["sender_id"]["tags"] == {}
    if not check_mode:
        client.request_sender_id.assert_called_once_with(IsoCountryCode="DE", SenderId="EXAMPLE", aws_retry=True)


def test_create_passes_aws_errors_through():
    # Countries that require registration are rejected by AWS, which the module reports.
    client = model_client()
    client.request_sender_id.side_effect = client_error("ValidationException", "RequestSenderId")
    module = FakeModule(params(iso_country_code="US"), client=client)
    result, _require, _paginate = run(module, describe=None)

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "Unable to request Pinpoint SMS Voice V2 sender ID EXAMPLE in US"


def test_create_rejects_malformed_response():
    client = model_client()
    client.request_sender_id.return_value = {"SenderId": "EXAMPLE"}
    module = FakeModule(params(), client=client)
    result, _require, _paginate = run(module, describe=None)

    assert isinstance(result, ModuleFail)
    assert result.values == {
        "changed": True,
        "msg": "AWS returned a malformed Pinpoint SMS Voice V2 sender ID while requesting it",
    }


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("message_types", [["TRANSACTIONAL"], None])
def test_existing_sender_id_is_unchanged(check_mode, message_types):
    client = model_client()
    module = FakeModule(
        params(deletion_protection_enabled=False, message_types=message_types, tags={"Team": "Ops"}),
        check_mode=check_mode,
        client=client,
    )
    result, _require, _paginate = run(module, describe=described(), tags=[{"Key": "Team", "Value": "Ops"}])

    assert result.values["changed"] is False
    assert result.values["sender_id"]["tags"] == {"Team": "Ops"}
    assert result.values["sender_id"]["sender_id_arn"] == ARN
    client.request_sender_id.assert_not_called()
    client.update_sender_id.assert_not_called()
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


def test_existing_sender_id_ignores_omitted_options():
    client = model_client()
    module = FakeModule(params(deletion_protection_enabled=None, message_types=None, tags=None), client=client)
    result, _require, _paginate = run(
        module, describe=described(DeletionProtectionEnabled=True), tags=[{"Key": "Keep", "Value": "me"}]
    )

    assert result.values["changed"] is False
    assert result.values["sender_id"]["deletion_protection_enabled"] is True
    assert result.values["sender_id"]["tags"] == {"Keep": "me"}
    client.update_sender_id.assert_not_called()
    client.untag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_deletion_protection_change(check_mode):
    client = model_client()
    client.update_sender_id.return_value = dict(described(DeletionProtectionEnabled=True), ResponseMetadata={})
    module = FakeModule(params(deletion_protection_enabled=True), check_mode=check_mode, client=client)
    result, require, _paginate = run(module, describe=described(MessagingLimits={"RateLimits": {"SMS": 1}}))

    assert result.values["changed"] is True
    assert result.values["sender_id"]["deletion_protection_enabled"] is True
    # UpdateSenderId omits fields DescribeSenderIds returns, which are kept.
    assert result.values["sender_id"]["messaging_limits"] == {"rate_limits": {"sms": 1}}
    if check_mode:
        client.update_sender_id.assert_not_called()
    else:
        client.update_sender_id.assert_called_once_with(
            SenderId="EXAMPLE", IsoCountryCode="DE", DeletionProtectionEnabled=True, aws_retry=True
        )
        assert (
            call(
                module,
                client,
                "Pinpoint SMS Voice V2",
                {"update_sender_id": ("DeletionProtectionEnabled", "IsoCountryCode", "SenderId")},
            )
            in require.call_args_list
        )


def test_deletion_protection_update_error_reports_no_change():
    client = model_client()
    client.update_sender_id.side_effect = client_error("AccessDeniedException", "UpdateSenderId")
    module = FakeModule(params(deletion_protection_enabled=True), client=client)
    result, _require, _paginate = run(module, describe=described())

    assert isinstance(result, ModuleFail)
    assert result.values == {"msg": "Unable to update Pinpoint SMS Voice V2 sender ID EXAMPLE in DE"}


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("purge_tags", "expected", "unset"),
    [(True, {"Team": "Dev", "New": "1"}, ["Old"]), (False, {"Team": "Dev", "New": "1", "Old": "x"}, [])],
)
def test_tag_changes(check_mode, purge_tags, expected, unset):
    client = model_client()
    module = FakeModule(
        params(purge_tags=purge_tags, tags={"Team": "Dev", "New": "1"}), check_mode=check_mode, client=client
    )
    result, _require, _paginate = run(
        module,
        describe=described(),
        tags=[{"Key": "Team", "Value": "Ops"}, {"Key": "Old", "Value": "x"}],
    )

    assert result.values["changed"] is True
    assert result.values["sender_id"]["tags"] == expected
    if check_mode:
        client.tag_resource.assert_not_called()
        client.untag_resource.assert_not_called()
        return

    client.tag_resource.assert_called_once()
    assert client.tag_resource.call_args.kwargs["ResourceArn"] == ARN
    assert sorted(client.tag_resource.call_args.kwargs["Tags"], key=lambda tag: tag["Key"]) == [
        {"Key": "New", "Value": "1"},
        {"Key": "Team", "Value": "Dev"},
    ]
    if unset:
        client.untag_resource.assert_called_once_with(ResourceArn=ARN, TagKeys=unset, aws_retry=True)
    else:
        client.untag_resource.assert_not_called()


def test_empty_tags_purge_existing_tags():
    client = model_client()
    module = FakeModule(params(tags={}), client=client)
    result, _require, _paginate = run(module, describe=described(), tags=[{"Key": "Old", "Value": "x"}])

    assert result.values["changed"] is True
    assert result.values["sender_id"]["tags"] == {}
    client.untag_resource.assert_called_once_with(ResourceArn=ARN, TagKeys=["Old"], aws_retry=True)


def test_tag_error_after_update_reports_change():
    client = model_client()
    client.update_sender_id.return_value = described(DeletionProtectionEnabled=True)
    client.tag_resource.side_effect = client_error("AccessDeniedException", "TagResource")
    module = FakeModule(params(deletion_protection_enabled=True, tags={"Team": "Dev"}), client=client)
    result, _require, _paginate = run(module, describe=described())

    assert isinstance(result, ModuleFail)
    assert result.values == {"changed": True, "msg": f"Unable to tag Pinpoint SMS Voice V2 sender ID {ARN}"}


def test_tag_limit_counts_existing_tags():
    client = model_client()
    module = FakeModule(params(purge_tags=False, tags={"New": "1"}), client=client)
    existing = [{"Key": f"k{index}", "Value": "v"} for index in range(200)]
    result, _require, _paginate = run(module, describe=described(), tags=existing)

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "The resulting Pinpoint SMS Voice V2 sender ID tags must contain at most 200 entries"
    client.tag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("existing", "requested", "message"),
    [
        (
            ["TRANSACTIONAL"],
            ["PROMOTIONAL"],
            "from TRANSACTIONAL to PROMOTIONAL",
        ),
        (
            ["TRANSACTIONAL"],
            ["TRANSACTIONAL", "PROMOTIONAL"],
            "from TRANSACTIONAL to PROMOTIONAL, TRANSACTIONAL",
        ),
    ],
)
def test_message_type_mismatch_fails_without_changes(check_mode, existing, requested, message):
    client = model_client()
    module = FakeModule(
        params(deletion_protection_enabled=True, message_types=requested, tags={"New": "1"}),
        check_mode=check_mode,
        client=client,
    )
    result, _require, _paginate = run(module, describe=described(MessageTypes=existing))

    assert isinstance(result, ModuleFail)
    assert result.values == {
        "msg": (
            f"Unable to change the message types of Pinpoint SMS Voice V2 sender ID EXAMPLE in DE {message}; "
            "AWS does not allow message types to change, so release the sender ID and request it again"
        )
    }
    client.update_sender_id.assert_not_called()
    client.tag_resource.assert_not_called()


def test_message_type_order_and_repeats_are_ignored():
    client = model_client()
    module = FakeModule(params(message_types=["TRANSACTIONAL", "PROMOTIONAL", "TRANSACTIONAL"]), client=client)
    result, _require, _paginate = run(module, describe=described(MessageTypes=["PROMOTIONAL", "TRANSACTIONAL"]))

    assert result.values["changed"] is False


@pytest.mark.parametrize("check_mode", [False, True])
def test_message_types_described_in_title_case_match(check_mode):
    # Live: DescribeSenderIds returns Transactional for a sender ID requested with TRANSACTIONAL.
    client = model_client()
    module = FakeModule(params(), check_mode=check_mode, client=client)
    result, _require, _paginate = run(module, describe=described(MessageTypes=["Transactional"]))

    assert result.values["changed"] is False
    # Values are returned as AWS gives them.
    assert result.values["sender_id"]["message_types"] == ["Transactional"]


def test_title_case_message_type_mismatch_fails():
    module = FakeModule(params(message_types=["PROMOTIONAL"]), client=model_client())
    result, _require, _paginate = run(module, describe=described(MessageTypes=["Transactional"]))

    assert isinstance(result, ModuleFail)
    assert "from TRANSACTIONAL to PROMOTIONAL" in result.values["msg"]


@pytest.mark.parametrize("check_mode", [False, True])
def test_release(check_mode):
    client = model_client()
    client.release_sender_id.return_value = dict(
        described(),
        ResponseMetadata={},
    )
    module = FakeModule(params(state="absent"), check_mode=check_mode, client=client)
    result, _require, _paginate = run(module, describe=described(MessagingLimits={"RateLimits": {"SMS": 1}}))

    assert result.values["changed"] is True
    assert result.values["sender_id"]["sender_id"] == "EXAMPLE"
    assert result.values["sender_id"]["sender_id_arn"] == ARN
    if check_mode:
        client.release_sender_id.assert_not_called()
        # Only the members ReleaseSenderId returns are predicted.
        assert "messaging_limits" not in result.values["sender_id"]
        assert "deletion_protection_enabled" not in result.values["sender_id"]
    else:
        client.release_sender_id.assert_called_once_with(SenderId="EXAMPLE", IsoCountryCode="DE", aws_retry=True)


@pytest.mark.parametrize("check_mode", [False, True])
def test_release_of_missing_sender_id_is_no_change(check_mode):
    client = model_client()
    module = FakeModule(params(state="absent"), check_mode=check_mode, client=client)
    result, _require, _paginate = run(module, describe=client_error("ResourceNotFoundException", "DescribeSenderIds"))

    assert result.values == {"changed": False, "state": "absent"}
    client.release_sender_id.assert_not_called()


def test_release_of_sender_id_released_elsewhere_is_no_change():
    client = model_client()
    client.release_sender_id.side_effect = client_error("ResourceNotFoundException", "ReleaseSenderId")
    module = FakeModule(params(state="absent"), client=client)
    result, _require, _paginate = run(module, describe=described())

    assert result.values == {"changed": False, "state": "absent"}


@pytest.mark.parametrize("check_mode", [False, True])
def test_release_of_deletion_protected_sender_id_fails(check_mode):
    client = model_client()
    module = FakeModule(params(state="absent"), check_mode=check_mode, client=client)
    result, _require, _paginate = run(module, describe=described(DeletionProtectionEnabled=True))

    assert isinstance(result, ModuleFail)
    assert result.values == {
        "msg": (
            "Unable to release Pinpoint SMS Voice V2 sender ID EXAMPLE in DE because deletion protection is "
            "enabled; set deletion_protection_enabled to false with state=present first"
        )
    }
    client.update_sender_id.assert_not_called()
    client.release_sender_id.assert_not_called()


def test_release_error_is_reported():
    client = model_client()
    client.release_sender_id.side_effect = client_error(
        "ConflictException", "ReleaseSenderId", reason="SENDER_ID_ASSOCIATED_TO_POOL"
    )
    module = FakeModule(params(state="absent"), client=client)
    result, _require, _paginate = run(module, describe=described())

    assert isinstance(result, ModuleFail)
    assert result.values == {"msg": "Unable to release Pinpoint SMS Voice V2 sender ID EXAMPLE in DE"}


@pytest.mark.parametrize("state", ["absent", "present"])
def test_describe_error_is_reported(state):
    module = FakeModule(params(state=state), client=model_client())
    result, _require, _paginate = run(module, describe=client_error("AccessDeniedException", "DescribeSenderIds"))

    assert isinstance(result, ModuleFail)
    assert result.values == {"msg": "Unable to describe Pinpoint SMS Voice V2 sender ID EXAMPLE in DE"}


@pytest.mark.parametrize(
    "response",
    [
        {"SenderIds": "invalid"},
        {"SenderIds": [{"SenderId": "EXAMPLE"}]},
        {"SenderIds": [described(DeletionProtectionEnabled="yes")]},
        {"SenderIds": [described(MessageTypes="TRANSACTIONAL")]},
    ],
)
def test_describe_rejects_malformed_response(response):
    module = FakeModule(params(), client=model_client())
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=response),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_sender_id(module._client, module)

    assert "malformed" in raised.value.values["msg"]


def test_describe_rejects_another_sender_id():
    module = FakeModule(params(), client=model_client())
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value={"SenderIds": [described(SenderId="OTHER")]}),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_sender_id(module._client, module)

    assert raised.value.values["msg"] == "AWS returned the wrong Pinpoint SMS Voice V2 sender ID while describing it"


def test_describe_matches_without_letter_case():
    module = FakeModule(params(sender_id="example"), client=model_client())
    with patch.object(plugin, "paginated_query_with_retries", return_value={"SenderIds": [described()]}):
        assert plugin.get_sender_id(module._client, module)["SenderId"] == "EXAMPLE"


def test_list_tags_error_is_reported():
    client = model_client()
    module = FakeModule(params(tags={"Team": "Ops"}), client=client)
    client.list_tags_for_resource.side_effect = client_error("AccessDeniedException", "ListTagsForResource")
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"SenderIds": [described()]}),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "changed": False,
        "msg": f"Unable to list tags for Pinpoint SMS Voice V2 sender ID {ARN}",
    }


def test_sdk_methods_are_checked_before_writes():
    client = model_client()
    module = FakeModule(params(deletion_protection_enabled=True, tags={"New": "1"}), client=client)
    result, require, _paginate = run(module, describe=described(), tags=[{"Key": "Old", "Value": "x"}])

    assert result.values["changed"] is True
    assert require.call_args_list == [
        call(
            module, client, "Pinpoint SMS Voice V2", {"describe_sender_ids": ("MaxResults", "NextToken", "SenderIds")}
        ),
        call(module, client, "Pinpoint SMS Voice V2", {"list_tags_for_resource": ("ResourceArn",)}),
        call(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {
                "update_sender_id": ("DeletionProtectionEnabled", "IsoCountryCode", "SenderId"),
                "tag_resource": ("ResourceArn", "Tags"),
                "untag_resource": ("ResourceArn", "TagKeys"),
            },
        ),
    ]


def test_unsupported_sdk_fails_before_writes():
    client = model_client()
    module = FakeModule(params(deletion_protection_enabled=True), client=client)
    client.list_tags_for_resource.return_value = {"Tags": []}

    def require(module, client, service, methods, changed=False):
        if "update_sender_id" in methods:
            module.fail_json(msg="Installed botocore does not support Pinpoint SMS Voice V2 update_sender_id")

    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", side_effect=require),
        patch.object(plugin, "paginated_query_with_retries", return_value={"SenderIds": [described()]}),
        pytest.raises(ModuleFail),
    ):
        plugin.main()

    client.update_sender_id.assert_not_called()
