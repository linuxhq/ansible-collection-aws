from unittest.mock import Mock, call, patch

import pytest
from botocore.loaders import Loader
from botocore.waiter import Waiter, WaiterModel

from ansible_collections.linuxhq.aws.plugins.module_utils import tags
from ansible_collections.linuxhq.aws.plugins.modules import ec2_vpc_prefix_list as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)

OWNER = "123456789012"


def test_sdk_validation_starts_with_lookup_only():
    module = Mock(
        params={
            "address_family": "IPv4",
            "entries": [{"cidr": "10.0.0.0/8"}],
            "name": "main",
            "purge_tags": True,
            "state": "present",
            "tags": {},
            "wait": False,
            "wait_delay": 1,
            "wait_timeout": 60,
        },
        client=Mock(return_value=Mock()),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "get_aws_account_id", return_value=OWNER),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once_with(module.client.return_value, module, OWNER)

    require.assert_called_once_with(
        module,
        module.client.return_value,
        "EC2",
        {
            "describe_managed_prefix_lists": (
                "Filters",
                "MaxResults",
                "NextToken",
            )
        },
    )


def test_delete_tolerates_prefix_list_disappearing():
    client = Mock()
    client.delete_managed_prefix_list.side_effect = plugin.ClientError(
        {"Error": {"Code": "InvalidPrefixListID.NotFound", "Message": "gone"}},
        "DeleteManagedPrefixList",
    )
    module = FakeModule({"name": "main", "wait": True})
    with (
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "wait_for_prefix_list_state") as wait,
    ):
        plugin.delete_prefix_list(client, module, "pl-1")

    require.assert_called_once_with(
        module,
        client,
        "EC2",
        {"delete_managed_prefix_list": ("PrefixListId",)},
    )
    wait.assert_not_called()


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["required_if"] == [("state", "present", ["entries"])]


def test_entries_are_normalized_and_sorted():
    assert plugin.comparable_entries(
        [
            {"Cidr": "192.0.2.0/24", "Description": None},
            {"Cidr": "10.0.0.0/8", "Description": "private"},
            {"Cidr": "198.51.100.0/24", "Description": ""},
        ]
    ) == [
        {"cidr": "10.0.0.0/8", "description": "private"},
        {"cidr": "192.0.2.0/24"},
        {"cidr": "198.51.100.0/24"},
    ]


def test_entry_changes_include_current_prefix_list_version():
    client = Mock()
    client.modify_managed_prefix_list.return_value = {
        "PrefixList": {
            "AddressFamily": "IPv4",
            "MaxEntries": 2,
            "OwnerId": "123456789012",
            "PrefixListId": "pl-1",
            "PrefixListName": "main",
            "State": "modify-in-progress",
            "Version": 4,
        }
    }
    module = FakeModule({"name": "main"})
    with patch.object(plugin, "require_client_methods") as require:
        plugin.modify_prefix_list(
            client,
            module,
            {"PrefixListId": "pl-1", "Version": 3},
            add_entries=[{"cidr": "192.0.2.0/24"}],
        )

    require.assert_called_once_with(
        module,
        client,
        "EC2",
        {
            "modify_managed_prefix_list": (
                "PrefixListId",
                "CurrentVersion",
                "AddEntries",
            )
        },
        changed=False,
    )
    client.modify_managed_prefix_list.assert_called_once_with(
        AddEntries=[{"Cidr": "192.0.2.0/24"}],
        CurrentVersion=3,
        PrefixListId="pl-1",
        aws_retry=True,
    )


