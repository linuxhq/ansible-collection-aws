# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import sdk
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


def test_query_list_returns_requested_envelope():
    client = Mock()
    client.can_paginate.return_value = True
    with patch.object(sdk, "paginated_query_with_retries", return_value={"Items": [1, 2]}) as query:
        result = sdk.query_list(Mock(), client, "list_items", "Items", "failed", Limit=2)

    assert result == [1, 2]
    query.assert_called_once_with(client, "list_items", Limit=2)


def test_query_list_falls_back_for_non_pageable_marker_operations():
    for marker_name, response_marker_name in (
        ("Marker", "Marker"),
        ("Marker", "NextMarker"),
        ("NextMarker", "NextMarker"),
        ("NextToken", "NextToken"),
        ("marker", "marker"),
        ("nextMarker", "nextMarker"),
        ("nextToken", "nextToken"),
    ):
        client = Mock()
        client.can_paginate.return_value = False
        client.list_items.side_effect = [{"Items": [1], response_marker_name: "next"}, {"Items": [2]}]
        with (
            patch.object(sdk, "get_boto3_client_method_parameters", return_value=[marker_name]),
            patch.object(sdk, "get_client_method_output_members", return_value=[response_marker_name]),
        ):
            result = sdk.query_list(Mock(), client, "list_items", "Items", "failed", Limit=2)

        assert result == [1, 2]
        client.list_items.assert_any_call(Limit=2, aws_retry=True)
        client.list_items.assert_any_call(**{"Limit": 2, marker_name: "next", "aws_retry": True})


def test_query_list_rejects_repeated_manual_pagination_markers():
    client = Mock()
    client.can_paginate.return_value = False
    client.list_items.side_effect = [{"Items": [1], "NextMarker": "same"}, {"Items": [2], "NextMarker": "same"}]
    module = FakeModule({})
    with (
        patch.object(sdk, "get_boto3_client_method_parameters", return_value=["NextMarker"]),
        patch.object(sdk, "get_client_method_output_members", return_value=["NextMarker"]),
        pytest.raises(ModuleFail) as raised,
    ):
        sdk.query_list(module, client, "list_items", "Items", "unable to list")

    assert raised.value.values["msg"] == "unable to list: repeated pagination marker"


def test_query_list_rejects_truncated_response_without_marker():
    for truncated_name in ("IsTruncated", "isTruncated"):
        client = Mock()
        client.can_paginate.return_value = False
        client.list_items.return_value = {truncated_name: True, "Items": [1]}
        module = FakeModule({})
        with (
            patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Marker"]),
            patch.object(sdk, "get_client_method_output_members", return_value=["Marker", truncated_name]),
            pytest.raises(ModuleFail) as raised,
        ):
            sdk.query_list(module, client, "list_items", "Items", "unable to list")

        assert raised.value.values["msg"] == "unable to list: truncated response without a marker"


def test_query_list_ignores_echoed_request_marker():
    client = Mock()
    client.can_paginate.return_value = False
    client.list_items.side_effect = [
        {"Items": [1], "IsTruncated": True, "NextMarker": "page-2"},
        {"Items": [2], "Marker": "page-2", "IsTruncated": True, "NextMarker": "page-3"},
        {"Items": [3], "Marker": "page-3", "IsTruncated": False},
    ]
    with (
        patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Marker"]),
        patch.object(
            sdk, "get_client_method_output_members", return_value=["Items", "Marker", "IsTruncated", "NextMarker"]
        ),
    ):
        result = sdk.query_list(FakeModule({}), client, "list_items", "Items", "unable to list")

    assert result == [1, 2, 3]
    assert client.list_items.call_count == 3
    client.list_items.assert_any_call(Marker="page-2", aws_retry=True)
    client.list_items.assert_any_call(Marker="page-3", aws_retry=True)


def test_query_list_does_not_follow_echoed_marker_when_next_marker_is_missing():
    client = Mock()
    client.can_paginate.return_value = False
    client.list_items.return_value = {"Items": [1], "Marker": "page-2"}
    module = FakeModule({})
    with (
        patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Marker"]),
        patch.object(sdk, "get_client_method_output_members", return_value=["Items", "Marker", "NextMarker"]),
    ):
        result = sdk.query_list(module, client, "list_items", "Items", "unable to list")

    assert result == [1]
    client.list_items.assert_called_once_with(aws_retry=True)


def test_query_list_stops_when_response_is_not_truncated():
    for truncated_name, marker_name in (("IsTruncated", "Marker"), ("isTruncated", "marker")):
        client = Mock()
        client.can_paginate.return_value = False
        client.list_items.return_value = {"Items": [1], marker_name: "echoed", truncated_name: False}
        with (
            patch.object(sdk, "get_boto3_client_method_parameters", return_value=[marker_name]),
            patch.object(sdk, "get_client_method_output_members", return_value=[marker_name, truncated_name]),
        ):
            result = sdk.query_list(FakeModule({}), client, "list_items", "Items", "unable to list")

        assert result == [1]
        client.list_items.assert_called_once_with(aws_retry=True)


def test_reads_client_method_output_members():
    client = Mock()
    client.meta.method_to_api_mapping = {"list_items": "ListItems"}
    client.meta.service_model.operation_model.return_value.output_shape.members = {"Items": None, "NextMarker": None}

    assert sdk.get_client_method_output_members(client, "list_items") == ["Items", "NextMarker"]
    client.meta.service_model.operation_model.assert_called_once_with("ListItems")

    client.meta.service_model.operation_model.return_value.output_shape = None
    assert sdk.get_client_method_output_members(client, "list_items") == []


def test_query_list_translates_sdk_errors():
    module = FakeModule({})
    error = ClientError({"Error": {"Code": "Failed", "Message": "no"}}, "List")
    with patch.object(sdk, "paginated_query_with_retries", side_effect=error), pytest.raises(ModuleFail) as raised:
        sdk.query_list(module, Mock(), "list_items", "Items", "unable to list")

    assert raised.value.values["msg"] == "unable to list"


def test_requires_supported_client_parameters():
    module = FakeModule({})
    with patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Name"]):
        sdk.require_client_methods(module, Mock(), "Example", {"get_item": ("Name",)})

    with (
        patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Name"]),
        pytest.raises(ModuleFail) as raised,
    ):
        sdk.require_client_methods(module, Mock(), "Example", {"get_item": ("Unsupported",)})

    assert "parameter Unsupported" in raised.value.values["msg"]


def test_reports_missing_client_operation():
    module = FakeModule({})
    with (
        patch.object(sdk, "get_boto3_client_method_parameters", side_effect=AttributeError),
        pytest.raises(ModuleFail) as raised,
    ):
        sdk.require_client_methods(module, Mock(), "Example", {"missing": ()})

    assert raised.value.values["msg"] == "Installed botocore does not support Example missing"
