# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase

from ansible.errors import AnsibleLookupError, AnsibleRequiredOptionError
from ansible.plugins.loader import lookup_loader


class SesCredentialTests(TestCase):
    @staticmethod
    def run_lookup(terms=None, variables=None, **kwargs):
        lookup = lookup_loader.get("linuxhq.aws.ses_credential")
        return lookup.run(terms or [], variables=variables, **kwargs)

    def test_known_smtp_password_vector(self):
        expected = ["BHlIeyDS4HKFlws/Wlu6WRChwO84ARb1Ju9h0cZWr4+3"]
        for region in ("us-east-1", " us-east-1 "):
            self.assertEqual(
                self.run_lookup(
                    aws_secret_access_key="secret",
                    region=region,
                ),
                expected,
            )

    def test_region_uses_alias(self):
        expected = ["BHlIeyDS4HKFlws/Wlu6WRChwO84ARb1Ju9h0cZWr4+3"]
        self.assertEqual(
            self.run_lookup(aws_region="us-east-1", aws_secret_access_key="secret"),
            expected,
        )

    def test_rejects_invalid_options_and_positional_terms(self):
        cases = (
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
            with self.subTest(message=message), self.assertRaisesRegex(AnsibleLookupError, message):
                self.run_lookup(**kwargs)

        with self.assertRaisesRegex(AnsibleLookupError, "positional terms"):
            self.run_lookup(
                terms=["unexpected"],
                aws_secret_access_key="secret",
                region="us-east-1",
            )

    def test_propagates_required_option_error(self):
        for kwargs, option in (
            ({"region": "us-east-1"}, "aws_secret_access_key"),
            ({"aws_secret_access_key": "secret"}, "region"),
        ):
            with self.subTest(option=option), self.assertRaisesRegex(AnsibleRequiredOptionError, option):
                self.run_lookup(**kwargs)
