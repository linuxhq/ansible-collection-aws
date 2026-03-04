# notifications\_contacts

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws notifications contacts

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.37.10

## Role Variables

    notifications_contacts_async: 300
    notifications_contacts_batch: 10
    notifications_contacts_delay: 3
    notifications_contacts_list: []
    notifications_contacts_poll: 0
    notifications_contacts_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.notifications_contacts
          notifications_contacts_list:
            - name: molecule-dummy01
              email_address: dummy01@molecule.org
            - name: molecule-dummy02
              email_address: dummy02@molecule.org
            - name: molecule-dummy03
              email_address: dummy03@molecule.org
            - name: molecule-dummy04
              email_address: dummy04@molecule.org
            - name: molecule-dummy05
              email_address: dummy05@molecule.org
            - name: molecule-dummy06
              email_address: dummy06@molecule.org
            - name: molecule-dummy07
              email_address: dummy07@molecule.org
            - name: molecule-dummy08
              email_address: dummy08@molecule.org
            - name: molecule-dummy09
              email_address: dummy09@molecule.org
            - name: molecule-dummy10
              email_address: dummy10@molecule.org
            - name: molecule-dummy11
              email_address: dummy11@molecule.org
            - name: molecule-dummy12
              email_address: dummy12@molecule.org

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
