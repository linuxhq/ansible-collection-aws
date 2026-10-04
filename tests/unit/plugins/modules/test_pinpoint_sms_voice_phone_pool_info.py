from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_pool_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["owner", "pool_ids"]]
    assert "default" not in options["argument_spec"]["owner"]


def test_ids_do_not_send_the_implicit_owner():
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": None,
            "pool_ids": ["pool-1"],
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_args.kwargs == {"PoolIds": ["pool-1"]}


def test_rejects_nonpositive_max_results():
    module = FakeModule({"filters": None, "max_results": 0, "owner": "SELF", "pool_ids": None})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "max_results must be between 1 and 100"


def test_rejects_provider_list_limits():
    cases = [
        (
            {
                "filters": {str(index): "x" for index in range(21)},
                "max_results": None,
                "owner": None,
                "pool_ids": None,
            },
            "filters must contain at most 20 entries",
        ),
        (
            {
                "filters": None,
                "max_results": None,
                "owner": None,
                "pool_ids": [f"pool-{index}" for index in range(6)],
            },
            "pool_ids must contain at most 5 entries",
        ),
    ]
    for params, message in cases:
        module = FakeModule(params)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert raised.value.values["msg"] == message


def test_pools_are_enriched_with_identities_and_tags():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Name", "Value": "primary"}]}
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": "SELF",
            "pool_ids": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "query_list",
            return_value=[{"PoolArn": "arn:pool", "PoolId": "pool-1"}],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"OriginationIdentities": [{"OriginationIdentity": "phone-1"}]},
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    pool = raised.value.values["pools"][0]
    assert pool["origination_identities"][0]["origination_identity"] == "phone-1"
    assert pool["tags"] == {"Name": "primary"}
    assert require.call_args.args[3] == {
        "describe_pools": ("Owner", "MaxResults", "NextToken"),
        "list_pool_origination_identities": (
            "PoolId",
            "MaxResults",
            "NextToken",
        ),
        "list_tags_for_resource": ("ResourceArn",),
    }


def test_rejects_malformed_pool():
    module = FakeModule({"filters": None, "max_results": None, "owner": "SELF", "pool_ids": None})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"PoolArn": "arn:pool"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "malformed" in raised.value.values["msg"]


def test_rejects_malformed_origination_identities():
    module = FakeModule({"filters": None, "max_results": None, "owner": "SELF", "pool_ids": None})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"PoolId": "pool-1"}]),
        patch.object(plugin, "paginated_query_with_retries", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "malformed origination identities" in raised.value.values["msg"]


def test_rejects_malformed_tags():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": "invalid"}
    module = FakeModule(
        {"filters": None, "max_results": None, "owner": "SELF", "pool_ids": None},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"PoolArn": "arn:pool", "PoolId": "pool-1"}],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"OriginationIdentities": []},
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "malformed tags" in raised.value.values["msg"]
