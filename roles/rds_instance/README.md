# rds\_instance

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws relational database service instances

## Requirements

None

## Role Variables

    rds_instance_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.rds_instance
          rds_instance_list:
            - allocated_storage: 20
              db_instance_class: db.t3.medium
              db_instance_identifier: mariadb106
              db_subnet_group_name: molecule
              engine: mariadb
              engine_version: 10.6.20
              master_user_password: sTxmp3nXHCiMf34e9eWcH39v
              master_username: mnkes9JwUdsq
              publicly_accessible: true
              skip_final_snapshot: true
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].vpc_id }}"
              wait: false

            - allocated_storage: 20
              auto_minor_version_upgrade: false
              ca_certificate_identifier: rds-ca-rsa2048-g1
              copy_tags_to_snapshot: true
              db_instance_class: db.t3.medium
              db_instance_identifier: mariadb118
              db_parameter_group_name: mariadb118
              db_subnet_group_name: molecule
              enable_cloudwatch_logs_exports:
                - audit
                - error
                - general
                - slowquery
              enable_iam_database_authentication: true
              engine: mariadb
              engine_version: 11.8.5
              master_user_password: sTxmp3nXHCiMf34e9eWcH39v
              master_username: mnkes9JwUdsq
              max_allocated_storage: 40
              monitoring_interval: 60
              monitoring_role_arn: 'arn:aws:iam::{{ _aws_caller_info_account }}:role/MoleculeRdsMonitoring'
              multi_az: true
              option_group_name: mariadb118
              publicly_accessible: false
              rules:
                - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                  ports:
                    - 3306
                  proto: tcp
              storage_encrypted: true
              storage_type: gp3
              skip_final_snapshot: true
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].vpc_id }}"
              wait: false

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
