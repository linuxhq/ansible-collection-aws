# ec2\_instance\_metadata

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 instance metadata defaults

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.32.70

## Role Variables

    ec2_instance_metadata_http_endpoint: enabled
    ec2_instance_metadata_http_tokens: required
    ec2_instance_metadata_http_put_response_hop_limit: 2
    ec2_instance_metadata_instance_metadata_tags: disabled

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_instance_metadata

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