def test_create_without_wait_returns_the_create_response():
    client = Mock(
        create_managed_prefix_list=Mock(
            return_value={
                "PrefixList": {
                    "AddressFamily": "IPv4",
                    "MaxEntries": 1,
                    "OwnerId": "123456789012",
                    "PrefixListId": "pl-new",
                    "PrefixListName": "main",
                    "State": "create-in-progress",
                    "Version": 1,
                }
            }
        )
    )
    module = FakeModule({"name": "main", "tags": None, "wait": False})
    entries = [{"cidr": "192.0.2.0/24"}]
    with (
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "get_current") as get_current,
    ):
        result = plugin.create_prefix_list(
            client,
            module,
            OWNER,
            {
                "address_family": "IPv4",
                "max_entries": 1,
                "prefix_list_name": "main",
            },
            entries,
        )

    require.assert_called_once_with(
        module,
        client,
        "EC2",
        {
            "create_managed_prefix_list": (
                "AddressFamily",
                "MaxEntries",
                "PrefixListName",
                "Entries",
            )
        },
    )
    assert result == (
        {
            "AddressFamily": "IPv4",
            "MaxEntries": 1,
            "OwnerId": "123456789012",
            "PrefixListId": "pl-new",
            "PrefixListName": "main",
            "State": "create-in-progress",
            "Version": 1,
        },
        entries,
    )
    get_current.assert_not_called()


def test_create_rejects_malformed_response():
    client = Mock(create_managed_prefix_list=Mock(return_value={"PrefixList": None}))
    module = FakeModule({"name": "main", "tags": None, "wait": False})
    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail),
    ):
        plugin.create_prefix_list(
            client,
            module,
            OWNER,
            {
                "address_family": "IPv4",
                "max_entries": 1,
                "prefix_list_name": "main",
            },
            [{"cidr": "192.0.2.0/24"}],
        )


def test_additive_check_mode_preserves_unmanaged_tags():
    current = {
        "AddressFamily": "IPv4",
        "MaxEntries": 1,
        "PrefixListId": "pl-1",
        "PrefixListName": "main",
        "Tags": [
            {"Key": "keep", "Value": "yes"},
            {"Key": "managed", "Value": "old"},
        ],
    }
    entries = [{"Cidr": "10.0.0.0/8"}]
    module = FakeModule(
        {
            "address_family": "IPv4",
            "entries": [{"cidr": "10.0.0.0/8"}],
            "name": "main",
            "purge_tags": False,
            "tags": {"managed": "new"},
            "wait": False,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "get_current", return_value=(current, entries)),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module, OWNER)

    assert raised.value.values["prefix_list"]["tags"] == {"keep": "yes", "managed": "new"}


