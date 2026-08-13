# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import sdk
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


class SdkTests(TestCase):
    def test_query_list_returns_requested_envelope(self):
        client = Mock()
        client.can_paginate.return_value = True
        with patch.object(
            sdk,
            "paginated_query_with_retries",
            return_value={"Items": [1, 2]},
        ) as query:
            result = sdk.query_list(
                Mock(), client, "list_items", "Items", "failed", Limit=2
            )

        self.assertEqual(result, [1, 2])
        query.assert_called_once_with(client, "list_items", Limit=2)

    def test_query_list_falls_back_for_non_pageable_marker_operations(self):
        for marker_name, response_marker_name in (
            ("Marker", "Marker"),
            ("Marker", "NextMarker"),
            ("NextMarker", "NextMarker"),
            ("NextToken", "NextToken"),
            ("marker", "marker"),
            ("nextMarker", "nextMarker"),
            ("nextToken", "nextToken"),
        ):
            with self.subTest(
                marker_name=marker_name, response_marker_name=response_marker_name
            ):
                client = Mock()
                client.can_paginate.return_value = False
                client.list_items.side_effect = [
                    {"Items": [1], response_marker_name: "next"},
                    {"Items": [2]},
                ]
                with patch.object(
                    sdk,
                    "get_boto3_client_method_parameters",
                    return_value=[marker_name],
                ):
                    result = sdk.query_list(
                        Mock(), client, "list_items", "Items", "failed", Limit=2
                    )

                self.assertEqual(result, [1, 2])
                client.list_items.assert_any_call(Limit=2, aws_retry=True)
                client.list_items.assert_any_call(
                    **{"Limit": 2, marker_name: "next", "aws_retry": True}
                )

    def test_query_list_rejects_repeated_manual_pagination_markers(self):
        client = Mock()
        client.can_paginate.return_value = False
        client.list_items.side_effect = [
            {"Items": [1], "NextMarker": "same"},
            {"Items": [2], "NextMarker": "same"},
        ]
        module = FakeModule({})
        with (
            patch.object(
                sdk,
                "get_boto3_client_method_parameters",
                return_value=["NextMarker"],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            sdk.query_list(module, client, "list_items", "Items", "unable to list")

        self.assertEqual(
            raised.exception.values["msg"],
            "unable to list: repeated pagination marker",
        )

    def test_query_list_rejects_truncated_response_without_marker(self):
        for truncated_name in ("IsTruncated", "isTruncated"):
            with self.subTest(truncated_name=truncated_name):
                client = Mock()
                client.can_paginate.return_value = False
                client.list_items.return_value = {
                    truncated_name: True,
                    "Items": [1],
                }
                module = FakeModule({})
                with (
                    patch.object(
                        sdk,
                        "get_boto3_client_method_parameters",
                        return_value=["Marker"],
                    ),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    sdk.query_list(
                        module, client, "list_items", "Items", "unable to list"
                    )

                self.assertEqual(
                    raised.exception.values["msg"],
                    "unable to list: truncated response without a marker",
                )

    def test_query_list_translates_sdk_errors(self):
        module = FakeModule({})
        error = ClientError({"Error": {"Code": "Failed", "Message": "no"}}, "List")
        with (
            patch.object(sdk, "paginated_query_with_retries", side_effect=error),
            self.assertRaises(ModuleFail) as raised,
        ):
            sdk.query_list(module, Mock(), "list_items", "Items", "unable to list")

        self.assertEqual(raised.exception.values["msg"], "unable to list")

    def test_requires_supported_client_parameters(self):
        module = FakeModule({})
        with patch.object(
            sdk,
            "get_boto3_client_method_parameters",
            return_value=["Name"],
        ):
            sdk.require_client_methods(
                module, Mock(), "Example", {"get_item": ("Name",)}
            )

        with (
            patch.object(
                sdk,
                "get_boto3_client_method_parameters",
                return_value=["Name"],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            sdk.require_client_methods(
                module, Mock(), "Example", {"get_item": ("Unsupported",)}
            )

        self.assertIn("parameter Unsupported", raised.exception.values["msg"])

    def test_reports_missing_client_operation(self):
        module = FakeModule({})
        with (
            patch.object(
                sdk,
                "get_boto3_client_method_parameters",
                side_effect=AttributeError,
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            sdk.require_client_methods(module, Mock(), "Example", {"missing": ()})

        self.assertEqual(
            raised.exception.values["msg"],
            "Installed botocore does not support Example missing",
        )
