# wafv2\_ip\_set

Manage aws wafv2 ip sets

## Requirements

None

## Role Variables

    wafv2_ip_set_async: 300
    wafv2_ip_set_batch: 10
    wafv2_ip_set_delay: 3
    wafv2_ip_set_list: []
    wafv2_ip_set_poll: 0
    wafv2_ip_set_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.wafv2_ip_set
          wafv2_ip_set_list:
            - name: molecule-cloudflare
              addresses:
                - 1.1.1.1/32
              ip_address_version: ipv4
              scope: regional

            - name: molecule-google
              addresses:
                - 8.8.8.8/32
                - 8.8.8.4/32
              ip_address_version: ipv4
              scope: regional
