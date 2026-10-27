from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ssm_association as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

UPDATE_PARAMETERS = (
    "AssociationId",
    "AssociationName",
    "AssociationVersion",
    "DocumentVersion",
    "Name",
    "Parameters",
    "ScheduleExpression",
    "Targets",
)


def params(**overrides):
    values = {
        "association_name": None,
        "name": "document",
        "purge_tags": True,
        "schedule_expression": "rate(1 hour)",
        "state": "present",
        "tags": None,
        "targets": [{"key": "InstanceIds", "values": ["i-1"]}],
    }
    values.update(overrides)
    return values


def current_association(**overrides):
    values = {
        "AssociationId": "association-1",
        "AssociationVersion": "1",
        "DocumentVersion": "$LATEST",
        "Name": "document",
        "Parameters": {"Mode": ["safe"]},
        "ScheduleExpression": "rate(1 hour)",
        "Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
    }
    values.update(overrides)
    return values


@pytest.fixture(autouse=True)
def sleep():
    with patch.object(plugin.time, "sleep") as sleep:
        yield sleep


def read_after_update_is_current(client):
    if client.describe_association.side_effect is None:
        client.describe_association.side_effect = lambda **_kwargs: client.update_association.return_value


def run_present(client, module, current):
    read_after_update_is_current(client)
    with (
        patch.object(plugin, "get_boto3_client_method_parameters", return_value=UPDATE_PARAMETERS),
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.ensure_present(client, module, current)

    return raised.value


def run_main(module, associations):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=associations),
        patch.object(
            plugin,
            "describe_association",
            side_effect=lambda client, module, association_id: {"AssociationId": association_id},
        ),
        patch.object(
            plugin, "ensure_present", side_effect=lambda client, module, current: module.exit_json(current=current)
        ),
        patch.object(
            plugin, "ensure_absent", side_effect=lambda client, module, current: module.exit_json(current=current)
        ),
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert "required_if" not in captured
    assert captured["argument_spec"]["association_name"] == {"type": "str"}
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_targets_apply_defaults_and_ignore_order():
    left = [
        {"key": "tag:Role", "values": ["web", "api", "web"]},
        {"key": "InstanceIds", "values": ["i-2", "i-1"]},
        {"key": "InstanceIds", "values": ["i-1", "i-2"]},
    ]
    normalized = plugin.comparable_targets(left)

    assert normalized == plugin.comparable_targets(reversed(left))
    assert normalized[1]["values"] == ["api", "web"]


def test_absent_tolerates_association_disappearing_during_delete():
    client = Mock()
    client.delete_association.side_effect = ClientError(
        {"Error": {"Code": "AssociationDoesNotExist", "Message": "gone"}}, "DeleteAssociation"
    )
    with pytest.raises(ModuleExit) as raised:
        plugin.ensure_absent(client, FakeModule({"name": "document"}), {"AssociationId": "association-1"})

    assert raised.value.values["changed"]


def test_check_mode_predicts_new_association_without_api_call():
    client = Mock()
    result = run_present(client, FakeModule(params(tags={"Env": "test"}), check_mode=True), None)

    client.create_association.assert_not_called()
    assert result.values["changed"]
    assert result.values["association"]["schedule_expression"] == "rate(1 hour)"


@pytest.mark.parametrize("overrides", [{}, {"association_name": "weekly", "schedule_expression": None}])
def test_check_mode_predicts_a_created_association_as_aws_returns_it(overrides):
    module_params = params(tags={"Env": "test"}, **overrides)
    # CreateAssociation fills these in for an association created without them.
    created = {
        "ApplyOnlyAtCronInterval": False,
        "AssociationId": "association-1",
        "AssociationVersion": "1",
        "Date": "2026-10-26T15:42:09.002000-07:00",
        "DocumentVersion": "$DEFAULT",
        "LastUpdateAssociationDate": "2026-10-26T15:42:09.002000-07:00",
        "Name": "document",
        "Overview": {"DetailedStatus": "Creating", "Status": "Pending"},
        "Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
    }
    for option, field in (("association_name", "AssociationName"), ("schedule_expression", "ScheduleExpression")):
        if module_params[option] is not None:
            created[field] = module_params[option]

    client = Mock()
    client.create_association.return_value = {"AssociationDescription": created}
    real = run_present(client, FakeModule(module_params), None)
    check_client = Mock()
    predicted = run_present(check_client, FakeModule(module_params, check_mode=True), None)

    assigned = {"association_id", "date", "last_update_association_date"}
    assert predicted.values["association"] == {
        key: value for key, value in real.values["association"].items() if key not in assigned
    }
    check_client.create_association.assert_not_called()


