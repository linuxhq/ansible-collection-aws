import json
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ssm_document as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)


def params(**overrides):
    values = {
        "content": {"schemaVersion": "2.2"},
        "document_type": "Command",
        "document_version": "$LATEST",
        "force": False,
        "name": "example",
        "purge_tags": True,
        "state": "present",
        "tags": None,
        "wait": True,
        "wait_delay": 5,
        "wait_timeout": 300,
    }
    values.update(overrides)
    return values


def document(content, **overrides):
    values = {"Content": json.dumps(content), "DocumentType": "Command", "DocumentVersion": "1", "Name": "example"}
    values.update(overrides)
    return values


def run_present(client, module, documents):
    """Run ensure_present with get_document returning each document in turn and waits patched out."""
    reads = documents if callable(documents) else Mock(side_effect=list(documents))
    with (
        patch.object(plugin, "get_document", side_effect=reads) as get_document,
        patch.object(plugin, "wait_for_document") as wait_for_document,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.ensure_present(client, module)

    return raised.value, wait_for_document, get_document


def run_absent(client, module, current):
    with (
        patch.object(plugin, "get_document", return_value=current),
        patch.object(plugin, "wait_for_document") as wait_for_document,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.ensure_absent(client, module)

    return raised.value, wait_for_document


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    spec = captured["argument_spec"]
    assert captured["supports_check_mode"]
    assert captured["required_if"] == [("state", "present", ["content", "document_type"])]
    assert spec["force"]["default"] is False
    assert spec["wait"]["default"] is True
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_document_content_accepts_json_or_mapping():
    assert plugin.document_content({"Content": '{"schemaVersion":"2.2"}'}) == {"schemaVersion": "2.2"}
    content = {"schemaVersion": "2.2"}
    assert plugin.document_content({"Content": content}) is content
    assert plugin.document_content(None) == {}


def test_content_is_sent_compared_and_returned_unchanged():
    content = {
        "schemaVersion": "2.2",
        "parameters": {"Message": {"type": "String", "default": "Hi"}, "message": {"type": "String"}},
        "mainSteps": [{"action": "aws:runShellScript", "name": "run", "inputs": {"runCommand": ["echo"]}}],
    }
    client = Mock()
    client.create_document.return_value = {"DocumentDescription": {"DocumentVersion": "1", "Name": "example"}}
    result, _wait, _get = run_present(client, FakeModule(params(content=content)), [None, document(content)])

    assert json.loads(client.create_document.call_args.kwargs["Content"]) == content
    assert result.values["document"]["content"] == content

    result, _wait, _get = run_present(
        Mock(), FakeModule(params(content=content)), [document(content), document(content)]
    )
    assert not result.values["changed"]


def test_snake_case_content_is_not_converted():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    result, _wait, _get = run_present(
        client,
        FakeModule(params(content={"schema_version": "2.2"})),
        [document({"schemaVersion": "2.2"}), document({"schema_version": "2.2"}, DocumentVersion="2")],
    )

    assert result.values["changed"]
    assert client.update_document.call_args.kwargs["Content"] == '{"schema_version":"2.2"}'


def test_content_update_waits_for_the_new_version_before_promoting():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    calls = Mock()
    client.update_document_default_version.side_effect = calls.promote
    module = FakeModule(params(wait=False))
    with (
        patch.object(
            plugin,
            "get_document",
            side_effect=[document({"schemaVersion": "1.2"}), document({"schemaVersion": "2.2"}, DocumentVersion="2")],
        ),
        patch.object(plugin, "wait_for_document", side_effect=lambda *args, **kwargs: calls.wait(*args[2:])),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert client.update_document.call_args.kwargs["Content"] == '{"schemaVersion":"2.2"}'
    assert calls.mock_calls == [
        call.wait("active", "2"),
        call.promote(DocumentVersion="2", Name="example", aws_retry=True),
    ]


def test_default_version_updates_latest_instead_of_the_older_default():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "3"}}
    current = document({"schemaVersion": "1.2"})
    latest = dict(current, DocumentVersion="2")
    updated = document({"schemaVersion": "2.2"}, DocumentVersion="3")
    run_present(client, FakeModule(params(document_version="$DEFAULT")), [current, latest, updated])

    assert client.update_document.call_args.kwargs["DocumentVersion"] == "$LATEST"
    client.update_document_default_version.assert_called_once_with(DocumentVersion="3", Name="example", aws_retry=True)


def test_default_version_promotes_matching_latest_without_duplicate_update():
    client = Mock()
    current = document({"schemaVersion": "1.2"})
    latest = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    run_present(client, FakeModule(params(document_version="$DEFAULT")), [current, latest, latest])

    client.update_document.assert_not_called()
    client.update_document_default_version.assert_called_once_with(DocumentVersion="2", Name="example", aws_retry=True)


def test_default_version_waits_for_a_transitional_latest_before_promoting():
    client = Mock()
    current = document({"schemaVersion": "1.2"})
    creating = document({"schemaVersion": "2.2"}, DocumentVersion="2", Status="Creating")
    active = dict(creating, Status="Active")
    module = FakeModule(params(document_version="$DEFAULT"))
    _result, wait_for_document, get_document = run_present(client, module, [current, creating, active, active])

    wait_for_document.assert_called_once_with(client, module, "active", "2", fail_on_failed=False)
    assert get_document.call_args_list[2].kwargs["document_version"] == "$LATEST"
    client.update_document.assert_not_called()
    client.update_document_default_version.assert_called_once_with(DocumentVersion="2", Name="example", aws_retry=True)


def test_default_version_fails_on_a_failed_latest_with_the_requested_content():
    client = Mock()
    current = document({"schemaVersion": "1.2"})
    failed = document({"schemaVersion": "2.2"}, DocumentVersion="2", Status="Failed", StatusInformation="bad step")
    result, _wait, _get = run_present(client, FakeModule(params(document_version="$DEFAULT")), [current, failed])

    assert result.values["msg"] == "AWS Systems Manager document example failed: bad step"
    assert result.values["changed"] is False
    client.update_document.assert_not_called()
    client.update_document_default_version.assert_not_called()


def test_default_version_promotion_purges_tags_after_a_stale_refresh():
    client = Mock()
    current = document({"schemaVersion": "1.2"}, Tags=[{"Key": "Old", "Value": "1"}])
    latest = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    result, _wait, _get = run_present(
        client,
        FakeModule(params(document_version="$DEFAULT", tags={"Name": "example"})),
        [current, latest, current],
    )

    client.update_document_default_version.assert_called_once_with(DocumentVersion="2", Name="example", aws_retry=True)
    client.remove_tags_from_resource.assert_called_once_with(
        ResourceType="Document", ResourceId="example", TagKeys=["Old"], aws_retry=True
    )
    assert result.values["document"]["tags"] == {"Name": "example"}


def test_update_refresh_reuses_tags_read_before_the_update():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    current = document({"schemaVersion": "1.2"}, Tags=[{"Key": "Name", "Value": "example"}])
    updated = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    result, _wait, get_document = run_present(client, FakeModule(params(tags={"Name": "example"})), [current, updated])

    assert not get_document.call_args_list[1].kwargs.get("include_tags")
    assert result.values["document"]["tags"] == {"Name": "example"}
    client.add_tags_to_resource.assert_not_called()
    client.remove_tags_from_resource.assert_not_called()


@pytest.mark.parametrize("refreshed_content", [{"schemaVersion": "2.2"}, {"schemaVersion": "1.2"}])
def test_update_response_tags_do_not_replace_tags_read_before_the_update(refreshed_content):
    client = Mock()
    client.update_document.return_value = {
        "DocumentDescription": {"DocumentVersion": "2", "Name": "example", "Tags": [{"Key": "Stale", "Value": "1"}]}
    }
    current = document({"schemaVersion": "1.2"}, Tags=[{"Key": "Old", "Value": "1"}])
    refreshed = document(refreshed_content, DocumentVersion="2")
    result, _wait, _get = run_present(client, FakeModule(params(tags={"Name": "example"})), [current, refreshed])

    client.remove_tags_from_resource.assert_called_once_with(
        ResourceType="Document", ResourceId="example", TagKeys=["Old"], aws_retry=True
    )
    client.add_tags_to_resource.assert_called_once_with(
        ResourceType="Document", ResourceId="example", Tags=[{"Key": "Name", "Value": "example"}], aws_retry=True
    )
    assert result.values["document"]["tags"] == {"Name": "example"}


def test_update_response_tags_are_not_returned_when_tags_are_omitted():
    client = Mock()
    client.update_document.return_value = {
        "DocumentDescription": {"DocumentVersion": "2", "Name": "example", "Tags": [{"Key": "Stale", "Value": "1"}]}
    }
    current = document({"schemaVersion": "1.2"})
    refreshed = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    result, _wait, _get = run_present(client, FakeModule(params()), [current, refreshed])

    assert "tags" not in result.values["document"]
    client.add_tags_to_resource.assert_not_called()
    client.remove_tags_from_resource.assert_not_called()


def test_update_result_ignores_stale_default_version_refresh():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2", "Name": "example"}}
    current = document({"schemaVersion": "1.2"})
    result, _wait, _get = run_present(
        client, FakeModule(params(document_version="$DEFAULT")), [current, current, current]
    )

    assert result.values["document"]["content"] == {"schemaVersion": "2.2"}
    assert result.values["document"]["document_version"] == "2"


def test_update_fails_when_aws_omits_the_new_document_version():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {}}
    result, _wait, _get = run_present(
        client, FakeModule(params()), lambda *args, **kwargs: document({"schemaVersion": "1.2"})
    )

    assert "no document version" in result.values["msg"]
    client.update_document_default_version.assert_not_called()


