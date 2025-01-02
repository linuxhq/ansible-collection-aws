# wafv2\_ip\_set\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about wafv2 ip sets

## Requirements

None

## Role Variables

    wafv2_ip_set_info_name: null
    wafv2_ip_set_info_scope: null

## Return Values

    _wafv2_ip_set_info_dict
    _wafv2_ip_set_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.wafv2_ip_set_info
          wafv2_ip_set_info_name: linuxhq-google
          wafv2_ip_set_info_scope: regional

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
