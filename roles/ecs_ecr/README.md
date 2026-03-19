# ecs\_ecr

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws elastic container registry repositories

## Requirements

None

## Role Variables

    ecs_ecr_async: 300
    ecs_ecr_batch: 10
    ecs_ecr_delay: 3
    ecs_ecr_list: []
    ecs_ecr_poll: 0
    ecs_ecr_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ecs_ecr
          ecs_ecr_list:
            - name: molecule-00
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-01
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-02
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-03
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-04
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-05
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-06
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-07
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-08
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-09
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-10
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-11
              image_tag_mutability: immutable
              scan_on_push: true

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
