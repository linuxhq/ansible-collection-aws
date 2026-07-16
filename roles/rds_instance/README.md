# rds\_instance

Manage aws rds instances

## Requirements

None

## Role Variables

    rds_instance_async: 3600
    rds_instance_batch: 10
    rds_instance_delay: 3
    rds_instance_list: []
    rds_instance_poll: 0
    rds_instance_retries: 1200

## Return Values

None

## Dependencies

* [ec2\_security\_group\_info](../ec2_security_group_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_security_group
          ec2_security_group_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              security_groups:
                - name: mariadb106
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 3306
                      proto: tcp

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
              vpc_security_group_ids:
                - "{{ _ec2_security_group_info_dict['mariadb106'].group_id }}"
