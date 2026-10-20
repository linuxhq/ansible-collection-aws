# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    ansible_dict_to_string_filter_list,
    filter_value_batches,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


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


def test_filter_value_batches_without_values_return_the_filters_unchanged():
    filters = {"state": ["available"]}

    assert filter_value_batches(FakeModule({}), filters, "group-name", [], "group_names") == [filters]


def test_filter_value_batches_count_values_across_other_filters():
    filters = {"group-name": "ignored", "state": ["available", "pending"], "strategy": "cluster"}
    values = [f"name-{index}" for index in range(400)]

    batches = filter_value_batches(FakeModule({}), filters, "group-name", values, "group_names")

    assert [len(batch["group-name"]) for batch in batches] == [197, 197, 6]
    assert [value for batch in batches for value in batch["group-name"]] == values
    assert all(list(batch) == ["group-name", "state", "strategy"] for batch in batches)
    assert filters["group-name"] == "ignored"


def test_filter_value_batches_fail_when_other_filters_leave_no_room():
    filters = {"state": [str(index) for index in range(199)], "strategy": "cluster"}

    with pytest.raises(ModuleFail) as raised:
        filter_value_batches(FakeModule({}), filters, "group-name", ["name"], "group_names")

    assert raised.value.values["msg"] == (
        "EC2 accepts at most 200 filter values in each request, so filters must contain fewer than 200 values "
        "when group_names is set"
    )


def test_filter_value_batches_honor_a_lower_max_values():
    filters = {"state": ["available"]}
    values = [f"tgw-rtb-{index}" for index in range(100)]

    batches = filter_value_batches(FakeModule({}), filters, "id", values, "ids", max_values=100)

    assert [len(batch["id"]) for batch in batches] == [99, 1]

    with pytest.raises(ModuleFail) as raised:
        filter_value_batches(FakeModule({}), {"state": [str(index) for index in range(100)]}, "id", ["x"], "ids", 100)

    assert raised.value.values["msg"] == (
        "EC2 accepts at most 100 filter values in each request, so filters must contain fewer than 100 values "
        "when ids is set"
    )
