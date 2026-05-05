#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
)
from botocore.exceptions import WaiterError


class _CustomWaiterFactory(BaseWaiterFactory):
    def __init__(self, waiter_model_data):
        self.waiter_model_data = waiter_model_data
        super().__init__()

    @property
    def _waiter_model_data(self):
        return self.waiter_model_data


def _wait_config_from_module(
    module, timeout_param="wait_timeout", delay_param="wait_delay"
):
    return custom_waiter_config(
        module.params[timeout_param],
        module.params[delay_param],
    )


def _waiter_config_from_module_or_value(module, waiter_config):
    if waiter_config is not None:
        return waiter_config
    return _wait_config_from_module(module)


def _custom_waiter(client, waiter_model_data, waiter_name):
    return _CustomWaiterFactory(waiter_model_data).get_waiter(client, waiter_name)


def wait_for_aws_resource(
    client,
    module,
    waiter_model_data,
    waiter_name,
    timeout_message,
    waiter_config=None,
    **kwargs,
):
    waiter = _custom_waiter(client, waiter_model_data, waiter_name)
    try:
        waiter.wait(
            WaiterConfig=_waiter_config_from_module_or_value(module, waiter_config),
            **kwargs,
        )
    except WaiterError as e:
        module.fail_json_aws(e, msg=timeout_message)
