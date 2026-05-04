# route53\_zone\_associate

Manage aws route53 zone associations

## Requirements

None

## Role Variables

    route53_zone_associate_async: 300
    route53_zone_associate_batch: 10
    route53_zone_associate_delay: 3
    route53_zone_associate_list: []
    route53_zone_associate_poll: 0
    route53_zone_associate_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [route53\_zone\_info](../route53_zone_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_zone_associate
          route53_zone_associate_list:
            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.0.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-2'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.1.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-2'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.0.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-3'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - hosted_zone_id: "{{ _route53_zone_info_dict[route53_zone_list.1.zone].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-3'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"
