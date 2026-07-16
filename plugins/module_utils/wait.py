# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
)


def require_positive_wait_bounds(module):
    if not module.params.get("wait"):
        return

    for name in ("wait_delay", "wait_timeout"):
        if module.params[name] < 1:
            module.fail_json(msg=f"{name} must be 1 or greater")


def build_waiter_factory(model_data):
    class _WaiterFactory(BaseWaiterFactory):
        @property
        def _waiter_model_data(self):
            return model_data

    return _WaiterFactory()


def run_waiter(module, client, model_data, waiter_name, error_msg, **wait_kwargs):
    try:
        build_waiter_factory(model_data).get_waiter(client, waiter_name).wait(
            **wait_kwargs,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=module.params["wait_delay"],
            ),
        )
    except Exception as e:
        module.fail_json_aws(e, msg=error_msg)