def test_existing_document_type_is_immutable():
    client = Mock()
    result, _wait, _get = run_present(
        client, FakeModule(params(document_type="Session")), [document({"schemaVersion": "2.2"})]
    )

    assert "immutable fields differ" in result.values["msg"]
    client.update_document.assert_not_called()


def test_new_document_serializes_content_and_tags_for_aws():
    client = Mock()
    client.create_document.return_value = {"DocumentDescription": {"DocumentVersion": "1", "Name": "example"}}
    result, wait_for_document, _get = run_present(client, FakeModule(params(tags={"Name": "example"})), [None, None])

    assert result.values["changed"]
    assert result.values["document"] == {
        "content": {"schemaVersion": "2.2"},
        "document_version": "1",
        "name": "example",
        "tags": {"Name": "example"},
    }
    client.create_document.assert_called_once_with(
        Content='{"schemaVersion":"2.2"}',
        DocumentFormat="JSON",
        DocumentType="Command",
        Name="example",
        Tags=[{"Key": "Name", "Value": "example"}],
        aws_retry=True,
    )
    assert wait_for_document.call_args.args[2:] == ("active", "1")


def test_new_document_does_not_wait_when_wait_is_disabled():
    client = Mock()
    client.create_document.return_value = {"DocumentDescription": {"DocumentVersion": "1", "Name": "example"}}
    _result, wait_for_document, _get = run_present(client, FakeModule(params(wait=False)), [None, None])

    wait_for_document.assert_not_called()


