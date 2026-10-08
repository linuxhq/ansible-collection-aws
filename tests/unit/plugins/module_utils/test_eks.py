# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.eks import has_valid_cluster_tags


@pytest.mark.parametrize(
    "cluster",
    [{}, {"tags": None}, {"tags": {}}, {"tags": {"Name": "ops"}}],
)
def test_has_valid_cluster_tags_accepts_missing_or_string_tags(cluster):
    assert has_valid_cluster_tags(cluster) is True


@pytest.mark.parametrize(
    "cluster",
    [{"tags": []}, {"tags": "Name"}, {"tags": {"Name": 1}}, {"tags": {1: "ops"}}, {"tags": {"Name": None}}],
)
def test_has_valid_cluster_tags_rejects_invalid_tags(cluster):
    assert has_valid_cluster_tags(cluster) is False
