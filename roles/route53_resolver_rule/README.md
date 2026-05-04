# route53\_resolver\_rule

Manage aws route53 resolver rules

## Requirements

None

## Role Variables

    route53_resolver_rule_async: 300
    route53_resolver_rule_batch: 10
    route53_resolver_rule_delay: 3
    route53_resolver_rule_list: []
    route53_resolver_rule_poll: 0
    route53_resolver_rule_retries: 100

## Return Values

None

## Dependencies

* [route53\_resolver\_info](../route53_resolver_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_resolver_rule
          route53_resolver_rule_list:
            - name: molecule-cloudflare
              domain_name: cloudflare.com
              resolver_endpoint_id: "{{ _route53_resolver_info_dict['molecule-cloudflare'].id }}"
              rule_type: forward
              target_ips:
                - ip: 1.1.1.1
                  port: 53
                - ip: 1.1.1.2
                  port: 53

            - name: molecule-google
              domain_name: google.com
              resolver_endpoint_id: "{{ _route53_resolver_info_dict['molecule-google'].id }}"
              rule_type: forward
              target_ips:
                - ip: 8.8.8.8
                  port: 53
                - ip: 8.8.8.4
                  port: 53
