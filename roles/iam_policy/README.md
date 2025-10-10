# iam\_policy

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws identity and access management inline policies

## Requirements

None

## Role Variables

    iam_policy_list: []

## Return Values

    _iam_policy_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_policy
          iam_policy_list:
            - iam_name: linuxhq
              iam_type: user
              policy_json:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action:
                      - ec2:*
                    Resource:
                      - '*'
              policy_name: LinuxHQEC2FullAccess

            - iam_name: backups
              iam_type: group
              policy_json:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action:
                      - rds:*
                    Resource:
                      - '*'
              policy_name: LinuxHQRDSFullAccess

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