def test_create_uses_known_tags_without_eventual_lookup():
    client = Mock()
    client.create_association.return_value = {
        "AssociationDescription": {"AssociationId": "association-1", "Name": "document"}
    }
    run_present(client, FakeModule(params(tags={"Env": "test"})), None)

    client.list_tags_for_resource.assert_not_called()
    client.add_tags_to_resource.assert_not_called()


def test_create_sends_association_name():
    client = Mock()
    client.create_association.return_value = {
        "AssociationDescription": {"AssociationId": "association-1", "Name": "document"}
    }
    result = run_present(client, FakeModule(params(association_name="weekly")), None)

    assert result.values["changed"]
    assert client.create_association.call_args.kwargs["AssociationName"] == "weekly"


def test_create_without_schedule_or_targets_sends_only_the_document():
    client = Mock()
    client.create_association.return_value = {
        "AssociationDescription": {"AssociationId": "association-1", "Name": "document"}
    }
    run_present(client, FakeModule(params(schedule_expression=None, targets=None)), None)

    client.create_association.assert_called_once_with(Name="document", aws_retry=True)


def test_existing_association_updates_schedule_and_sorted_targets():
    client = Mock()
    client.update_association.return_value = {
        "AssociationDescription": current_association(
            ScheduleExpression="rate(2 hours)", Targets=[{"Key": "InstanceIds", "Values": ["i-1", "i-2"]}]
        )
    }
    result = run_present(
        client,
        FakeModule(
            params(schedule_expression="rate(2 hours)", targets=[{"key": "InstanceIds", "values": ["i-2", "i-1"]}])
        ),
        current_association(),
    )

    assert result.values["changed"]
    client.update_association.assert_called_once_with(
        AssociationId="association-1",
        AssociationVersion="1",
        DocumentVersion="$LATEST",
        Name="document",
        Parameters={"Mode": ["safe"]},
        ScheduleExpression="rate(2 hours)",
        Targets=[{"Key": "InstanceIds", "Values": ["i-1", "i-2"]}],
        aws_retry=True,
    )


@pytest.mark.parametrize(
    ("overrides", "kept"),
    [
        ({"schedule_expression": None}, {"ScheduleExpression": "rate(1 hour)"}),
        ({"targets": None}, {"Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}]}),
    ],
)
def test_omitted_option_keeps_the_current_value(overrides, kept):
    client = Mock()
    client.update_association.return_value = {"AssociationDescription": current_association()}
    changes = {"schedule_expression": "rate(2 hours)", "targets": [{"key": "InstanceIds", "values": ["i-2"]}]}
    changes.update(overrides)
    result = run_present(client, FakeModule(params(**changes)), current_association())

    assert result.values["changed"]
    request = client.update_association.call_args.kwargs
    for key, value in kept.items():
        assert request[key] == value


def test_omitted_schedule_and_targets_report_no_change():
    client = Mock()
    result = run_present(client, FakeModule(params(schedule_expression=None, targets=None)), current_association())

    assert not result.values["changed"]
    client.update_association.assert_not_called()


def test_update_waits_until_describe_returns_the_new_version(sleep):
    stale = {"AssociationDescription": current_association()}
    updated = {
        "AssociationDescription": current_association(AssociationVersion="2", ScheduleExpression="rate(2 hours)")
    }
    client = Mock(update_association=Mock(return_value=updated))
    client.describe_association.side_effect = [stale, stale, updated]
    result = run_present(client, FakeModule(params(schedule_expression="rate(2 hours)")), current_association())

    assert result.values["changed"] is True
    assert result.values["association"]["association_version"] == "2"
    assert result.values["association"]["schedule_expression"] == "rate(2 hours)"
    assert client.describe_association.call_count == 3
    client.describe_association.assert_called_with(AssociationId="association-1", aws_retry=True)
    assert sleep.call_count == 2


def test_update_fails_when_describe_never_returns_the_new_version(sleep):
    client = Mock(
        update_association=Mock(return_value={"AssociationDescription": current_association(AssociationVersion="2")}),
    )
    client.describe_association.side_effect = lambda **_kwargs: {"AssociationDescription": current_association()}
    module = FakeModule(params(schedule_expression="rate(2 hours)"))
    with patch.object(plugin.time, "monotonic", side_effect=[0, 30, plugin.ASSOCIATION_VERSION_TIMEOUT]):
        result = run_present(client, module, current_association())

    assert result.values["changed"] is True
    assert result.values["msg"] == (
        "Timed out waiting for AWS Systems Manager association association-1 to report version 2"
    )
    assert sleep.call_count == 1


def test_describe_failure_after_update_reports_changed():
    client = Mock(
        update_association=Mock(return_value={"AssociationDescription": current_association(AssociationVersion="2")})
    )
    client.describe_association.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "no"}}, "DescribeAssociation"
    )
    result = run_present(client, FakeModule(params(schedule_expression="rate(2 hours)")), current_association())

    assert result.values["changed"] is True
    assert result.values["msg"] == "Unable to describe AWS Systems Manager association association-1"


