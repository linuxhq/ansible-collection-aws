# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)

SSM_ASSOCIATION_RESOURCE_TYPE = "Association"
SSM_DOCUMENT_RESOURCE_TYPE = "Document"


def ssm_filter_list(filters, key_name="Key", values_name="Values", split_values=False):
    """Build an SSM filter list from a dict, stringifying values.

    Each filter holds a list of values under values_name, or with split_values one value per filter.
    """
    filter_list = []
    for key, value in filters.items():
        values = [str(item) for item in (value if isinstance(value, list) else [value])]
        if split_values:
            filter_list.extend({key_name: key, values_name: item} for item in values)
        else:
            filter_list.append({key_name: key, values_name: values})

    return filter_list


def require_valid_ssm_targets(module, targets):
    """Fail unless each target has a 1 to 163 character key and 1 to 50 distinct values."""
    for target in targets:
        if not target["key"] or not 1 <= len(target["key"]) <= 163:
            module.fail_json(msg="targets[].key must be 1 to 163 characters")

        if not target["values"]:
            module.fail_json(msg="targets[].values must contain at least one entry")

        if len(set(target["values"])) > 50:
            module.fail_json(msg="targets[].values must contain at most 50 entries")


def association_overview(overview, count_key="AssociationStatusAggregatedCount"):
    # The aggregated count is keyed by association status names, which are data rather than field names.
    if not isinstance(overview, dict):
        return overview

    return camel_dict_to_snake_dict(overview, ignore_list=[count_key])


def list_ssm_tags(module, client, resource_type, resource_id, description, changed=False, missing_ok=False):
    """Return an SSM resource's tag list, or None when missing_ok is set and the resource no longer exists.

    changed reports whether the resource was already modified, for failure results.
    """
    try:
        response = client.list_tags_for_resource(
            ResourceType=resource_type,
            ResourceId=resource_id,
            aws_retry=True,
        )
    except is_boto3_error_code("InvalidResourceId") as e:
        if missing_ok:
            return None

        module.fail_json_aws(e, changed=changed, msg=f"Unable to list tags for {description} {resource_id}")
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=f"Unable to list tags for {description} {resource_id}")

    tags = response.get("TagList", []) if isinstance(response, dict) else None
    if not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags):
        module.fail_json(changed=changed, msg=f"Unexpected response while listing tags for {description} {resource_id}")

    return tags


def describe_ssm_document(module, client, name, **request):
    """Return a document's DescribeDocument description, or None when the document or requested version is missing.

    The description reports the stored DocumentFormat, which GetDocument cannot read for a format it cannot serve.
    """
    try:
        response = client.describe_document(**request, Name=name, aws_retry=True)
    except is_boto3_error_code(["InvalidDocument", "InvalidDocumentVersion"]):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe AWS Systems Manager document {name}")

    document = response.get("Document") if isinstance(response, dict) else None
    document_format = document.get("DocumentFormat") if isinstance(document, dict) else None
    if not isinstance(document_format, str) or not document_format:
        module.fail_json(msg=f"Unexpected response while describing AWS Systems Manager document {name}")

    return document