def test_entry_replacement_is_one_request_before_shrinking():
    client = Mock()
    module = FakeModule(
        {
            "address_family": "IPv4",
            "entries": [{"cidr": "192.0.2.0/24"}],
            "max_entries": 1,
            "name": "main",
            "purge_tags": True,
            "tags": None,
            "wait": False,
        }
    )
    initial = {
        "AddressFamily": "IPv4",
        "MaxEntries": 2,
        "PrefixListId": "pl-1",
        "PrefixListName": "main",
        "Version": 1,
    }
    replaced = dict(initial, Version=2)
    resized = dict(initial, MaxEntries=1, Version=3)
    with (
        patch.object(
            plugin,
            "get_current",
            return_value=(initial, [{"Cidr": "10.0.0.0/8"}, {"Cidr": "172.16.0.0/12"}]),
        ),
        patch.object(plugin, "describe_prefix_list", return_value=replaced),
        patch.object(plugin, "modify_prefix_list", return_value=resized) as modify,
        patch.object(plugin, "wait_for_ready_state") as wait_for_ready_state,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert raised.value.values["changed"]
    assert modify.call_args_list == [
        call(
            client,
            module,
            initial,
            changed=False,
            add_entries=[{"cidr": "192.0.2.0/24"}],
            remove_entries=[{"cidr": "10.0.0.0/8"}, {"cidr": "172.16.0.0/12"}],
        ),
        call(client, module, replaced, changed=True, max_entries=1),
    ]
    wait_for_ready_state.assert_called_once_with(client, module, "pl-1", changed=True)
    assert raised.value.values["prefix_list"]["entries"] == [{"cidr": "192.0.2.0/24"}]


def test_present_entries_must_be_nonempty_and_unique():
    base = {"address_family": "IPv4", "state": "present", "tags": None}
    cases = [
        (
            dict(base, entries=[]),
            "entries must contain at least one item when state=present",
        ),
        (
            dict(base, entries=[{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}], max_entries=1),
            "max_entries must be at least the number of entries",
        ),
        (
            dict(
                base,
                entries=[{"cidr": "10.0.0.0/8"}, {"cidr": "10.0.0.0/8"}],
            ),
            "entries[].cidr values must be unique",
        ),
        (
            dict(base, entries=[{"cidr": "not-a-cidr"}]),
            "entries[].cidr must be a valid CIDR: not-a-cidr",
        ),
        (
            dict(base, entries=[{"cidr": "2001:db8::/32"}]),
            "entries[].cidr must match address_family IPv4: 2001:db8::/32",
        ),
        (
            dict(
                base,
                entries=[{"cidr": "192.0.2.0/24", "description": "d" * 256}],
            ),
            "entries[].description must contain at most 255 characters",
        ),
    ]
    for params, message in cases:
        assert_module_rejects(plugin, params, message)


def test_present_waits_for_an_existing_modification_and_rechecks():
    client = Mock()
    module = FakeModule(
        {
            "address_family": "IPv4",
            "entries": [{"cidr": "10.0.0.0/8"}],
            "max_entries": 1,
            "name": "main",
            "purge_tags": True,
            "tags": None,
            "wait": False,
        }
    )
    transitioning = {
        "AddressFamily": "IPv4",
        "MaxEntries": 2,
        "PrefixListId": "pl-1",
        "PrefixListName": "main",
        "State": "modify-in-progress",
    }
    ready = dict(transitioning, MaxEntries=1, State="modify-complete")
    with (
        patch.object(
            plugin,
            "get_current",
            side_effect=[
                (transitioning, [{"Cidr": "10.0.0.0/8"}]),
                (ready, [{"Cidr": "10.0.0.0/8"}]),
            ],
        ),
        patch.object(plugin, "wait_for_ready_state") as wait_for_ready_state,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    wait_for_ready_state.assert_called_once_with(client, module, "pl-1")
    assert not raised.value.values["changed"]
    client.modify_managed_prefix_list.assert_not_called()


def test_absent_does_not_repeat_an_in_progress_delete():
    client = Mock()
    module = FakeModule({"name": "main", "wait": False})
    current = {
        "PrefixListId": "pl-1",
        "PrefixListName": "main",
        "State": "delete-in-progress",
    }
    with (
        patch.object(
            plugin,
            "get_customer_managed_prefix_list_by_name",
            return_value=current,
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module, OWNER)

    assert not raised.value.values["changed"]
    client.delete_managed_prefix_list.assert_not_called()


def test_lookup_ignores_delete_complete_tombstones():
    module = FakeModule({"name": "main"})
    active = {
        "AddressFamily": "IPv4",
        "MaxEntries": 1,
        "OwnerId": "123456789012",
        "PrefixListId": "pl-new",
        "PrefixListName": "main",
        "State": "create-complete",
        "Version": 1,
    }
    with patch.object(
        plugin,
        "query_list",
        return_value=[
            {
                "AddressFamily": "IPv4",
                "MaxEntries": 1,
                "OwnerId": "123456789012",
                "PrefixListId": "pl-old",
                "PrefixListName": "main",
                "State": "delete-complete",
                "Version": 1,
            },
            active,
        ],
    ):
        assert plugin.get_customer_managed_prefix_list_by_name(Mock(), module, OWNER) == active


def test_lookup_rejects_malformed_response():
    module = FakeModule({"name": "main"})
    with (
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail),
    ):
        plugin.get_customer_managed_prefix_list_by_name(Mock(), module, OWNER)


def test_entries_reject_malformed_response():
    module = FakeModule({"name": "main"})
    with (
        patch.object(
            plugin,
            "get_customer_managed_prefix_list_by_name",
            return_value={"PrefixListId": "pl-1", "State": "create-complete"},
        ),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail),
    ):
        plugin.get_current(Mock(), module, OWNER)


@pytest.mark.parametrize("check_mode", [False, True])
def test_address_family_change_preserves_prefix_list(check_mode):
    module = FakeModule(
        {
            "address_family": "IPv6",
            "entries": [{"cidr": "2001:db8::/32"}],
            "name": "main",
            "purge_tags": True,
            "tags": {"new": "value"},
            "wait": False,
        },
        check_mode=check_mode,
    )
    current = {
        "AddressFamily": "IPv4",
        "MaxEntries": 1,
        "PrefixListId": "pl-old",
        "PrefixListName": "main",
        "Version": 1,
    }
    client = Mock()
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "delete_prefix_list") as delete,
        patch.object(plugin, "create_prefix_list") as create,
        patch.object(plugin, "modify_prefix_list") as modify,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert "address_family cannot be changed" in raised.value.values["msg"]
    delete.assert_not_called()
    create.assert_not_called()
    modify.assert_not_called()
    assert not client.mock_calls


