# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.validation import require_non_blank
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


@pytest.mark.parametrize("value", [None, "a", " a ", "\tvalue\n", [], ["a"], ["a", " b "]])
def test_require_non_blank_accepts_unset_and_non_blank_values(value):
    require_non_blank(FakeModule({}), value, "option")


@pytest.mark.parametrize("value", ["", " ", "\t\n", "　"])
def test_require_non_blank_rejects_a_blank_string(value):
    with pytest.raises(ModuleFail) as raised:
        require_non_blank(FakeModule({}), value, "option")

    assert raised.value.values == {"msg": "option must not be empty"}


@pytest.mark.parametrize("value", [[""], [" "], ["a", "\t\n"], ["a", "b", "　"]])
def test_require_non_blank_rejects_a_list_with_a_blank_entry(value):
    with pytest.raises(ModuleFail) as raised:
        require_non_blank(FakeModule({}), value, "parent[].option")

    assert raised.value.values == {"msg": "parent[].option must not contain empty entries"}
