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
        with patch.object(sdk, "get_boto3_client_method_parameters", return_value=[marker_name]):
            result = sdk.query_list(Mock(), client, "list_items", "Items", "failed", Limit=2)

        assert result == [1, 2]
        client.list_items.assert_any_call(Limit=2, aws_retry=True)
        client.list_items.assert_any_call(**{"Limit": 2, marker_name: "next", "aws_retry": True})


def test_query_list_rejects_repeated_manual_pagination_markers():
    client = Mock()
    client.can_paginate.return_value = False
    client.list_items.side_effect = [{"Items": [1], "NextMarker": "same"}, {"Items": [2], "NextMarker": "same"}]
    module = FakeModule({})
    with patch.object(sdk, "get_boto3_client_method_parameters", return_value=["NextMarker"]), pytest.raises(
        ModuleFail
    ) as raised:
        sdk.query_list(module, client, "list_items", "Items", "unable to list")

    assert raised.value.values["msg"] == "unable to list: repeated pagination marker"


def test_query_list_rejects_truncated_response_without_marker():
    for truncated_name in ("IsTruncated", "isTruncated"):
        client = Mock()
        client.can_paginate.return_value = False
        client.list_items.return_value = {truncated_name: True, "Items": [1]}
        module = FakeModule({})
        with patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Marker"]), pytest.raises(
            ModuleFail
        ) as raised:
            sdk.query_list(module, client, "list_items", "Items", "unable to list")

        assert raised.value.values["msg"] == "unable to list: truncated response without a marker"


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

    with patch.object(sdk, "get_boto3_client_method_parameters", return_value=["Name"]), pytest.raises(
        ModuleFail
    ) as raised:
        sdk.require_client_methods(module, Mock(), "Example", {"get_item": ("Unsupported",)})

    assert "parameter Unsupported" in raised.value.values["msg"]


def test_reports_missing_client_operation():
    module = FakeModule({})
    with patch.object(sdk, "get_boto3_client_method_parameters", side_effect=AttributeError), pytest.raises(
        ModuleFail
    ) as raised:
        sdk.require_client_methods(module, Mock(), "Example", {"missing": ()})

    assert raised.value.values["msg"] == "Installed botocore does not support Example missing"
