# route53\_resolver\_rule\_associate

Manage aws route53 resolver rule associations

## Requirements

None

## Role Variables

    route53_resolver_rule_associate_async: 300
    route53_resolver_rule_associate_batch: 10
    route53_resolver_rule_associate_delay: 3
    route53_resolver_rule_associate_list: []
    route53_resolver_rule_associate_poll: 0
    route53_resolver_rule_associate_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [route53\_resolver\_rule\_info](../route53_resolver_rule_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver_rule_associate
          route53_resolver_rule_associate_list:
            - name: molecule-1
              resolver_rule_id: "{{ _route53_resolver_rule_info_dict['molecule-cloudflare'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-1'].id }}"

            - name: molecule-1
              resolver_rule_id: "{{ _route53_resolver_rule_info_dict['molecule-google'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-1'].id }}"

            - name: molecule-2
              resolver_rule_id: "{{ _route53_resolver_rule_info_dict['molecule-cloudflare'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-2'].id }}"

            - name: molecule-2
              resolver_rule_id: "{{ _route53_resolver_rule_info_dict['molecule-google'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-2'].id }}"

            - name: molecule-3
              resolver_rule_id: "{{ _route53_resolver_rule_info_dict['molecule-cloudflare'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-3'].id }}"

            - name: molecule-3
              resolver_rule_id: "{{ _route53_resolver_rule_info_dict['molecule-google'].id }}"
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule-3'].id }}"
