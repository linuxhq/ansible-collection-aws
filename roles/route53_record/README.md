# route53\_record

Manage aws route53 records

## Requirements

None

## Role Variables

    route53_record_async: 300
    route53_record_batch: 10
    route53_record_delay: 3
    route53_record_list: []
    route53_record_poll: 0
    route53_record_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [elb\_application\_lb\_info](../elb_application_lb_info)
* [route53\_record\_info](../route53_record_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.route53_record
          route53_record_list:
            - zone: pub.molecule.org
              records:
                - record: molecule-1.pub.molecule.org
                  type: A
                  value: 127.0.0.1
                - record: molecule-2.pub.molecule.org
                  type: A
                  value: 127.0.0.2

            - zone: pvt.molecule.org
              private_zone: true
              records:
                - record: molecule-1.pvt.molecule.org
                  type: A
                  value: 127.0.0.1
                - record: molecule-2.pvt.molecule.org
                  type: A
                  value: 127.0.0.2
