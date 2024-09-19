# s3\_bucket\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about simple storage service buckets

## Requirements

None

## Role Variables

    s3_bucket_info_bucket_facts: {}
    s3_bucket_info_name: null
    s3_bucket_info_name_filter: null
    s3_bucket_info_transform_location: false

## Return Values

    _s3_bucket_info_dict
    _s3_bucket_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_bucket_info
          s3_bucket_info_bucket_facts:
            bucket_accelerate_configuration: true
            bucket_acl: true
            bucket_cors: true
            bucket_encryption: true
            bucket_lifecycle_configuration: true
            bucket_location: true
            bucket_logging: true
            bucket_notification_configuration: true
            bucket_ownership_controls: true
            bucket_policy: true
            bucket_policy_status: true
            bucket_replication: true
            bucket_request_payment: true
            bucket_tagging: true
            bucket_versioning: true
            bucket_website: true
            public_access_block: true

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