def test_describe_missing_association_returns_none():
    client = Mock()
    client.describe_association.side_effect = ClientError(
        {"Error": {"Code": "AssociationDoesNotExist", "Message": "gone"}}, "DescribeAssociation"
    )

    assert plugin.describe_association(client, FakeModule({}), "a-1") is None


def test_describe_rejects_malformed_response():
    client = Mock(describe_association=Mock(return_value={"AssociationDescription": None}))
    with pytest.raises(ModuleFail) as raised:
        plugin.describe_association(client, FakeModule({}), "a-1")

    assert raised.value.values["msg"] == "Unexpected response while describing AWS Systems Manager association a-1"


def test_create_rejects_malformed_response():
    client = Mock(create_association=Mock(return_value={"AssociationDescription": None}))
    result = run_present(client, FakeModule(params()), None)

    assert result.values["msg"] == "AWS Systems Manager did not return the created association document"


def test_association_tags_rejects_malformed_response():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": [None]}))
    with pytest.raises(ModuleFail) as raised:
        plugin.association_with_tags(client, FakeModule({}), {"AssociationId": "a-1"})

    assert (
        raised.value.values["msg"] == "Unexpected response while listing tags for AWS Systems Manager association a-1"
    )


def test_update_rejects_malformed_response():
    client = Mock(update_association=Mock(return_value={"AssociationDescription": None}))
    result = run_present(client, FakeModule(params(schedule_expression="rate(2 hours)")), current_association())

    assert result.values["msg"] == "AWS Systems Manager did not return the updated association document"


@pytest.mark.parametrize("association", [None, {"Name": "document"}])
def test_main_rejects_malformed_association_summaries(association):
    result, _require = run_main(FakeModule(params(state="absent"), client=Mock()), [association])

    assert result.values["msg"] == "Unexpected response while listing AWS Systems Manager associations for document"


def test_association_name_selects_one_of_several_associations():
    associations = [
        {"AssociationId": "a-1", "Name": "document", "AssociationName": "quick-setup"},
        {"AssociationId": "a-2", "Name": "document", "AssociationName": "weekly"},
    ]
    result, _require = run_main(
        FakeModule(params(association_name="weekly", state="absent"), client=Mock()), associations
    )

    assert result.values["current"]["AssociationId"] == "a-2"


def test_association_name_ignores_associations_with_another_name():
    associations = [{"AssociationId": "a-1", "Name": "document", "AssociationName": "quick-setup"}]
    result, _require = run_main(
        FakeModule(params(association_name="weekly", state="absent"), client=Mock()), associations
    )

    assert result.values["current"] is None


