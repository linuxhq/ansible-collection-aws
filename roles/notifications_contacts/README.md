# notifications\_contacts

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws notifications contacts

## Requirements

* [awscli](https://pypi.org/project/awscli) >= 1.37.10

## Role Variables

    notifications_contacts_list: []
    notifications_contacts_async: 300
    notifications_contacts_batch: 10
    notifications_contacts_delay: 3
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
            - name: aws-billing
              email_address: aws-billing@linuxhq.org
            - name: aws-health
              email_address: aws-health@linuxhq.org
            - name: aws-security
              email_address: aws-security@linuxhq.org

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
