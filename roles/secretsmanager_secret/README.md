# secretsmanager\_secret

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws secrets manager secrets

## Requirements

None

## Role Variables

    secretsmanager_secret_async: 300
    secretsmanager_secret_batch: 10
    secretsmanager_secret_delay: 3
    secretsmanager_secret_list: []
    secretsmanager_secret_poll: 0
    secretsmanager_secret_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.rds\_instance\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/rds_instance_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.secretsmanager_secret
          secretsmanager_secret_list:
            - name: molecule-secret-1
              secret:
                - key: molecule-secret-1
                  value: WnvpxzicuneCE7PM7upC7aVNFwYoz7wE
            - name: molecule-secret-2
              secret:
                - key: molecule-secret-2
                  value: JUJMm9adCgL7FPtF7qiuHjyXYne7ivbX
                - key: molecule-secret-2a
                  value: ggfiFwtaauCRwwNfxJUE3oRjoHr3ETLL

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
