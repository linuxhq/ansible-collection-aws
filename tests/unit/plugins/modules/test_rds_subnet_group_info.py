from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import rds_subnet_group_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)

GROUP = {
    "DBSubnetGroupArn": "arn:aws:rds:us-east-1:1:subgrp:main",
    "DBSubnetGroupName": "main",
    "Subnets": [{"SubnetIdentifier": "subnet-1", "SubnetStatus": "Active"}],
    "VpcId": "vpc-1",
}


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"] == {"name": {"type": "str"}}


def test_name_is_forwarded_to_rds():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": []}))
    module = FakeModule({"name": "main"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "paginated_query_with_retries", return_value={"DBSubnetGroups": [GROUP]}) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert [call.args[3] for call in require.call_args_list] == [
        {"describe_db_subnet_groups": ("DBSubnetGroupName", "Marker", "MaxRecords")},
        {"list_tags_for_resource": ("ResourceName",)},
    ]
    assert query.call_args.args[1] == "describe_db_subnet_groups"
    assert query.call_args.kwargs == {"DBSubnetGroupName": "main"}


def test_tags_are_returned_with_key_case_preserved():
    client = Mock(
        list_tags_for_resource=Mock(
            return_value={"TagList": [{"Key": "Name", "Value": "main"}, {"Key": "CostCenter", "Value": "1"}]}
        )
    )
    module = FakeModule({"name": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"DBSubnetGroups": [GROUP]}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    group = raised.value.values["subnet_groups"][0]
    assert group["tags"] == {"Name": "main", "CostCenter": "1"}
    assert group["db_subnet_group_name"] == "main"
    assert group["subnets"][0]["subnet_identifier"] == "subnet-1"
    client.list_tags_for_resource.assert_called_once_with(ResourceName=GROUP["DBSubnetGroupArn"], aws_retry=True)


def test_group_deleted_before_tag_lookup_is_skipped():
    client = Mock()
    client.list_tags_for_resource.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameterValue", "Message": "Unable to find a subnet group"}},
        "ListTagsForResource",
    )
    module = FakeModule({"name": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"DBSubnetGroups": [GROUP]}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["subnet_groups"] == []


def test_empty_results_do_not_require_tag_lookup():
    module = FakeModule({"name": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "paginated_query_with_retries", return_value={"DBSubnetGroups": []}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["subnet_groups"] == []
    assert require.call_count == 1


def test_missing_named_group_returns_an_empty_list():
    error = ClientError(
        {"Error": {"Code": "DBSubnetGroupNotFoundFault", "Message": "missing"}}, "DescribeDBSubnetGroups"
    )
    module = FakeModule({"name": "missing"}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=error),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["subnet_groups"] == []


def test_malformed_response_fails_cleanly():
    for response in (None, {}, {"DBSubnetGroups": [None]}, {"DBSubnetGroups": [{}]}):
        module = FakeModule({"name": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "paginated_query_with_retries", return_value=response),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert (
            raised.value.values["msg"]
            == "Unable to describe AWS RDS DB subnet groups: AWS returned an invalid response"
        )
