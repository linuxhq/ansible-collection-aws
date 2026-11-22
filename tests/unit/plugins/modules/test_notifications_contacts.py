from unittest.mock import Mock, patch

import pytest

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

from ansible_collections.linuxhq.aws.plugins.modules import notifications_contacts as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    assert_module_contract,
    assert_module_rejects,
)


def test_absent_reports_unchanged_for_contact_disappearing_during_delete():
    client = Mock()
    client.delete_email_contact.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteEmailContact",
    )
    module = FakeModule({"email_address": "ops@example.com"})
    with (
        patch.object(
            plugin,
            "get_contact_by_address",
            return_value={"arn": "arn:contact"},
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False


def test_delete_retries_conflicts():
    calls = []

    def delete(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise plugin.ClientError({"Error": {"Code": "ConflictException", "Message": "busy"}}, "DeleteEmailContact")

        return {}

    client = Mock(delete_email_contact=delete)
    with (
        patch.object(plugin, "get_contact_by_address", return_value={"arn": "arn:contact"}),
        patch.object(plugin, "require_client_methods"),
        patch("time.sleep"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, FakeModule({"email_address": "ops@example.com"}))

    assert raised.value.values["changed"] is True
    assert calls == [{"arn": "arn:contact"}] * 2


def test_client_retry_does_not_retry_create_conflicts():
    module = FakeModule({"email_address": "ops@example.com", "name": None, "state": "absent", "tags": None})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_absent"),
        patch.object(module, "client", return_value=Mock()) as client,
    ):
        plugin.main()

    decorator = client.call_args.kwargs["retry_decorator"]
    error = plugin.ClientError({"Error": {"Code": "ConflictException", "Message": "exists"}}, "CreateEmailContact")
    operation = Mock(side_effect=[error, {"arn": "arn:contact"}])
    with patch("time.sleep"), pytest.raises(plugin.ClientError):
        decorator(operation)()

    assert operation.call_count == 1


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["required_if"] == [("state", "present", ["name"])]
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]


@pytest.mark.parametrize("check_mode", [False, True])
def test_tag_only_update_does_not_recreate_the_contact(check_mode):
    client = Mock()
    client.list_tags_for_resource.return_value = {"tags": {"keep": "old", "remove": "yes"}}
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": {"keep": "new"},
        },
        check_mode=check_mode,
    )
    contact = {
        "address": "ops@example.com",
        "arn": "arn:contact",
        "name": "Operations",
    }
    with (
        patch.object(plugin, "get_contact_by_address", return_value=contact),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert raised.value.values["email_contact"]["tags"] == {"keep": "new"}
    if check_mode:
        client.untag_resource.assert_not_called()
        client.tag_resource.assert_not_called()
    else:
        client.untag_resource.assert_called_once_with(arn="arn:contact", tagKeys=["remove"], aws_retry=True)
        client.tag_resource.assert_called_once_with(arn="arn:contact", tags={"keep": "new"}, aws_retry=True)

    client.create_email_contact.assert_not_called()


# User Notifications Contacts, not the module, rejects an address or name it does not accept.
@pytest.mark.parametrize(
    ("email_address", "name"),
    [("ops@example.com", name) for name in ("山田a", "é-", "~", "_", "Z", "7", "山田", " ", "x" * 65)]
    + [("invalid", "Operations"), ("a@b.c", "Operations")],
)
def test_address_and_name_reach_aws(email_address, name):
    module = FakeModule(
        {"email_address": email_address, "name": name, "purge_tags": True, "state": "present", "tags": None}
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


def test_null_name_is_rejected_before_api_calls():
    params = {"email_address": "ops@example.com", "name": None, "state": "present", "tags": None}
    spec = assert_module_contract(plugin)
    spec.pop("supports_check_mode")

    # required_if counts only supplied keys, so ansible-core accepts an explicit null name.
    assert ArgumentSpecValidator(**spec).validate(params).error_messages == []
    assert_module_rejects(plugin, params, "state is present but all of the following are missing: name")


def test_new_contact_omits_empty_tags():
    client = Mock()
    client.create_email_contact.return_value = {"arn": "arn:new"}
    client.get_email_contact.return_value = {"emailContact": None}
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": {},
        }
    )
    with (
        patch.object(plugin, "get_contact_by_address", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    client.create_email_contact.assert_called_once_with(
        emailAddress="ops@example.com", name="Operations", aws_retry=True
    )


def test_new_contact_tolerates_post_create_lookup_race():
    client = Mock()
    client.create_email_contact.return_value = {"arn": "arn:new"}
    client.get_email_contact.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "not visible yet"}},
        "GetEmailContact",
    )
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "get_contact_by_address", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["email_contact"] == {
        "address": "ops@example.com",
        "arn": "arn:new",
        "name": "Operations",
        "status": "inactive",
    }


