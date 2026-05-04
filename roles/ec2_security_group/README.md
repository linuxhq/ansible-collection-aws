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
            - vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              security_groups:
                - name: molecule-ftp
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 21
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-ssh
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 22
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-telnet
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 23
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-smtp
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 25
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-domain
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 53
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-http
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 80
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-pop3
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 110
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-imap
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 143
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-ldap
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 389
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-https
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 443
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-ircd
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 6667
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
                - name: molecule-ircs
                  rules:
                    - cidr_ip: "{{ ec2_vpc_net_list.0.cidr_block }}"
                      ports:
                        - 6697
                      proto: tcp
                  rules_egress:
                    - cidr_ip: 0.0.0.0/0
                      proto: -1
