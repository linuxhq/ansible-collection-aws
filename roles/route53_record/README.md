# route53\_record

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

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

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.elb\_application\_lb\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/elb_application_lb_info)
* [linuxhq.aws.route53\_record\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/route53_record_info)

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

## License

Copyright (c) Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
