# efs

Manage aws elastic filesystems

## Requirements

None

## Role Variables

    efs_list: []

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.efs
          efs_list:
            - name: linuxhq-efs1
              encrypt: true
              targets:
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-a'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-b'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-c'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['linuxhq'].id }}"

            - name: linuxhq-efs2
              encrypt: true
              rules:
                - cidr_ip: 10.0.0.0/8
                  ports:
                    - 2049
                  proto: tcp
              rules_egress:
                - cidr_ip: 10.0.0.0/8
                  ports:
                    - 0-65535
                  proto: tcp
              targets:
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-a'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-b'].id }}"
                - subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-c'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['linuxhq'].id }}"
