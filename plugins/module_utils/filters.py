# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
)


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
