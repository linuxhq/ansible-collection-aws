# kms\_key

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws key management service keys

## Requirements

None

## Role Variables

    kms_key_list: []

## Return Values

    _kms_key_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.kms_key
          kms_key_list:
            - name: linuxhq/ssm
              enable_key_rotation: true
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS:
                        - "arn:aws:iam::{{ _aws_caller_info_account }}:root"
                    Action:
                      - kms:*
                    Resource:
                      - '*'
                  - Effect: Allow
                    Principal:
                      AWS: '*'
                    Action:
                      - kms:Decrypt
                    Resource:
                      - '*'
                    Condition:
                      ArnLike:
                        'aws:PrincipalArn':
                          - "arn:aws:iam::{{ _aws_caller_info_account }}:role/LinuxHQInstanceProfile*"
                  - Effect: Allow
                    Principal:
                      Service: "logs.{{ aws_region }}.amazonaws.com"
                    Action:
                      - kms:Decrypt*
                      - kms:Describe*
                      - kms:Encrypt*
                      - kms:GenerateKeyData*
                      - kms:ReEncrypt*
                    Resource:
                      - '*'
                    Condition:
                      ArnLike:
                        'kms:EncryptionContext:aws:logs:arn':
                          "arn:aws:logs:{{ aws_region }}:{{ _aws_caller_info_account }}:log-group:/linuxhq/ssm/sessions"

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
