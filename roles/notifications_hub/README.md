# notifications\_hub

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws notifications hubs

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.37.10

## Role Variables

    notifications_hub_list: []
    notifications_hub_async: 300
    notifications_hub_batch: 10
    notifications_hub_delay: 3
    notifications_hub_poll: 0
    notifications_hub_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.notifications_hub
          notifications_hub_list:
            - region: us-east-1
            - region: us-west-1
              state: absent

## License

Copyright (C) 2025 Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
