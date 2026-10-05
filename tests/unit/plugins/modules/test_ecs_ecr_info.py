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


def not_found():
    return plugin.ClientError(
        {"Error": {"Code": "RepositoryNotFoundException", "Message": "missing"}},
        "DescribeRepositories",
    )


def repository(name):
    return {"repositoryArn": f"arn:aws:ecr:us-east-1:123456789012:repository/{name}", "repositoryName": name}


def test_missing_repository_keeps_the_repositories_that_exist():
    module = FakeModule(
        {"registry_id": None, "repository_names": ["app", "missing", "web"]},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[
                not_found(),
                {"repositories": [repository("app")]},
                not_found(),
                {"repositories": [repository("web")]},
            ],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [repo["repository_name"] for repo in raised.value.values["repositories"]] == ["app", "web"]
    assert [describe.kwargs["repositoryNames"] for describe in query.call_args_list] == [
        ["app", "missing", "web"],
        ["app"],
        ["missing"],
        ["web"],
    ]


def test_single_missing_repository_returns_an_empty_list():
    module = FakeModule(
        {"registry_id": None, "repository_names": ["missing"]},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=not_found()) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["repositories"] == []
    query.assert_called_once()
