# rds\_subnet\_group

Manage aws rds subnet groups

## Requirements

None

## Role Variables

    rds_subnet_group_async: 300
    rds_subnet_group_batch: 10
    rds_subnet_group_delay: 3
    rds_subnet_group_list: []
    rds_subnet_group_poll: 0
    rds_subnet_group_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.rds_subnet_group
          rds_subnet_group_list:
            - name: molecule
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"