def test_multiple_associations_suggest_association_name():
    associations = [
        {"AssociationId": "a-1", "Name": "document"},
        {"AssociationId": "a-2", "Name": "document", "AssociationName": "weekly"},
    ]
    result, _require = run_main(FakeModule(params(state="absent"), client=Mock()), associations)

    assert result.values["msg"] == (
        "Multiple AWS Systems Manager associations exist for document document: a-1, a-2; "
        "set association_name to select one"
    )


def test_association_name_requires_sdk_support_on_create():
    _result, require_client_methods = run_main(FakeModule(params(association_name="weekly"), client=Mock()), [])

    assert "AssociationName" in require_client_methods.call_args.args[3]["create_association"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"association_name": "ab"},
            "association_name must be 3 to 128 letters, numbers, underscores, hyphens, or periods",
        ),
        (
            {"association_name": "has space"},
            "association_name must be 3 to 128 letters, numbers, underscores, hyphens, or periods",
        ),
        ({"schedule_expression": ""}, "schedule_expression must be 1 to 256 characters"),
        (
            {"targets": [{"key": f"tag:Role{index}", "values": ["web"]} for index in range(6)]},
            "targets must contain at most 5 targets",
        ),
        ({"targets": [{"key": "", "values": ["web"]}]}, "targets[].key must be 1 to 163 characters"),
        (
            {"targets": [{"key": "tag:Role", "values": [f"role-{index}" for index in range(51)]}]},
            "targets[].values must contain at most 50 entries",
        ),
        ({"targets": [{"key": "tag:Role", "values": []}]}, "targets[].values must contain at least one entry"),
    ],
)
def test_provider_limits_are_rejected(overrides, message):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params(**overrides))),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == message


