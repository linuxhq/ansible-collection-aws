# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


def has_valid_cluster_tags(cluster):
    """Return whether an EKS cluster dictionary omits tags or has string tag keys and values."""
    tags = cluster.get("tags")
    return tags is None or (
        isinstance(tags, dict) and all(isinstance(key, str) and isinstance(value, str) for key, value in tags.items())
    )
