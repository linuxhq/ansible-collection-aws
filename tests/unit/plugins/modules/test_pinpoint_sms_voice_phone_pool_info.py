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
        patch.object(plugin, "paginated_query_with_retries", return_value={"Pools": []}) as query,
        patch.object(plugin, "query_list") as query_list,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_args.kwargs == {"PoolIds": ["pool-1"]}
    query_list.assert_not_called()


def test_missing_ids_are_omitted_from_results():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribePools",
    )
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": None,
            "pool_ids": ["pool-missing", "pool-1"],
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[
                missing,
                {"Pools": [{"PoolArn": "arn:pool", "PoolId": "pool-1"}]},
                {"OriginationIdentities": []},
            ],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [item.kwargs.get("PoolIds") for item in query.call_args_list[:2]] == [["pool-missing"], ["pool-1"]]
    assert raised.value.values["pool_ids"] == ["pool-1"]
    assert raised.value.values["changed"] is False


def test_only_missing_ids_return_empty_results():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribePools",
    )
    module = FakeModule({"filters": None, "max_results": None, "owner": None, "pool_ids": ["pool-missing"]})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=missing),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["pool_ids"] == []
    assert raised.value.values["pools"] == []


@pytest.mark.parametrize("response", [[], {"Pools": "invalid"}, {"Pools": None}])
def test_id_lookup_rejects_malformed_response(response):
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=response),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.describe_pools_by_id(FakeModule({}), Mock(), {"PoolIds": ["pool-1"]})

    assert raised.value.values["msg"] == "AWS returned malformed Pinpoint SMS Voice V2 pool data"


def test_empty_result_does_not_require_detail_operations():
    module = FakeModule({"filters": None, "max_results": None, "owner": "SELF", "pool_ids": None})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_count == 1
    assert require.call_args.args[3] == {"describe_pools": ("Owner", "MaxResults", "NextToken")}


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
    assert [item.args[3] for item in require.call_args_list] == [
        {"describe_pools": ("Owner", "MaxResults", "NextToken")},
        {
            "list_pool_origination_identities": (
                "PoolId",
                "MaxResults",
                "NextToken",
            ),
            "list_tags_for_resource": ("ResourceArn",),
        },
    ]


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
