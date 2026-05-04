# route53\_resolver

Manage aws route53 resolver endpoints

## Requirements

None

## Role Variables

    route53_resolver_async: 300
    route53_resolver_batch: 10
    route53_resolver_delay: 3
    route53_resolver_list: []
    route53_resolver_poll: 0
    route53_resolver_retries: 100

## Return Values

None

## Dependencies

* [ec2\_security\_group\_info](../ec2_security_group_info)
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
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-route53resolver'].group_id }}"

            - name: molecule-google
              direction: outbound
              ip_addresses:
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.0.name].id }}"
                  Ip: 192.168.0.126
                - SubnetId: "{{ _ec2_vpc_subnet_info_dict[ec2_vpc_subnet_list.0.subnets.1.name].id }}"
                  Ip: 192.168.0.254
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-route53resolver'].group_id }}"