def test_deleting_document_is_waited_on_and_created_again():
    client = Mock()
    client.create_document.return_value = {"DocumentDescription": {"DocumentVersion": "1", "Name": "example"}}
    deleting = document({"schemaVersion": "2.2"}, Status="Deleting")
    result, wait_for_document, _get = run_present(client, FakeModule(params()), [deleting, None, None])

    assert result.values["changed"]
    assert wait_for_document.call_args_list[0].args[2:] == ("deleted",)
    client.create_document.assert_called_once()


def test_deleting_document_is_predicted_as_created_in_check_mode():
    client = Mock()
    deleting = document({"schemaVersion": "2.2"}, Status="Deleting")
    result, wait_for_document, _get = run_present(client, FakeModule(params(), check_mode=True), [deleting])

    assert result.values["changed"]
    wait_for_document.assert_not_called()
    client.create_document.assert_not_called()


@pytest.mark.parametrize("status", ["Creating", "Updating"])
def test_transitional_document_is_waited_on_before_comparing(status):
    settling = document({"schemaVersion": "2.2"}, Status=status)
    active = document({"schemaVersion": "2.2"}, Status="Active")
    result, wait_for_document, _get = run_present(Mock(), FakeModule(params()), [settling, active, active])

    assert not result.values["changed"]
    assert wait_for_document.call_args_list[0].args[2:] == ("active", "1")


def test_failed_document_with_the_requested_content_fails_with_status_information():
    failed = document({"schemaVersion": "2.2"}, Status="Failed", StatusInformation="Invalid step")
    result, _wait, _get = run_present(Mock(), FakeModule(params()), [failed])

    assert result.values["msg"] == "AWS Systems Manager document example failed: Invalid step"


