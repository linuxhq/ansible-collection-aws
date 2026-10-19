# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.iterators import chunks
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
)

# EC2 counts values across all filters in a request and rejects more than this.
MAX_FILTER_VALUES_PER_REQUEST = 200


def filter_value(value):
    # AWS filter values are strings, and boolean values only match in lowercase.
    if isinstance(value, bool):
        return str(value).lower()

    if isinstance(value, (int, float)):
        return str(value)

    return value


def ansible_dict_to_string_filter_list(filters):
    """Build boto3 Filters, converting Boolean and numeric values, including list entries, to strings."""
    return ansible_dict_to_boto3_filter_list(
        {
            name: [filter_value(item) for item in value] if isinstance(value, list) else filter_value(value)
            for name, value in filters.items()
        }
    )


def filter_value_batches(module, filters, name, values, option):
    """Return copies of filters with values split across them under name, so no request exceeds the EC2 limit.

    Without values, filters are returned unchanged and EC2 validates them.
    """
    if not values:
        return [filters]

    other_value_count = sum(
        len(value) if isinstance(value, list) else 1 for key, value in filters.items() if key != name
    )
    batch_size = MAX_FILTER_VALUES_PER_REQUEST - other_value_count
    if batch_size < 1:
        module.fail_json(
            msg=(
                f"EC2 accepts at most {MAX_FILTER_VALUES_PER_REQUEST} filter values in each request, so filters "
                f"must contain fewer than {MAX_FILTER_VALUES_PER_REQUEST} values when {option} is set"
            )
        )

    batches = []
    for batch in chunks(values, batch_size):
        batch_filters = dict(filters)
        batch_filters[name] = batch
        batches.append(batch_filters)

    return batches
