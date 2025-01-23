# ec2\_customer\_gateway

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 customer gateways

## Requirements

None

## Role Variables

    ec2_customer_gateway_list: []
    ec2_customer_gateway_list: []
    ec2_customer_gateway_async: 300
    ec2_customer_gateway_batch: 10
    ec2_customer_gateway_delay: 3
    ec2_customer_gateway_poll: 0
    ec2_customer_gateway_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_customer_gateway
          ec2_customer_gateway_list:
            - name: "{{ aws_vpc }}-proton1"
              ip_address: 146.70.127.253

            - name: "{{ aws_vpc }}-proton2"
              ip_address: 146.70.127.254

## License

Copyright (C) 2025 Linux HeadQuarters

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
