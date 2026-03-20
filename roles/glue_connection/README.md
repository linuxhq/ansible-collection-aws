# glue\_connection

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws glue connections

## Requirements

None

## Role Variables

    glue_connection_async: 300
    glue_connection_batch: 10
    glue_connection_delay: 3
    glue_connection_list: []
    glue_connection_poll: 0
    glue_connection_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_security\_group\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_security_group_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.glue_connection
          glue_connection_list:
            - name: molecule
              availability_zone: us-east-1a
              connection_properties:
                KAFKA_SSL_ENABLED: 'false'
              connection_type: NETWORK
              security_groups:
                - "{{ _ec2_security_group_info_dict['molecule-rds'].group_id }}"
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule'].id }}"

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
