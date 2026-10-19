# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import time

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
)


def require_positive_wait_bounds(module, always=False):
    if not always and not module.params.get("wait"):
        return

    for name in ("wait_delay", "wait_timeout"):
        if module.params[name] < 1:
            module.fail_json(msg=f"{name} must be 1 or greater")


def wait_deadline(module):
    """Return the monotonic time at which one run's shared wait_timeout budget ends."""
    return time.monotonic() + module.params["wait_timeout"]


def remaining_wait_timeout(module, deadline, error_msg, changed=False):
    """Return the whole seconds left before deadline, failing with error_msg once less than one remains."""
    timeout = int(deadline - time.monotonic())
    if timeout < 1:
        module.fail_json(changed=changed, msg=error_msg)

    return timeout


def build_waiter_factory(model_data):
    class _WaiterFactory(BaseWaiterFactory):
        @property
        def _waiter_model_data(self):
            return model_data

    return _WaiterFactory()


def run_waiter(module, client, model_data, waiter_name, error_msg, changed=False, timeout=None, **wait_kwargs):
    """Run a custom waiter; changed reports whether the resource was already modified, for failure results.

    timeout overrides wait_timeout when part of the wait budget was already spent.
    """
    try:
        build_waiter_factory(model_data).get_waiter(client, waiter_name).wait(
            **wait_kwargs,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"] if timeout is None else timeout,
                default_pause=module.params["wait_delay"],
            ),
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=error_msg)
