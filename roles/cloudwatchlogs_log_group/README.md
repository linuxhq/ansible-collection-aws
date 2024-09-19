# cloudwatchlogs\_log\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage cloudwatchlogs log groups

## Requirements

None

## Role Variables

    cloudwatchlogs_log_group_list: []

## Return Values

    _cloudwatchlogs_log_group_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.cloudwatchlogs_log_group
          cloudwatchlogs_log_group_list:
            - name: linuxhq-log-group
              kms_key_id: "{{ _kms_key_info_dict['linuxhq/logs'].key_arn }}"
              retention: 90

## License

Copyright (C) 2023 Linux HeadQuarters

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
