# ec2\_vpc\_dhcp\_option\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about virtual private cloud dhcp options

## Requirements

None

## Role Variables

Available variables are listed below, along with default values:

    ec2_vpc_dhcp_option_info_dhcp_options_ids: []
    ec2_vpc_dhcp_option_info_filters: {}

## Return Values

    _ec2_vpc_dhcp_option_info_dhcp_configurations
    _ec2_vpc_dhcp_option_info_dhcp_options_id

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_vpc_dhcp_option_info

## License

Copyright (C) 2023 Linux HeadQuarters

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
