# ec2\_vpc\_dhcp\_option

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud dhcp options

## Requirements

None

## Role Variables

    ec2_vpc_dhcp_option_list: []
    ec2_vpc_dhcp_option_async: 300
    ec2_vpc_dhcp_option_batch: 10
    ec2_vpc_dhcp_option_delay: 3
    ec2_vpc_dhcp_option_poll: 0
    ec2_vpc_dhcp_option_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_dhcp_option
          ec2_vpc_dhcp_option_list:
            - name: linuxhq
              dns_servers:
                - 1.1.1.1
                - 1.1.1.2

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