def test_failed_document_with_new_content_is_updated():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    failed = document({"schemaVersion": "1.2"}, Status="Failed")
    result, _wait, _get = run_present(
        client, FakeModule(params()), [failed, document({"schemaVersion": "2.2"}, DocumentVersion="2")]
    )

    assert result.values["changed"]
    client.update_document.assert_called_once()


@pytest.mark.parametrize("state", ["active", "deleted"])
def test_wait_message_names_the_target_state(state):
    module = FakeModule(params())
    with patch.object(plugin, "run_waiter", side_effect=ModuleFail({})) as run_waiter, pytest.raises(ModuleFail):
        plugin.wait_for_document(Mock(), module, state, "2" if state == "active" else None)

    assert run_waiter.call_args.args[3] == f"document_{state}"
    assert run_waiter.call_args.args[4] == f"Unable to wait for AWS Systems Manager document example to become {state}"


def test_wait_fails_when_the_document_version_failed():
    client = Mock(describe_document=Mock(return_value={"Document": {"Status": "Failed", "StatusInformation": "Bad"}}))
    with patch.object(plugin, "run_waiter"), pytest.raises(ModuleFail) as raised:
        plugin.wait_for_document(client, FakeModule(params()), "active", "2")

    assert raised.value.values["msg"] == "AWS Systems Manager document example failed: Bad"
    client.describe_document.assert_called_once_with(Name="example", DocumentVersion="2", aws_retry=True)


def test_waiters_stop_on_terminal_states():
    active = {
        acceptor["expected"]: acceptor["state"]
        for acceptor in plugin.SSM_DOCUMENT_WAITER_MODEL_DATA["document_active"]["acceptors"]
    }
    deleted = {
        acceptor["expected"]: acceptor["state"]
        for acceptor in plugin.SSM_DOCUMENT_WAITER_MODEL_DATA["document_deleted"]["acceptors"]
    }

    assert active == {
        "Active": "success",
        "Failed": "success",
        "Creating": "retry",
        "Updating": "retry",
        "Deleting": "failure",
    }
    assert deleted == {"InvalidDocument": "success", "Deleting": "retry"}


@pytest.mark.parametrize("check_mode", [False, True])
def test_retry_recovers_failed_default_promotion(check_mode):
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    client.update_document_default_version.side_effect = [
        ClientError({"Error": {"Code": "InternalServerError", "Message": "failed"}}, "UpdateDocumentDefaultVersion"),
        {},
    ]
    module = FakeModule(params())
    old = document({"schemaVersion": "1.2"})
    latest = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    run_present(client, module, lambda *args, **kwargs: old)

    module.check_mode = check_mode

    def read_document(client, module, include_tags=False, document_version=None, changed=False):
        return old if document_version == "$DEFAULT" else latest

    result, _wait, _get = run_present(client, module, read_document)

    assert client.update_document.call_count == 1
    assert client.update_document_default_version.call_count == (1 if check_mode else 2)
    assert result.values["changed"] is True
    if not check_mode:
        result, _wait, _get = run_present(client, module, lambda *args, **kwargs: latest)

        assert result.values["changed"] is False
        assert client.update_document_default_version.call_count == 2


def test_absent_tolerates_document_disappearing_during_delete():
    client = Mock()
    client.delete_document.side_effect = ClientError(
        {"Error": {"Code": "InvalidDocument", "Message": "gone"}}, "DeleteDocument"
    )
    result, _wait = run_absent(client, FakeModule(params(state="absent")), {"Name": "example"})

    assert result.values["changed"]


def test_absent_waits_for_deletion():
    client = Mock()
    result, wait_for_document = run_absent(client, FakeModule(params(state="absent")), {"Name": "example"})

    assert result.values["changed"]
    client.delete_document.assert_called_once_with(Name="example", aws_retry=True)
    assert wait_for_document.call_args.args[2:] == ("deleted",)


def test_absent_sends_force_when_requested():
    client = Mock()
    run_absent(client, FakeModule(params(state="absent", force=True, wait=False)), {"Name": "example"})

    client.delete_document.assert_called_once_with(Name="example", Force=True, aws_retry=True)