def test_update_mismatch_preserves_prefix_list():
    module = FakeModule(
        {
            "address_family": "IPv4",
            "entries": [{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}],
            "name": "main",
            "purge_tags": True,
            "tags": None,
            "wait": True,
        }
    )
    current = {
        "AddressFamily": "IPv4",
        "MaxEntries": 1,
        "PrefixListId": "pl-old",
        "PrefixListName": "main",
        "Version": 1,
    }
    grown = dict(current, MaxEntries=2, Version=2)
    client = Mock()
    with (
        patch.object(
            plugin,
            "get_current",
            side_effect=[(current, [{"Cidr": "10.0.0.0/8"}]), (current, [{"Cidr": "10.0.0.0/8"}])],
        ),
        patch.object(plugin, "describe_prefix_list", return_value=grown),
        patch.object(plugin, "wait_for_ready_state"),
        patch.object(plugin, "delete_prefix_list") as delete,
        patch.object(plugin, "create_prefix_list") as create,
        patch.object(plugin, "modify_prefix_list") as modify,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert "has not been deleted" in raised.value.values["msg"]
    assert modify.call_args_list == [
        call(client, module, current, changed=False, max_entries=2),
        call(client, module, grown, changed=True, add_entries=[{"cidr": "192.0.2.0/24"}], remove_entries=None),
    ]
    delete.assert_not_called()
    create.assert_not_called()


@pytest.mark.parametrize(
    "name,state",
    [("managed_prefix_list_ready", "restore-complete"), ("managed_prefix_list_deleted", "delete-complete")],
)
def test_prefix_list_waiter_accepts_completed_state(name, state):
    config = WaiterModel({"version": 2, "waiters": plugin.EC2_WAITER_MODEL_DATA}).get_waiter(name)
    operation = Mock(return_value={"PrefixLists": [{"State": state}]})
    waiter = Waiter(name, config, operation)
    waiter.wait(PrefixListIds=["pl-1"], WaiterConfig={"Delay": 0, "MaxAttempts": 1})


@pytest.mark.parametrize("state", ["create-in-progress", "modify-in-progress", "restore-in-progress"])
@pytest.mark.parametrize("wait_enabled,check_mode", [(True, False), (False, False), (True, True)])
def test_matching_prefix_list_readiness(state, wait_enabled, check_mode):
    module = FakeModule(
        {
            "name": "example",
            "address_family": "IPv4",
            "entries": [{"cidr": "10.0.0.0/8"}],
            "tags": None,
            "purge_tags": True,
            "wait": wait_enabled,
        },
        check_mode=check_mode,
    )
    current = {
        "PrefixListId": "pl-1",
        "PrefixListName": "example",
        "AddressFamily": "IPv4",
        "MaxEntries": 1,
        "Version": 1,
        "State": state,
    }
    entries = [{"Cidr": "10.0.0.0/8"}]
    ready = dict(current, State="modify-complete")
    client = Mock()
    with (
        patch.object(plugin, "get_current", side_effect=[(current, entries), (ready, entries)]),
        patch.object(plugin, "wait_for_ready_state") as wait,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is False
    assert client.mock_calls == []
    if wait_enabled and not check_mode:
        wait.assert_called_once_with(client, module, "pl-1")
        assert result.value.values["prefix_list"]["state"] == "modify-complete"
    else:
        wait.assert_not_called()
        assert result.value.values["prefix_list"]["state"] == state


def test_add_entries_without_wait_returns_modified_version_and_state():
    current = {
        "PrefixListId": "pl-1",
        "PrefixListName": "example",
        "AddressFamily": "IPv4",
        "MaxEntries": 2,
        "OwnerId": "123456789012",
        "Version": 3,
        "State": "modify-complete",
    }
    updated = dict(current, Version=4, State="modify-in-progress")
    client = Mock(modify_managed_prefix_list=Mock(return_value={"PrefixList": updated}))
    module = FakeModule(
        {
            "name": "example",
            "address_family": "IPv4",
            "entries": [{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}],
            "tags": None,
            "purge_tags": True,
            "wait": False,
        }
    )
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_ready_state") as wait,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is True
    assert result.value.values["prefix_list"]["version"] == 4
    assert result.value.values["prefix_list"]["state"] == "modify-in-progress"
    client.modify_managed_prefix_list.assert_called_once_with(
        PrefixListId="pl-1", CurrentVersion=3, AddEntries=[{"Cidr": "192.0.2.0/24"}], aws_retry=True
    )
    wait.assert_not_called()


def prefix_list(**overrides):
    return dict(
        {
            "AddressFamily": "IPv4",
            "MaxEntries": 1,
            "OwnerId": OWNER,
            "PrefixListId": "pl-1",
            "PrefixListName": "main",
            "State": "modify-complete",
            "Version": 1,
        },
        **overrides,
    )


def present_params(entries, **overrides):
    return dict(
        {
            "address_family": "IPv4",
            "entries": entries,
            "name": "main",
            "purge_tags": True,
            "tags": None,
            "wait": False,
        },
        **overrides,
    )


def cidrs(start, count):
    return [{"cidr": f"10.{index // 256}.{index % 256}.0/24"} for index in range(start, start + count)]


def test_description_change_is_one_addition_without_removal():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8", "description": "new"}]))
    current = prefix_list()
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8", "Description": "old"}])),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(Version=2)) as modify,
        patch.object(plugin, "wait_for_ready_state") as wait,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is True
    modify.assert_called_once_with(
        client,
        module,
        current,
        changed=False,
        add_entries=[{"cidr": "10.0.0.0/8", "description": "new"}],
        remove_entries=None,
    )
    wait.assert_not_called()


def test_max_entries_headroom_avoids_resizing():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}], max_entries=10))
    current = prefix_list(MaxEntries=10)
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(MaxEntries=10, Version=2)) as modify,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module, OWNER)

    modify.assert_called_once_with(
        client, module, current, changed=False, add_entries=[{"cidr": "192.0.2.0/24"}], remove_entries=None
    )


