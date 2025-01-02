# ec2\_vpc\_prefix\_list

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws virtual private cloud prefix lists

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    ec2_vpc_prefix_list_entries: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_prefix_list
          ec2_vpc_prefix_list_entries:
            - name: cloudflare-ipv4
              entries:
                "{{ lookup('ansible.builtin.url',
                           'https://www.cloudflare.com/ips-v4',
                           wantlist=true) }}"

            - name: cloudflare-ipv6
              address_family: IPv6
              entries:
                "{{ lookup('ansible.builtin.url',
                           'https://www.cloudflare.com/ips-v6',
                           wantlist=true) }}"

            - name: "{{ aws_vpc }}"
              entries:
                - "{{ aws_network }}"

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
