# s3\_bucket

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws simple storage service buckets

## Requirements

None

## Role Variables

    s3_bucket_list: []

## Return Values

    _s3_bucket_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_bucket
          s3_bucket_list:
            - name: "{{ _aws_caller_info_account }}-{{ aws_region }}-linuxhq-backups"
              accelerate_enabled: true
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Deny
                    Action: s3:*
                    Principal: '*'
                    Resource:
                      - "arn:aws:s3:::{{ _aws_caller_info_account }}-{{ aws_region }}-linuxhq-backups"
                      - "arn:aws:s3:::{{ _aws_caller_info_account }}-{{ aws_region }}-linuxhq-backups/*"
                    Condition:
                      Bool:
                        'aws:SecureTransport': false
              public_access:
                block_public_acls: true
                block_public_policy: true
                ignore_public_acls: true
                restrict_public_buckets: true

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