def test_empty_description_matches_an_entry_without_description():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8", "description": ""}]))
    with (
        patch.object(plugin, "get_current", return_value=(prefix_list(), [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "modify_prefix_list") as modify,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is False
    modify.assert_not_called()


def test_empty_description_clears_a_description_without_sending_it():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8", "description": ""}]))
    current = prefix_list()
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8", "Description": "old"}])),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(Version=2)) as modify,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is True
    modify.assert_called_once_with(
        client, module, current, changed=False, add_entries=[{"cidr": "10.0.0.0/8"}], remove_entries=None
    )


def test_omitted_max_entries_never_shrinks_an_existing_prefix_list():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}]))
    current = prefix_list(MaxEntries=10)
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "modify_prefix_list") as modify,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is False
    assert result.value.values["prefix_list"]["max_entries"] == 10
    modify.assert_not_called()


def test_omitted_max_entries_keeps_headroom_when_entries_change():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}]))
    current = prefix_list(MaxEntries=10)
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(MaxEntries=10, Version=2)) as modify,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module, OWNER)

    modify.assert_called_once_with(
        client, module, current, changed=False, add_entries=[{"cidr": "192.0.2.0/24"}], remove_entries=None
    )


def test_omitted_max_entries_grows_an_existing_prefix_list_to_fit_entries():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}]))
    current = prefix_list(MaxEntries=1)
    grown = prefix_list(MaxEntries=2, Version=2)
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "describe_prefix_list", return_value=grown),
        patch.object(plugin, "modify_prefix_list", side_effect=[grown, prefix_list(MaxEntries=2, Version=3)]) as modify,
        patch.object(plugin, "wait_for_ready_state"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is True
    assert modify.call_args_list[0] == call(client, module, current, changed=False, max_entries=2)


def test_explicit_max_entries_shrinks_an_existing_prefix_list():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}], max_entries=1))
    current = prefix_list(MaxEntries=10)
    with (
        patch.object(plugin, "get_current", return_value=(current, [{"Cidr": "10.0.0.0/8"}])),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(MaxEntries=1, Version=2)) as modify,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert result.value.values["changed"] is True
    modify.assert_called_once_with(client, module, current, changed=False, max_entries=1)


