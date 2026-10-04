# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict


def association_overview(overview):
    # The aggregated count is keyed by association status names, which are data rather than field names.
    if not isinstance(overview, dict):
        return overview

    return camel_dict_to_snake_dict(overview, ignore_list=["AssociationStatusAggregatedCount"])
