# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase

from ansible.errors import AnsibleLookupError
from ansible_collections.linuxhq.aws.plugins.lookup.ses_credential import LookupModule


class SesCredentialTests(TestCase):
    def test_known_smtp_password_vector(self):
        expected = ["BHlIeyDS4HKFlws/Wlu6WRChwO84ARb1Ju9h0cZWr4+3"]
        for region in ("us-east-1", " us-east-1 "):
            self.assertEqual(
                LookupModule().run(
                    [],
                    aws_secret_access_key="secret",
                    region=region,
                ),
                expected,
            )

    def test_rejects_missing_options_and_positional_terms(self):
        cases = (
            ({"aws_secret_access_key": "secret"}, "non-empty region="),
            (
                {"region": "us-east-1"},
                "non-empty aws_secret_access_key=",
            ),
            (
                {"aws_secret_access_key": "secret", "region": " "},
                "non-empty region=",
            ),
            (
                {"aws_secret_access_key": "", "region": "us-east-1"},
                "non-empty aws_secret_access_key=",
            ),
        )
        for kwargs, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                AnsibleLookupError, message
            ):
                LookupModule().run([], **kwargs)

        with self.assertRaisesRegex(AnsibleLookupError, "positional terms"):
            LookupModule().run(
                ["unexpected"],
                aws_secret_access_key="secret",
                region="us-east-1",
            )