def test_absent_explains_documents_used_by_associations():
    client = Mock()
    client.delete_document.side_effect = ClientError(
        {"Error": {"Code": "AssociatedInstances", "Message": "in use"}}, "DeleteDocument"
    )
    result, _wait = run_absent(client, FakeModule(params(state="absent")), {"Name": "example"})

    assert result.values["msg"] == (
        "Unable to delete AWS Systems Manager document example because associations use it; "
        "delete the associations first"
    )


def test_absent_waits_on_a_document_already_deleting_without_deleting_again():
    client = Mock()
    result, wait_for_document = run_absent(
        client, FakeModule(params(state="absent")), {"Name": "example", "Status": "Deleting"}
    )

    assert not result.values["changed"]
    client.delete_document.assert_not_called()
    wait_for_document.assert_called_once()


@pytest.mark.parametrize("response", [None, {"Content": "not-json"}, {"Content": "[]"}])
def test_get_document_rejects_malformed_content(response):
    client = Mock(get_document=Mock(return_value=response))
    with pytest.raises(ModuleFail) as raised:
        plugin.get_document(client, FakeModule(params()))

    assert "Unexpected" in raised.value.values["msg"]


def test_get_document_rejects_malformed_tags():
    client = Mock(
        get_document=Mock(return_value={"Content": "{}"}),
        list_tags_for_resource=Mock(return_value={"TagList": [None]}),
    )
    with pytest.raises(ModuleFail) as raised:
        plugin.get_document(client, FakeModule(params()), include_tags=True)

    assert (
        raised.value.values["msg"] == "Unexpected response while listing tags for AWS Systems Manager document example"
    )


def test_create_rejects_malformed_response():
    client = Mock(create_document=Mock(return_value={"DocumentDescription": None}))
    result, _wait, _get = run_present(client, FakeModule(params()), [None])

    assert result.values["msg"] == "AWS Systems Manager did not return the created document example"


def test_present_validates_bounds_for_internal_promotion_wait():
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params(wait=False, wait_delay=0))),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "wait_delay" in raised.value.values["msg"]


def test_transitional_document_that_ends_failed_is_replaced_with_new_content():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    creating = document({"schemaVersion": "1.2"}, Status="Creating")
    failed = document({"schemaVersion": "1.2"}, Status="Failed", StatusInformation="Invalid step")
    updated = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    result, wait_for_document, _get = run_present(client, FakeModule(params()), [creating, failed, updated])

    assert result.values["changed"]
    assert wait_for_document.call_args_list[0].args[2:] == ("active", "1")
    assert wait_for_document.call_args_list[0].kwargs["fail_on_failed"] is False
    client.update_document.assert_called_once()


def test_wait_without_fail_on_failed_does_not_inspect_the_status():
    client = Mock()
    with patch.object(plugin, "run_waiter"):
        plugin.wait_for_document(client, FakeModule(params()), "active", "2", fail_on_failed=False)

    client.describe_document.assert_not_called()


@pytest.mark.parametrize("changed", [False, True])
def test_wait_failures_report_whether_the_document_changed(changed):
    client = Mock(describe_document=Mock(return_value={"Document": {"Status": "Failed"}}))
    with patch.object(plugin, "run_waiter") as run_waiter, pytest.raises(ModuleFail) as raised:
        plugin.wait_for_document(client, FakeModule(params()), "active", "2", changed=changed)

    assert run_waiter.call_args.kwargs["changed"] is changed
    assert raised.value.values["changed"] is changed


