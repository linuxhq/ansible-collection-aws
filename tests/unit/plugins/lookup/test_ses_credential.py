# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest
from botocore.session import Session

from ansible.errors import AnsibleLookupError, AnsibleRequiredOptionError
from ansible.plugins.loader import lookup_loader

EXPECTED = ["BHlIeyDS4HKFlws/Wlu6WRChwO84ARb1Ju9h0cZWr4+3"]


def run_lookup(terms=None, variables=None, **kwargs):
    lookup = lookup_loader.get("linuxhq.aws.ses_credential")
    return lookup.run(terms or [], variables=variables, **kwargs)


@pytest.mark.parametrize("region", ["us-east-1", " us-east-1 "])
def test_known_smtp_password_vector(region):
    assert run_lookup(aws_secret_access_key="secret", region=region) == EXPECTED


def test_region_uses_alias():
    assert run_lookup(aws_region="us-east-1", aws_secret_access_key="secret") == EXPECTED


def test_every_ses_region_is_accepted():
    session = Session()
    regions = {
        region
        for partition in session.get_available_partitions()
        for region in session.get_available_regions("ses", partition_name=partition)
    }

    assert regions
    for region in regions:
        assert run_lookup(aws_secret_access_key="secret", region=region)


@pytest.mark.parametrize("region", ["us-east1", "useast-1", "US-EAST-1", "us-east-one"])
def test_rejects_invalid_region(region):
    with pytest.raises(AnsibleLookupError, match=f"valid AWS region name, not '{region}'"):
        run_lookup(aws_secret_access_key="secret", region=region)


@pytest.mark.parametrize("secret", ["secret ", " secret", "sec ret", "secret\n"])
def test_rejects_whitespace_in_secret_without_revealing_it(secret):
    with pytest.raises(AnsibleLookupError) as raised:
        run_lookup(aws_secret_access_key=secret, region="us-east-1")

    assert str(raised.value) == "ses_credential lookup requires an aws_secret_access_key without whitespace"
    assert "secret" not in str(raised.value).replace("aws_secret_access_key", "")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"aws_secret_access_key": "secret", "region": " "}, "non-empty region="),
        ({"aws_secret_access_key": "", "region": "us-east-1"}, "non-empty aws_secret_access_key="),
    ],
)
def test_rejects_empty_options(kwargs, message):
    with pytest.raises(AnsibleLookupError, match=message):
        run_lookup(**kwargs)


def test_rejects_positional_terms():
    with pytest.raises(AnsibleLookupError, match="positional terms"):
        run_lookup(terms=["unexpected"], aws_secret_access_key="secret", region="us-east-1")


@pytest.mark.parametrize(
    ("kwargs", "option"),
    [({"region": "us-east-1"}, "aws_secret_access_key"), ({"aws_secret_access_key": "secret"}, "region")],
)
def test_propagates_required_option_error(kwargs, option):
    with pytest.raises(AnsibleRequiredOptionError, match=option):
        run_lookup(**kwargs)
