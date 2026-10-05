# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    ansible_dict_to_string_filter_list,
)


def test_boolean_and_numeric_values_are_sent_as_strings():
    assert ansible_dict_to_string_filter_list(
        {
            "flag": True,
            "flags": [False, True],
            "count": 2,
            "counts": [1, 2],
            "ratio": 0.5,
            "name": "example",
            "names": ["a", "b"],
        }
    ) == [
        {"Name": "flag", "Values": ["true"]},
        {"Name": "flags", "Values": ["false", "true"]},
        {"Name": "count", "Values": ["2"]},
        {"Name": "counts", "Values": ["1", "2"]},
        {"Name": "ratio", "Values": ["0.5"]},
        {"Name": "name", "Values": ["example"]},
        {"Name": "names", "Values": ["a", "b"]},
    ]


def test_caller_filters_are_not_mutated():
    filters = {"flags": [True]}
    ansible_dict_to_string_filter_list(filters)
    assert filters == {"flags": [True]}
