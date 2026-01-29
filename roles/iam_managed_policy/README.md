# iam\_managed\_policy

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws identity and access management policies

## Requirements

None

## Role Variables

    iam_managed_policy_async: 300
    iam_managed_policy_batch: 10
    iam_managed_policy_delay: 3
    iam_managed_policy_list: []
    iam_managed_policy_poll: 0
    iam_managed_policy_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_managed_policy
          iam_managed_policy_list:
            - name: linuxhq-admin
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action: '*'
                    Resource: '*'

            - name: linuxhq-s3
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action: 's3:*'
                    Resource: '*'

## License

Copyright (c) Linux HeadQuarters

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
