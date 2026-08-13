# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import Mock

from ansible_collections.linuxhq.aws.plugins.module_utils.ses import get_account


class SesTests(TestCase):
    def test_account_response_is_normalized_without_metadata(self):
        client = Mock(
            get_account=Mock(
                return_value={
                    "ProductionAccessEnabled": True,
                    "ResponseMetadata": {"RequestId": "request"},
                }
            )
        )

        self.assertEqual(get_account(client, Mock()), {"production_access_enabled": True})
        client.get_account.assert_called_once_with(aws_retry=True)
