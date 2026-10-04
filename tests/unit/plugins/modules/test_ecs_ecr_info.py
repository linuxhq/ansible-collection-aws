from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ecs_ecr_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["repository_names"]["elements"] == "str"


def test_repository_filters_are_sent_to_ecr():
    module = FakeModule(
        {"registry_id": None, "repository_names": ["app", "app"]},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"repositories": []},
        ) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_args.args[3] == {
        "describe_repositories": (
            "repositoryNames",
            "maxResults",
            "nextToken",
        )
    }
    assert query.call_args.kwargs["repositoryNames"] == ["app"]


def test_repository_name_limit_is_rejected():
    assert_module_rejects(
        plugin,
        {
            "registry_id": None,
            "repository_names": [f"repository-{index}" for index in range(101)],
        },
        "repository_names must contain at most 100 unique entries",
    )


def test_rejects_malformed_repository_response():
    module = FakeModule(
        {"registry_id": None, "repository_names": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"repositories": [None]}),
        pytest.raises(ModuleFail),
    ):
        plugin.main()


def test_missing_repository_returns_an_empty_list():
    module = FakeModule(
        {"registry_id": None, "repository_names": ["app", "missing"]},
        client=Mock(),
    )
    error = plugin.ClientError(
        {"Error": {"Code": "RepositoryNotFoundException", "Message": "missing"}},
        "DescribeRepositories",
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=error),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["repositories"] == []