@pytest.mark.parametrize("tags", [None, {}, {"team": "ops"}])
def test_check_mode_create_predicts_the_created_contact(tags):
    # GetEmailContact right after CreateEmailContact, as AWS answered live: a new contact is inactive.
    created = {
        "address": "ops@example.com",
        "arn": "arn:new",
        "creationTime": "2026-10-27T15:57:04.273000+00:00",
        "name": "Operations",
        "status": "inactive",
        "updateTime": "2026-10-27T15:57:04.273000+00:00",
    }
    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.create_email_contact.return_value = {"arn": "arn:new"}
        client.get_email_contact.return_value = {"emailContact": dict(created)}
        module = FakeModule(
            {"email_address": "ops@example.com", "name": "Operations", "purge_tags": True, "tags": tags},
            check_mode=check_mode,
        )
        with (
            patch.object(plugin, "get_contact_by_address", return_value=None),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        assert raised.value.values["changed"] is True
        assert client.create_email_contact.called is not check_mode
        results[check_mode] = raised.value.values["email_contact"]

    # AWS assigns the ARN and the timestamps, so check mode cannot predict them.
    real = {key: value for key, value in results[False].items() if key not in ("arn", "creation_time", "update_time")}
    assert results[True] == real
    assert results[True]["status"] == "inactive"


def test_converged_contact_does_not_require_unused_operations():
    client = Mock()
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": None,
        }
    )
    contact = {
        "address": "ops@example.com",
        "arn": "arn:contact",
        "name": "Operations",
    }
    with (
        patch.object(plugin, "get_contact_by_address", return_value=contact),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    require.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("tags", [None, {}, {"new": "value"}])
def test_name_change_preserves_contact(check_mode, tags):
    module = FakeModule(
        {"email_address": "ops@example.com", "name": "New Name", "purge_tags": True, "tags": tags},
        check_mode=check_mode,
    )
    current = {"address": "ops@example.com", "arn": "arn:old", "name": "Old Name"}
    client = Mock()
    with patch.object(plugin, "get_contact_by_address", return_value=current), pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, module)

    assert "name cannot be changed" in raised.value.values["msg"]
    assert not client.mock_calls


def test_email_address_follows_the_api_pattern():
    for email_address in ("ops@@example.com", "ops @example.com"):
        module = FakeModule({"email_address": email_address, "name": "Operations", "state": "present", "tags": None})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "ensure_present") as ensure_present,
        ):
            plugin.main()

        ensure_present.assert_called_once()