@pytest.mark.parametrize("check_mode", [False, True])
def test_empty_targets_are_rejected_before_aws(check_mode):
    module = FakeModule(params(targets=[]), check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "changed": False,
        "msg": "targets must contain at least one entry; omit targets to keep the current targets",
    }
    module.client.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_more_than_50_tags_are_rejected_before_aws(check_mode):
    # AWS rejects a 51st association tag with InvalidTag on create and TooManyTagsError when tagging.
    module = FakeModule(params(tags={f"key{index}": "" for index in range(51)}), check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": "tags must contain at most 50 entries"}
    module.client.assert_not_called()


def test_50_tags_and_aws_reserved_tags_are_accepted():
    tags = {f"key{index}": "" for index in range(50)}
    tags["aws:reserved"] = ""
    result, _require_client_methods = run_main(FakeModule(params(tags=tags)), [])

    assert isinstance(result, ModuleExit)
    assert result.values == {"current": None}


@pytest.mark.parametrize("check_mode", [False, True])
def test_association_result_preserves_parameter_names(check_mode):
    parameters = {"Message": ["Hello"], "message": ["World"]}
    result = run_present(
        Mock(), FakeModule(params(), check_mode=check_mode), current_association(Parameters=parameters)
    )

    assert result.values["changed"] is False
    assert result.values["association"]["parameters"] == parameters


def test_failure_after_create_reports_changed():
    client = Mock(create_association=Mock(return_value={"AssociationDescription": {}}))
    result = run_present(client, FakeModule(params()), None)

    assert result.values["changed"] is True
    assert result.values["msg"] == "AWS Systems Manager did not return the created association document"


def test_tag_failure_after_update_reports_changed():
    client = Mock(
        list_tags_for_resource=Mock(return_value={"TagList": []}),
        update_association=Mock(return_value={"AssociationDescription": current_association(AssociationVersion="2")}),
    )
    client.add_tags_to_resource.side_effect = ClientError(
        {"Error": {"Code": "InvalidResourceId", "Message": "no"}}, "AddTagsToResource"
    )
    module = FakeModule(params(schedule_expression="rate(2 hours)", tags={"Name": "example"}))
    result = run_present(client, module, current_association())

    assert result.values["changed"] is True
    assert result.values["msg"] == "Unable to tag AWS Systems Manager association association-1"


def test_update_reuses_tags_read_before_the_update():
    client = Mock(
        list_tags_for_resource=Mock(return_value={"TagList": [{"Key": "Old", "Value": "1"}]}),
        update_association=Mock(return_value={"AssociationDescription": current_association(AssociationVersion="2")}),
    )
    module = FakeModule(params(schedule_expression="rate(2 hours)", tags={"Name": "example"}))
    result = run_present(client, module, current_association())

    assert result.values["changed"] is True
    assert result.values["association"]["tags"] == {"Name": "example"}
    client.list_tags_for_resource.assert_called_once()
    client.remove_tags_from_resource.assert_called_once_with(
        ResourceType="Association", ResourceId="association-1", TagKeys=["Old"], aws_retry=True
    )
    client.add_tags_to_resource.assert_called_once_with(
        ResourceType="Association",
        ResourceId="association-1",
        Tags=[{"Key": "Name", "Value": "example"}],
        aws_retry=True,
    )


def test_tag_failure_without_update_reports_unchanged():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": []}))
    client.add_tags_to_resource.side_effect = ClientError(
        {"Error": {"Code": "InvalidResourceId", "Message": "no"}}, "AddTagsToResource"
    )
    result = run_present(client, FakeModule(params(tags={"Name": "example"})), current_association())

    assert result.values["changed"] is False
    client.update_association.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_association_status_names_are_preserved(check_mode):
    overview = {"AssociationStatusAggregatedCount": {"InProgress": 1, "Success": 2}, "DetailedStatus": "Success"}
    result = run_present(Mock(), FakeModule(params(), check_mode=check_mode), current_association(Overview=overview))

    assert result.values["association"]["overview"] == {
        "association_status_aggregated_count": {"InProgress": 1, "Success": 2},
        "detailed_status": "Success",
    }


def run_update(current, **overrides):
    client = Mock()
    client.update_association.return_value = {"AssociationDescription": current_association()}
    read_after_update_is_current(client)
    with (
        patch.object(
            plugin,
            "get_boto3_client_method_parameters",
            return_value=UPDATE_PARAMETERS
            + (
                "ApplyOnlyAtCronInterval",
                "CalendarNames",
                "Duration",
                "ScheduleOffset",
                "TargetLocations",
                "TargetMaps",
            ),
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(**overrides)), current)

    assert raised.value.values["changed"]
    return client.update_association.call_args.kwargs


def test_update_omits_empty_lists_copied_from_the_association():
    request = run_update(
        current_association(CalendarNames=[], TargetLocations=[], TargetMaps=[]),
        schedule_expression="rate(2 hours)",
        targets=None,
    )

    assert request["Targets"] == [{"Key": "InstanceIds", "Values": ["i-1"]}]
    assert not {"CalendarNames", "TargetLocations", "TargetMaps"} & set(request)


def test_update_omits_target_maps_when_sending_targets():
    target_maps = [{"Source": ["i-1"]}]
    request = run_update(
        current_association(Targets=[], TargetMaps=target_maps),
        targets=[{"key": "InstanceIds", "values": ["i-2"]}],
    )

    assert request["Targets"] == [{"Key": "InstanceIds", "Values": ["i-2"]}]
    assert "TargetMaps" not in request


def test_update_keeps_target_maps_without_targets():
    target_maps = [{"Source": ["i-1"]}]
    request = run_update(
        current_association(Targets=[], TargetMaps=target_maps),
        schedule_expression="rate(2 hours)",
        targets=None,
    )

    assert request["TargetMaps"] == target_maps
    assert "Targets" not in request


def test_check_mode_predicts_target_maps_replaced_by_targets():
    client = Mock()
    result = run_present(
        client,
        FakeModule(params(targets=[{"key": "InstanceIds", "values": ["i-2"]}]), check_mode=True),
        current_association(Targets=[], TargetMaps=[{"Source": ["i-1"]}]),
    )

    assert result.values["changed"]
    assert result.values["association"]["targets"] == [{"key": "InstanceIds", "values": ["i-2"]}]
    assert "target_maps" not in result.values["association"]
    client.update_association.assert_not_called()


def test_check_mode_keeps_target_maps_without_targets():
    client = Mock()
    target_maps = [{"Source": ["i-1"]}]
    result = run_present(
        client,
        FakeModule(params(schedule_expression="rate(2 hours)", targets=None), check_mode=True),
        current_association(Targets=[], TargetMaps=target_maps),
    )

    assert result.values["changed"]
    assert result.values["association"]["target_maps"] == target_maps
    client.update_association.assert_not_called()


CRON_ONLY_FIELDS = {"ApplyOnlyAtCronInterval": True, "Duration": 2, "ScheduleOffset": 3}


def test_update_to_rate_schedule_drops_cron_only_fields():
    request = run_update(
        current_association(ScheduleExpression="cron(0 0 * * ? *)", **CRON_ONLY_FIELDS),
        schedule_expression="rate(2 hours)",
    )

    assert request["ScheduleExpression"] == "rate(2 hours)"
    assert not set(CRON_ONLY_FIELDS) & set(request)


@pytest.mark.parametrize(
    "overrides",
    [
        {"schedule_expression": "cron(0 1 * * ? *)"},
        {"schedule_expression": None, "targets": [{"key": "InstanceIds", "values": ["i-2"]}]},
    ],
)
def test_update_keeps_cron_only_fields_without_a_rate_schedule(overrides):
    request = run_update(
        current_association(ScheduleExpression="cron(0 0 * * ? *)", **CRON_ONLY_FIELDS),
        **overrides,
    )

    assert {key: request[key] for key in CRON_ONLY_FIELDS} == CRON_ONLY_FIELDS


def test_check_mode_rate_schedule_predicts_cleared_cron_only_fields():
    client = Mock()
    result = run_present(
        client,
        FakeModule(params(schedule_expression="rate(2 hours)"), check_mode=True),
        current_association(ScheduleExpression="cron(0 0 * * ? *)", **CRON_ONLY_FIELDS),
    )

    assert result.values["changed"]
    # DescribeAssociation returns a cleared ApplyOnlyAtCronInterval as false and omits a cleared Duration and offset.
    assert result.values["association"]["apply_only_at_cron_interval"] is False
    assert not {"duration", "schedule_offset"} & set(result.values["association"])
    client.update_association.assert_not_called()


def test_rate_schedule_is_unchanged_after_cron_only_fields_are_cleared():
    client = Mock()
    result = run_present(
        client,
        FakeModule(params(schedule_expression="rate(2 hours)")),
        current_association(ScheduleExpression="rate(2 hours)"),
    )

    assert not result.values["changed"]
    client.update_association.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_resulting_tag_limit_fails_before_updating_the_association(check_mode):
    client = Mock()
    existing_tags = [{"Key": "aws:reserved", "Value": ""}]
    existing_tags += [{"Key": f"old{index}", "Value": ""} for index in range(50)]
    module = FakeModule(
        params(purge_tags=False, schedule_expression="rate(2 hours)", tags={"new": ""}),
        check_mode=check_mode,
    )
    with patch.object(plugin, "association_with_tags", side_effect=lambda *args: dict(args[2], Tags=existing_tags)):
        result = run_present(client, module, current_association())

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "The resulting AWS Systems Manager association tags must contain at most 50 entries"
    assert result.values.get("changed", False) is False
    client.update_association.assert_not_called()
    client.add_tags_to_resource.assert_not_called()


def test_resulting_50_tags_update_the_association():
    client = Mock(
        update_association=Mock(return_value={"AssociationDescription": current_association(AssociationVersion="2")}),
    )
    existing_tags = [{"Key": "aws:reserved", "Value": ""}]
    existing_tags += [{"Key": f"old{index}", "Value": ""} for index in range(49)]
    module = FakeModule(params(purge_tags=False, schedule_expression="rate(2 hours)", tags={"new": ""}))
    with patch.object(plugin, "association_with_tags", side_effect=lambda *args: dict(args[2], Tags=existing_tags)):
        result = run_present(client, module, current_association())

    assert isinstance(result, ModuleExit)
    assert result.values["changed"] is True
    client.update_association.assert_called_once()
    client.add_tags_to_resource.assert_called_once_with(
        ResourceType="Association",
        ResourceId="association-1",
        Tags=[{"Key": "new", "Value": ""}],
        aws_retry=True,
    )
    client.remove_tags_from_resource.assert_not_called()
