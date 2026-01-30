# iam\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws iam groups

## Requirements

None

## Role Variables

    iam_group_async: 300
    iam_group_batch: 10
    iam_group_delay: 3
    iam_group_list: []
    iam_group_poll: 0
    iam_group_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_group
          iam_group_list:
             - name: admin
               managed_policies:
                 - AdministratorAccess
               purge_policies: true
               users:
                 - linuxhq

             - name: backups
               managed_policies:
                 - LinuxHQS3KopiaReadWrite
               purge_policies: true
               users:
                 - kopia

             - name: development
               managed_policies:
                 - AmazonEC2FullAccess
                 - AmazonVPCReadOnlyAccess
               purge_policies: true
               users:
                 - molecule

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
