# ec2\_security\_group

Manage aws ec2 security groups

## Requirements

None

## Role Variables

    ec2_security_group_async: 300
    ec2_security_group_batch: 10
    ec2_security_group_delay: 3
    ec2_security_group_list: []
    ec2_security_group_poll: 0
    ec2_security_group_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_prefix\_list\_info](../ec2_vpc_prefix_list_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_security_group
          ec2_security_group_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict[aws_vpc].id }}"
              security_groups:
                - name: "{{ aws_vpc }}-ssh"
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 22
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1

                - name: "{{ aws_vpc }}-https"
                  rules:
                    - cidr_ip: 0.0.0.0/0
                      ports:
                        - 443
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
