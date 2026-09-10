# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import Mock

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    reconcile_ssm_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


class TagsTests(TestCase):
    def test_tag_limits_are_rejected(self):
        module = FakeModule({})
        for tags, message in (
            ({"one": "", "two": ""}, "tags must contain at most 1 entries"),
            (
                {"long": "v" * 257},
                "tag keys must contain 1 to 3 characters and values at most 256 characters",
            ),
        ):
            with self.subTest(message=message), self.assertRaises(ModuleFail) as raised:
                require_valid_tags(module, tags, 1, key_max=3)

            self.assertEqual(raised.exception.values["msg"], message)

    def test_tag_keys_and_values_are_normalized_for_map_apis(self):
        tags = {1: True, "count": 2}
        require_valid_tags(FakeModule({}), tags, 50)
        self.assertEqual(tags, {"1": "True", "count": "2"})

    def test_colliding_normalized_tag_keys_are_rejected(self):
        with self.assertRaises(ModuleFail) as raised:
            require_valid_tags(FakeModule({}), {1: "numeric", "1": "string"}, 50)

        self.assertEqual(
            raised.exception.values["msg"],
            "tag keys must be unique after string normalization",
        )

    def test_tag_deltas_do_not_mutate_source(self):
        resource = {
            "Arn": "arn:resource",
            "Tags": [{"Key": "old", "Value": "value"}],
        }

        updated = apply_tag_deltas(resource, {"new": "value"}, ["old"])

        self.assertEqual(updated["Tags"], [{"Key": "new", "Value": "value"}])
        self.assertEqual(resource["Tags"], [{"Key": "old", "Value": "value"}])

    def test_reconcile_arn_tags_only_calls_nonempty_operations(self):
        client = Mock()
        reconcile_arn_tags(Mock(), client, "arn:resource", {"new": "value"}, [], "resource")

        client.untag_resource.assert_not_called()
        client.tag_resource.assert_called_once_with(
            ResourceArn="arn:resource",
            Tags=[{"Key": "new", "Value": "value"}],
            aws_retry=True,
        )

    def test_reconcile_ssm_tags_uses_ssm_parameter_names(self):
        client = Mock()
        reconcile_ssm_tags(Mock(), client, "Document", "doc", {}, ["old"], "document")

        client.add_tags_to_resource.assert_not_called()
        client.remove_tags_from_resource.assert_called_once_with(
            ResourceType="Document",
            ResourceId="doc",
            TagKeys=["old"],
            aws_retry=True,
        )
