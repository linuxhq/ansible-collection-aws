#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
)

try:
    from botocore.exceptions import WaiterError
except ImportError:
    WaiterError = None

CUSTOM_WAITER_FACTORIES = {}


class _CustomWaiterFactory(BaseWaiterFactory):
    def __init__(self, waiter_model_data):
        self.waiter_model_data = waiter_model_data
        super().__init__()

    @property
    def _waiter_model_data(self):
        return self.waiter_model_data


def wait_for_aws_resource(
    client,
    module,
    waiter_model_data,
    waiter_name,
    timeout_message,
    waiter_config=None,
    **kwargs,
):
    try:
        cache_key = id(waiter_model_data)
        cached_model, waiter_factory = CUSTOM_WAITER_FACTORIES.get(
            cache_key,
            (None, None),
        )
        if cached_model is not waiter_model_data:
            waiter_factory = _CustomWaiterFactory(waiter_model_data)
            CUSTOM_WAITER_FACTORIES[cache_key] = (
                waiter_model_data,
                waiter_factory,
            )
        waiter = waiter_factory.get_waiter(client, waiter_name)
        if waiter_config is None:
            waiter_config = custom_waiter_config(
                module.params["wait_timeout"],
                module.params["wait_delay"],
            )
        waiter.wait(
            WaiterConfig=waiter_config,
            **kwargs,
        )
    except Exception as e:
        if WaiterError is not None and not isinstance(e, WaiterError):
            raise
        module.fail_json_aws(e, msg=timeout_message)