def test_omitted_max_entries_creates_with_the_number_of_entries():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}, {"cidr": "192.0.2.0/24"}]))
    created = prefix_list(MaxEntries=2)
    with (
        patch.object(plugin, "get_current", return_value=(None, None)),
        patch.object(plugin, "create_prefix_list", return_value=(created, [])) as create,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module, OWNER)

    assert create.call_args.args[3]["max_entries"] == 2


@pytest.mark.parametrize("max_entries", [None, 400])
def test_large_replacement_never_needs_more_than_max_entries(max_entries):
    current_entries = cidrs(0, 150)
    desired_entries = cidrs(150, 150)
    client = Mock()
    module = FakeModule(present_params(desired_entries, wait=True, max_entries=max_entries))
    current = prefix_list(MaxEntries=150)
    final = prefix_list(MaxEntries=max_entries or 150, Version=7)
    with (
        patch.object(
            plugin,
            "get_current",
            side_effect=[
                (current, [{"Cidr": entry["cidr"]} for entry in current_entries]),
                (final, [{"Cidr": entry["cidr"]} for entry in desired_entries]),
            ],
        ),
        patch.object(plugin, "describe_prefix_list", return_value=current),
        patch.object(plugin, "modify_prefix_list", return_value=final) as modify,
        patch.object(plugin, "wait_for_ready_state"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    steps = [call.kwargs for call in modify.call_args_list]
    sizes = [step["max_entries"] for step in steps if "max_entries" in step]
    assert max(sizes, default=150) == (max_entries or 150)
    entry_steps = [step for step in steps if "max_entries" not in step]
    assert [len(step.get("remove_entries") or []) for step in entry_steps] == [100, 50, 0, 0]
    assert [len(step.get("add_entries") or []) for step in entry_steps] == [0, 0, 100, 50]
    assert result.value.values["changed"] is True


def test_create_adds_entries_beyond_one_request_in_batches():
    entries = cidrs(0, 150)
    created = prefix_list(MaxEntries=150, State="create-in-progress")
    client = Mock(create_managed_prefix_list=Mock(return_value={"PrefixList": created}))
    module = FakeModule({"name": "main", "tags": None, "wait": False})
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_ready_state") as wait,
        patch.object(plugin, "describe_prefix_list", return_value=prefix_list(MaxEntries=150)),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(MaxEntries=150, Version=2)) as modify,
    ):
        plugin.create_prefix_list(
            client,
            module,
            OWNER,
            {"address_family": "IPv4", "max_entries": 150, "prefix_list_name": "main"},
            plugin.comparable_entries(entries),
        )

    assert len(client.create_managed_prefix_list.call_args.kwargs["Entries"]) == 100
    assert len(modify.call_args.kwargs["add_entries"]) == 50
    assert modify.call_args.kwargs["changed"] is True
    wait.assert_called_once_with(client, module, "pl-1", changed=True)


@pytest.mark.parametrize(
    "name,state",
    [
        ("managed_prefix_list_ready", "create-failed"),
        ("managed_prefix_list_ready", "modify-failed"),
        ("managed_prefix_list_ready", "restore-failed"),
        ("managed_prefix_list_ready", "delete-in-progress"),
        ("managed_prefix_list_ready", "delete-complete"),
        ("managed_prefix_list_ready", "delete-failed"),
        ("managed_prefix_list_deleted", "delete-failed"),
    ],
)
def test_prefix_list_waiter_stops_on_failed_state(name, state):
    config = WaiterModel({"version": 2, "waiters": plugin.EC2_WAITER_MODEL_DATA}).get_waiter(name)
    operation = Mock(return_value={"PrefixLists": [{"State": state}]})
    waiter = Waiter(name, config, operation)
    with pytest.raises(plugin.BotoCoreError, match="terminal failure state"):
        waiter.wait(PrefixListIds=["pl-1"], WaiterConfig={"Delay": 0, "MaxAttempts": 5})

    operation.assert_called_once()