@pytest.mark.parametrize(("current_tags", "changed"), [({"remove": "yes"}, True), ({}, False)])
def test_tag_failure_reports_whether_tags_were_removed(current_tags, changed):
    client = Mock()
    client.list_tags_for_resource.return_value = {"tags": current_tags}
    client.tag_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "failed"}}, "TagResource"
    )
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": {"keep": "new"},
        }
    )
    contact = {"address": "ops@example.com", "arn": "arn:contact", "name": "Operations"}
    with (
        patch.object(plugin, "get_contact_by_address", return_value=contact),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Unable to tag AWS Notifications contact arn:contact"
    assert raised.value.values["changed"] is changed
    assert client.untag_resource.called is changed


@pytest.mark.parametrize("check_mode", [False, True])
def test_resulting_tag_limit_fails_before_tagging(check_mode):
    client = Mock()
    existing_tags = {f"old{index}": "" for index in range(50)}
    existing_tags["aws:reserved"] = ""
    client.list_tags_for_resource.return_value = {"tags": existing_tags}
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": False,
            "tags": {"new": ""},
        },
        check_mode=check_mode,
    )
    contact = {"address": "ops@example.com", "arn": "arn:contact", "name": "Operations"}
    with (
        patch.object(plugin, "get_contact_by_address", return_value=contact),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "The resulting AWS Notifications contact tags must contain at most 50 entries"
    assert raised.value.values.get("changed", False) is False
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "tags",
    [{"Team": "R&D"}, {"Team": "a,b"}, {"Team#1": "x"}, {"Team": "a\nb"}],
    ids=["ampersand", "comma", "hash-key", "newline"],
)
def test_tag_characters_aws_rejects_fail_before_aws(check_mode, tags):
    # Notifications Contacts TagResource rejects these with BadRequestException (live), which an existing contact
    # with a tag to purge reaches only after UntagResource has removed that tag.
    client = Mock()
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "state": "present",
            "tags": tags,
        },
        check_mode=check_mode,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(module, "client") as connect,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": "tag keys and values must contain only letters, numbers, spaces, and _ . : / = + - @"
    }
    connect.assert_not_called()
    assert client.mock_calls == []


def test_tags_with_characters_aws_accepts_reach_aws():
    # Notifications Contacts TagResource accepts these (live).
    tags = {"Team": "a b_.:/=+-@é1", "日本": "٣²", "Sp": "a\u00a0b"}
    module = FakeModule(
        {"email_address": "ops@example.com", "name": "Operations", "purge_tags": True, "state": "present", "tags": tags}
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()
    assert module.params["tags"] == tags


def test_tag_count_is_not_checked_before_the_client_is_created():
    # Live: TagResource rejects a 51st user tag ("The resultant tag set must not have more than 50 user tags").
    tags = {f"key{index}": "" for index in range(51)}
    params = {
        "email_address": "ops@example.com",
        "name": "Operations",
        "purge_tags": True,
        "state": "present",
        "tags": tags,
    }
    module = FakeModule(params)
    # The tag count is checked against the tags a write would leave, or left to AWS on a create that sends the tags.
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("key", ["aws:owner", "AWS:owner", "Aws:owner"])
def test_reserved_tag_key_fails_before_any_tag_write(key, check_mode):
    client = Mock()
    client.list_tags_for_resource.return_value = {"tags": {"old": "x"}}
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": {key: "me"},
        },
        check_mode=check_mode,
    )
    contact = {"address": "ops@example.com", "arn": "arn:contact", "name": "Operations"}
    with (
        patch.object(plugin, "get_contact_by_address", return_value=contact),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "tag keys beginning with aws: are reserved and cannot be set"
    assert raised.value.values.get("changed", False) is False
    client.untag_resource.assert_not_called()
    client.tag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_unchanged_reserved_tag_key_keeps_working(check_mode):
    client = Mock()
    client.list_tags_for_resource.return_value = {"tags": {"aws:owner": "me"}}
    module = FakeModule(
        {
            "email_address": "ops@example.com",
            "name": "Operations",
            "purge_tags": True,
            "tags": {"aws:owner": "me"},
        },
        check_mode=check_mode,
    )
    contact = {"address": "ops@example.com", "arn": "arn:contact", "name": "Operations"}
    with (
        patch.object(plugin, "get_contact_by_address", return_value=contact),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.tag_resource.assert_not_called()
