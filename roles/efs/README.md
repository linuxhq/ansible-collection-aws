# efs

Manage aws elastic filesystems

## Requirements

None

## Role Variables

    efs_async: 600
    efs_batch: 10
    efs_delay: 3
    efs_list: []
    efs_poll: 0
    efs_retries: 200

## Return Values

None

## Dependencies

* [ec2\_security\_group\_info](../ec2_security_group_info)
* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_security_group
          ec2_security_group_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              security_groups:
                - name: molecule-efs1
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 2049
                      proto: tcp

        - role: linuxhq.aws.efs
          efs_list:
            - name: molecule-efs1
              encrypt: true
              targets:
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                  security_groups:
                    - "{{ _ec2_security_group_info_dict['molecule-efs1'].group_id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-b'].id }}"
                  security_groups:
                    - "{{ _ec2_security_group_info_dict['molecule-efs1'].group_id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-c'].id }}"
                  security_groups:
                    - "{{ _ec2_security_group_info_dict['molecule-efs1'].group_id }}"