def test_ready_waiter_handles_every_prefix_list_state():
    shapes = Loader().load_service_model("ec2", "service-2")["shapes"]
    acceptors = plugin.EC2_WAITER_MODEL_DATA["managed_prefix_list_ready"]["acceptors"]

    assert {acceptor["expected"] for acceptor in acceptors} == set(shapes["PrefixListState"]["enum"])


def test_ready_wait_fails_immediately_when_the_prefix_list_is_deleting():
    module = FakeModule({"wait_delay": 1, "wait_timeout": 600})
    client = Mock()
    client.describe_managed_prefix_lists.return_value = {
        "PrefixLists": [{"PrefixListId": "pl-1", "State": "delete-in-progress"}]
    }
    waiter = Waiter(
        "managed_prefix_list_ready",
        WaiterModel({"version": 2, "waiters": plugin.EC2_WAITER_MODEL_DATA}).get_waiter("managed_prefix_list_ready"),
        client.describe_managed_prefix_lists,
    )
    with (
        patch.object(plugin, "require_client_methods"),
        patch("botocore.waiter.time.sleep") as sleep,
        patch(
            "ansible_collections.linuxhq.aws.plugins.module_utils.wait.BaseWaiterFactory.get_waiter",
            return_value=waiter,
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_ready_state(client, module, "pl-1", changed=True)

    client.describe_managed_prefix_lists.assert_called_once_with(PrefixListIds=["pl-1"])
    sleep.assert_not_called()
    assert raised.value.values["msg"] == "Unable to wait for EC2 VPC managed prefix list pl-1 to become ready"
    assert raised.value.values["changed"] is True


def test_create_failed_prefix_list_is_not_modified():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}]))
    with (
        patch.object(plugin, "get_current", return_value=(prefix_list(State="create-failed"), [])),
        patch.object(plugin, "modify_prefix_list") as modify,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert "failed to create" in raised.value.values["msg"]
    modify.assert_not_called()


def test_lookup_ignores_prefix_lists_owned_by_other_accounts():
    own = prefix_list()
    shared = prefix_list(OwnerId="210987654321", PrefixListId="pl-shared")
    aws_managed = prefix_list(OwnerId="AWS", PrefixListId="pl-aws")
    with patch.object(plugin, "query_list", return_value=[shared, aws_managed, own]):
        assert plugin.get_customer_managed_prefix_list_by_name(Mock(), FakeModule({"name": "main"}), OWNER) == own

    with patch.object(plugin, "query_list", return_value=[shared]):
        assert plugin.get_customer_managed_prefix_list_by_name(Mock(), FakeModule({"name": "main"}), OWNER) is None


def test_lookup_skips_unversioned_aws_managed_prefix_lists_before_validation():
    own = prefix_list()
    aws_managed = {
        "AddressFamily": "IPv4",
        "OwnerId": "AWS",
        "PrefixListId": "pl-02cd2c6b",
        "PrefixListName": "main",
        "State": "create-complete",
        "Tags": [],
    }
    with patch.object(plugin, "query_list", return_value=[aws_managed, own]):
        assert plugin.get_customer_managed_prefix_list_by_name(Mock(), FakeModule({"name": "main"}), OWNER) == own


def test_lookup_validates_owned_prefix_lists():
    with (
        patch.object(plugin, "query_list", return_value=[prefix_list(Version=None)]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_customer_managed_prefix_list_by_name(Mock(), FakeModule({"name": "main"}), OWNER)

    assert raised.value.values["msg"] == "EC2 returned an invalid managed prefix list"


@pytest.mark.parametrize(
    ("waiter_name", "target_state"),
    [("managed_prefix_list_ready", "ready"), ("managed_prefix_list_deleted", "deleted")],
)
def test_wait_failure_names_target_state(waiter_name, target_state):
    module = FakeModule({})
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "run_waiter") as run_waiter,
    ):
        plugin.wait_for_prefix_list_state(Mock(), module, "pl-1", waiter_name)

    assert (
        run_waiter.call_args.args[4] == f"Unable to wait for EC2 VPC managed prefix list pl-1 to become {target_state}"
    )


@pytest.mark.parametrize(("description", "changed"), [("new", True), ("old", False)])
def test_tag_failure_reports_whether_entries_were_modified(description, changed):
    client = Mock()
    client.create_tags.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalError", "Message": "failed"}}, "CreateTags"
    )
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8", "description": description}], tags={"Env": "test"}))
    with (
        patch.object(
            plugin, "get_current", return_value=(prefix_list(), [{"Cidr": "10.0.0.0/8", "Description": "old"}])
        ),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(Version=2)) as modify,
        patch.object(plugin, "require_client_methods"),
        patch.object(tags, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert raised.value.values["msg"] == "Unable to tag EC2 VPC managed prefix list pl-1"
    assert raised.value.values["changed"] is changed
    assert modify.called is changed


def failing_waiter(module, client, model_data, waiter_name, error_msg, changed=False, **kwargs):
    module.fail_json(changed=changed, msg=error_msg)


def test_wait_failure_after_create_reports_changed():
    client = Mock(create_managed_prefix_list=Mock(return_value={"PrefixList": prefix_list(State="create-in-progress")}))
    module = FakeModule(dict(present_params([{"cidr": "10.0.0.0/8"}], wait=True), wait_delay=1, wait_timeout=60))
    with (
        patch.object(plugin, "get_current", return_value=(None, None)),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module, OWNER)

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to wait for EC2 VPC managed prefix list pl-1 to become ready"


def test_wait_failure_before_any_change_reports_unchanged():
    module = FakeModule(dict(present_params([{"cidr": "10.0.0.0/8"}], wait=True), wait_delay=1, wait_timeout=60))
    with (
        patch.object(plugin, "get_current", return_value=(prefix_list(State="modify-in-progress"), [])),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), module, OWNER)

    assert raised.value.values["changed"] is False


