# wafv2\_ip\_set

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws wafv2 ip sets

## Requirements

None

## Role Variables

    wafv2_ip_set_list: []

## Return Values

    _wafv2_ip_set_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.wafv2_ip_set
          wafv2_ip_set_list:
            - name: linuxhq-cloudflare
              addresses:
                - 1.1.1.1/32
              ip_address_version: ipv4
              scope: regional

            - name: linuxhq-google
              addresses:
                - 8.8.8.8/32
                - 8.8.8.4/32
              ip_address_version: ipv4
              scope: regional

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
