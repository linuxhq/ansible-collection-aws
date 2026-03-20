# ec2\_vpc\_endpoint

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud endpoints

## Requirements

None

## Role Variables

    ec2_vpc_endpoint_async: 300
    ec2_vpc_endpoint_batch: 10
    ec2_vpc_endpoint_delay: 3
    ec2_vpc_endpoint_list: []
    ec2_vpc_endpoint_poll: 0
    ec2_vpc_endpoint_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_security\_group\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_security_group_info)
* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_route\_table\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_route_table_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_endpoint
          ec2_vpc_endpoint_list:
            - name: molecule
              route_table_ids:
                - "{{ _ec2_vpc_route_table_info_dict['molecule'].id }}"
              service: com.amazonaws.us-east-1.s3
              vpc_endpoint_type: Gateway
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

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
