# profile

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws profile config and credentials

## Requirements

None

## Role Variables

    profile_dir: '~/.aws'
    profile_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      roles:
        - role: linuxhq.aws.profile
          profile_list:
            - name: linuxhq
              config:
                output: json
                region: us-east-1
              credentials:
                aws_access_key_id:
                  "{{ lookup('ansible.builtin.ini',
                             'aws_access_key_id',
                             file='~/.aws/credentials',
                             section='linuxhq') }}"
                aws_secret_access_key:
                  "{{ lookup('ansible.builtin.ini',
                             'aws_secret_access_key',
                             file='~/.aws/credentials',
                             section='linuxhq') }}"

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