def test_tag_deltas_after_update_without_wait_use_the_described_tags():
    client = Mock()
    tags = [{"Key": "Env", "Value": "test"}, {"Key": "Old", "Value": "x"}]
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}], tags={"Env": "test", "Team": "net"}))
    with (
        patch.object(plugin, "get_current", return_value=(prefix_list(Tags=tags), [{"Cidr": "192.0.2.0/24"}])),
        # ModifyManagedPrefixList may return the prefix list without its tags.
        patch.object(
            plugin, "modify_prefix_list", return_value=prefix_list(State="modify-in-progress", Tags=[], Version=2)
        ),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "reconcile_ec2_tags") as reconcile,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    reconcile.assert_called_once_with(
        module,
        client,
        ["pl-1"],
        {"Team": "net"},
        ["Old"],
        "EC2 VPC managed prefix list",
        changed=True,
        check_sdk=True,
    )
    assert result.value.values["prefix_list"]["tags"] == {"Env": "test", "Team": "net"}


def test_untagged_update_without_wait_keeps_the_described_tags():
    client = Mock()
    module = FakeModule(present_params([{"cidr": "10.0.0.0/8"}]))
    with (
        patch.object(
            plugin,
            "get_current",
            return_value=(prefix_list(Tags=[{"Key": "Env", "Value": "test"}]), [{"Cidr": "192.0.2.0/24"}]),
        ),
        patch.object(plugin, "modify_prefix_list", return_value=prefix_list(Version=2)),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "reconcile_ec2_tags") as reconcile,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module, OWNER)

    reconcile.assert_not_called()
    assert result.value.values["prefix_list"]["tags"] == {"Env": "test"}


@pytest.mark.parametrize("state", sorted(plugin.IN_PROGRESS_STATES))
def test_absent_waits_for_an_in_progress_prefix_list_before_deleting(state):
    client = Mock()
    module = FakeModule({"name": "main", "wait": False})
    with (
        patch.object(plugin, "get_customer_managed_prefix_list_by_name", return_value=prefix_list(State=state)),
        patch.object(plugin, "wait_for_ready_state") as wait,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module, OWNER)

    assert raised.value.values["changed"] is True
    wait.assert_called_once_with(client, module, "pl-1")
    client.delete_managed_prefix_list.assert_called_once_with(PrefixListId="pl-1", aws_retry=True)
