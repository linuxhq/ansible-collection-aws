# route53\_resolver

Manage aws route53 resolvers

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    route53_resolver_list: []

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver
          route53_resolver_list:
            - name: molecule-cloudflare
              direction: outbound
              ip_addresses:
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.0.name].id }}"
                  Ip: 192.168.0.125
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.1.name].id }}"
                  Ip: 192.168.0.253
              vpc_id: "{{ _ec2_vpc_net_info_dict[ec2_vpc_net_list.0.name].id }}"

            - name: molecule-google
              direction: outbound
              ip_addresses:
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.0.name].id }}"
                  Ip: 192.168.0.126
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.1.name].id }}"
                  Ip: 192.168.0.254
              rules:
                - cidr_ip: 192.168.0.0/24
                  ports:
                    - 53
                  proto: tcp
                - cidr_ip: 192.168.0.0/24
                  ports:
                    - 53
                  proto: udp
              rules_egress:
                - cidr_ip: 192.168.0.0/24
                  proto: -1
              vpc_id: "{{ _ec2_vpc_net_info_dict[ec2_vpc_net_list.0.name].id }}"
