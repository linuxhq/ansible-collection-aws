# ec2\_instance\_metadata

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 instance metadata defaults

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.32.70

## Role Variables

    ec2_instance_metadata_async: 300
    ec2_instance_metadata_batch: 10
    ec2_instance_metadata_delay: 3
    ec2_instance_metadata_http_endpoint: enabled
    ec2_instance_metadata_http_tokens: required
    ec2_instance_metadata_http_put_response_hop_limit: 2
    ec2_instance_metadata_instance_metadata_tags: disabled
    ec2_instance_metadata_poll: 0
    ec2_instance_metadata_regions:
      - us-east-1
    ec2_instance_metadata_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.aws\_region\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/aws_region_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_instance_metadata
          ec2_instance_metadata_regions:
            "{{ (_aws_region_info_list |
                map(attribute='region_name')) |
                d(['us-east-1']) }}"

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
