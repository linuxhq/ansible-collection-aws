# route53\_resolver\_rule

Manage aws route53 resolver rules

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    route53_resolver_rule_list: []

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
              resolver_endpoint_id: "{{ _route53_resolver_info_dict['molecule-cloudflare'].Id }}"
              rule_type: forward
              target_ips:
                - Ip: 1.1.1.1
                  Port: 53
                - Ip: 1.1.1.2
                  Port: 53

            - name: molecule-google
              domain_name: google.com
              resolver_endpoint_id: "{{ _route53_resolver_info_dict['molecule-google'].Id }}"
              rule_type: forward
              target_ips:
                - Ip: 8.8.8.8
                  Port: 53
                - Ip: 8.8.8.4
                  Port: 53