def test_failure_after_create_reports_changed():
    client = Mock()
    client.create_document.return_value = {"DocumentDescription": {"DocumentVersion": "1"}}
    with (
        patch.object(plugin, "get_document", return_value=None),
        patch.object(plugin, "run_waiter", side_effect=ModuleFail({})) as run_waiter,
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_present(client, FakeModule(params()))

    assert run_waiter.call_args.kwargs["changed"] is True


def test_promotion_failure_after_update_reports_changed():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    client.update_document_default_version.side_effect = ClientError(
        {"Error": {"Code": "InvalidDocumentOperation", "Message": "no"}}, "UpdateDocumentDefaultVersion"
    )
    result, _wait, _get = run_present(client, FakeModule(params()), [document({"schemaVersion": "1.2"})])

    assert result.values["changed"] is True
    assert result.values["msg"] == "Unable to set the default version of AWS Systems Manager document example"


def test_promotion_failure_without_update_reports_unchanged():
    client = Mock()
    client.update_document_default_version.side_effect = ClientError(
        {"Error": {"Code": "InvalidDocumentOperation", "Message": "no"}}, "UpdateDocumentDefaultVersion"
    )
    latest = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    result, _wait, _get = run_present(client, FakeModule(params()), [latest, document({"schemaVersion": "1.2"})])

    assert result.values["changed"] is False
    client.update_document.assert_not_called()


def test_tag_failure_after_update_reports_changed():
    client = Mock()
    client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
    client.add_tags_to_resource.side_effect = ClientError(
        {"Error": {"Code": "InvalidResourceId", "Message": "no"}}, "AddTagsToResource"
    )
    current = document({"schemaVersion": "1.2"}, Tags=[])
    updated = document({"schemaVersion": "2.2"}, DocumentVersion="2", Tags=[])
    result, _wait, _get = run_present(client, FakeModule(params(tags={"Name": "example"})), [current, updated])

    assert result.values["changed"] is True
    assert result.values["msg"] == "Unable to tag AWS Systems Manager document example"


def test_absent_wait_failure_after_delete_reports_changed():
    client = Mock()
    with (
        patch.object(plugin, "get_document", return_value={"Name": "example"}),
        patch.object(plugin, "run_waiter", side_effect=ModuleFail({})) as run_waiter,
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_absent(client, FakeModule(params(state="absent")))

    assert run_waiter.call_args.kwargs["changed"] is True


@pytest.mark.parametrize("check_mode", [False, True])
def test_numbered_version_with_different_content_fails_before_any_change(check_mode):
    client = Mock()
    result, _wait, get_document = run_present(
        client,
        FakeModule(params(document_version="2"), check_mode=check_mode),
        [document({"schemaVersion": "1.2"}, DocumentVersion="2")],
    )

    assert isinstance(result, ModuleFail)
    assert not result.values.get("changed")
    assert result.values["msg"] == (
        "Unable to update AWS Systems Manager document example version 2: "
        "numbered document versions cannot be updated; use $LATEST or $DEFAULT"
    )
    assert get_document.call_count == 1
    client.update_document.assert_not_called()
    client.update_document_default_version.assert_not_called()


def test_numbered_version_with_matching_content_is_unchanged_without_promotion():
    client = Mock()
    result, _wait, get_document = run_present(
        client,
        FakeModule(params(document_version="2")),
        [document({"schemaVersion": "2.2"}, DocumentVersion="2")],
    )

    assert result.values["changed"] is False
    assert result.values["document"]["document_version"] == "2"
    assert get_document.call_count == 1
    client.update_document.assert_not_called()
    client.update_document_default_version.assert_not_called()


def test_numbered_version_refreshes_latest_after_create():
    client = Mock()
    client.create_document.return_value = {"DocumentDescription": {"DocumentVersion": "1"}}
    result, _wait, get_document = run_present(
        client, FakeModule(params(document_version="3")), [None, document({"schemaVersion": "2.2"})]
    )

    assert result.values["changed"] is True
    assert get_document.call_args_list[1].kwargs["document_version"] == "$LATEST"


@pytest.mark.parametrize("document_version", ["$DEFAULT", "$LATEST", "2"])
def test_absent_ignores_document_version(document_version):
    client = Mock(get_document=Mock(return_value={"Content": "{}", "Name": "example"}))
    with pytest.raises(ModuleExit) as raised:
        plugin.ensure_absent(client, FakeModule(params(state="absent", document_version=document_version, wait=False)))

    assert raised.value.values["changed"] is True
    assert client.get_document.call_args.kwargs["DocumentVersion"] == "$LATEST"
    client.delete_document.assert_called_once_with(Name="example", aws_retry=True)


def test_default_version_check_mode_predicts_the_promoted_latest_version():
    current = document({"schemaVersion": "1.2"})
    latest = document({"schemaVersion": "2.2"}, DocumentVersion="2")
    real, _wait, _get = run_present(Mock(), FakeModule(params(document_version="$DEFAULT")), [current, latest, latest])
    client = Mock()
    predicted, _wait, _get = run_present(
        client, FakeModule(params(document_version="$DEFAULT"), check_mode=True), [current, latest]
    )

    assert predicted.values == real.values
    assert predicted.values["document"]["document_version"] == "2"
    client.update_document_default_version.assert_not_called()
