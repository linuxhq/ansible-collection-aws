# rds\_instance

Manage aws rds instances

## Requirements

None

## Role Variables

    rds_instance_list: []

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

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
              monitoring_role_arn: "arn:aws:iam::{{ _aws_caller_info_account }}:role/MoleculeRdsMonitoring"
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
