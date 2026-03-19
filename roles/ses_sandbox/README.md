# ses\_sandbox

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws simple email service account details

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    ses_sandbox_additional_contact_email_addresses: []
    ses_sandbox_contact_language: en
    ses_sandbox_mail_type: transactional
    ses_sandbox_use_case_description: null
    ses_sandbox_website_url: null

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ses_sandbox
          ses_sandbox_additional_contact_email_addresses:
            - jake@molecule.org
            - john@molecule.org
          ses_sandbox_use_case_description: |
            New account creation
          ses_sandbox_website_url: 'https://github.com/ansible/molecule'

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
