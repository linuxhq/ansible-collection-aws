# kms\_key

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws key management service keys

## Requirements

None

## Role Variables

    kms_key_async: 300
    kms_key_batch: 10
    kms_key_delay: 3
    kms_key_list: []
    kms_key_poll: 0
    kms_key_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.kms_key
          kms_key_list:
            - name: molecule-root
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS: 'arn:aws:iam::{{ _aws_caller_info_account }}:root'
                    Action:
                      - kms:*
                    Resource:
                      - '*'

            - name: molecule-admin
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS: 'arn:aws:iam::{{ _aws_caller_info_account }}:root'
                    Action:
                      - kms:*
                    Resource:
                      - '*'
                  - Effect: Allow
                    Principal:
                      AWS: '*'
                    Action:
                      - kms:*
                    Resource:
                      - '*'
                    Condition:
                      ArnEquals:
                        'aws:PrincipalArn':
                          - 'arn:aws:iam::{{ _aws_caller_info_account }}:role/admin'

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
