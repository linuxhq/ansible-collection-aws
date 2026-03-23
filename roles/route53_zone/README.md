# route53\_zone

Manage aws route53 zones

## Requirements

None

## Role Variables

    route53_zone_async: 300
    route53_zone_batch: 10
    route53_zone_delay: 3
    route53_zone_list: []
    route53_zone_poll: 0
    route53_zone_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [route53\_delegation\_set\_info](../route53_delegation_set_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_zone
          route53_zone_list:
            - zone: molecule-pub-00.org
            - zone: molecule-pub-01.org
            - zone: molecule-pub-02.org

            - zone: molecule-pvt-01.org
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - zone: molecule-pvt-02.org
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"

            - zone: molecule-pvt-03.org
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              vpc_region:
                "{{ lookup('ansible.builtin.ini',
                           'region',
                           file='~/.aws/config',
                           section='profile molecule') }}"
