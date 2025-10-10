# iam\_password\_policy

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws identity and access management password policy

## Requirements

None

## Role Variables

    iam_password_policy_allow_pw_change: false
    iam_password_policy_min_pw_length: 6
    iam_password_policy_pw_expire: false
    iam_password_policy_pw_max_age: 0
    iam_password_policy_pw_reuse_prevent: 0
    iam_password_policy_require_lowercase: false
    iam_password_policy_require_numbers: false
    iam_password_policy_require_symbols: false
    iam_password_policy_require_uppercase: false
    iam_password_policy_state: present

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_password_policy
          iam_password_policy_allow_pw_change: true
          iam_password_policy_min_pw_length: 12
          iam_password_policy_pw_expire: false
          iam_password_policy_pw_max_age: 90
          iam_password_policy_pw_reuse_prevent: 24
          iam_password_policy_require_lowercase: true
          iam_password_policy_require_numbers: true
          iam_password_policy_require_symbols: true
          iam_password_policy_require_uppercase: true

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
