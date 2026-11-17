from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_pool_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_documents_shape,
    assert_module_contract,
    documented_returns,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["owner", "pool_ids"]]
    assert "default" not in options["argument_spec"]["owner"]


def test_documented_returns_cover_the_sdk_shape():
    # Each pool is a DescribePools item with every member AWS sends.
    assert_documents_shape(documented_returns(plugin)["pools"]["contains"], "pinpoint-sms-voice-v2", "PoolInformation")


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


@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        (
            ["pool-1", "arn:aws:sms-voice:us-east-1:123456789012:pool/pool-1", "pool-2"],
            ["arn:aws:sms-voice:us-east-1:123456789012:pool/pool-1", "pool-2"],
        ),
        (
            ["arn:aws:sms-voice:us-east-1:123456789012:pool/pool-1", "pool-1"],
            ["arn:aws:sms-voice:us-east-1:123456789012:pool/pool-1"],
        ),
    ],
)
def test_ids_and_arns_of_one_resource_are_described_once(ids, expected):
    module = FakeModule({"filters": None, "max_results": None, "owner": None, "pool_ids": ids})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"Pools": []}) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert [query_call.kwargs for query_call in query.call_args_list] == [
        {"PoolIds": [identifier]} for identifier in expected
    ]


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


def test_more_than_five_ids_are_described_one_at_a_time():
    # Each ID is described in its own request, so the DescribePools limit of five IDs does not apply.
    pool_ids = [f"pool-{index}" for index in range(6)]
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule({"filters": None, "max_results": None, "owner": None, "pool_ids": pool_ids}, client=client)
    responses = [{"Pools": [{"PoolArn": f"arn:pool/{pool_id}", "PoolId": pool_id}]} for pool_id in pool_ids]
    responses += [{"OriginationIdentities": []} for _pool_id in pool_ids]
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=responses) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [item.kwargs["PoolIds"] for item in query.call_args_list[:6]] == [[pool_id] for pool_id in pool_ids]
    assert raised.value.values["pool_ids"] == pool_ids


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


POOL_ARN = "arn:aws:sms-voice:us-east-1:111111111111:pool/pool-1"


def test_origination_identities_use_the_pool_arn():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule(
        {"filters": None, "max_results": None, "owner": "SHARED", "pool_ids": None},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"PoolArn": POOL_ARN, "PoolId": "pool-1"}]),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"OriginationIdentities": [{"OriginationIdentity": "phone-1"}]},
        ) as paginate,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert paginate.call_args.kwargs["PoolId"] == POOL_ARN
    assert raised.value.values["pools"][0]["origination_identities"] == [{"origination_identity": "phone-1"}]


def test_pools_always_return_origination_identities_and_tags():
    client = Mock()
    client.list_tags_for_resource.return_value = {}
    module = FakeModule({"filters": None, "max_results": None, "owner": "SHARED", "pool_ids": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"PoolArn": POOL_ARN, "PoolId": "pool-1"}]),
        patch.object(plugin, "paginated_query_with_retries", return_value={}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    pool = raised.value.values["pools"][0]
    assert pool["origination_identities"] == []
    assert pool["tags"] == {}
