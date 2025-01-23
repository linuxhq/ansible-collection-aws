# ec2\_placement\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 placement groups

## Requirements

None

## Role Variables

    ec2_placement_group_list: []
    ec2_placement_group_async: 300
    ec2_placement_group_batch: 10
    ec2_placement_group_delay: 3
    ec2_placement_group_poll: 0
    ec2_placement_group_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_placement_group
          ec2_placement_group_list:
            - strategy: cluster
              placement_groups:
                - name: linuxhq-cluster-1
                - name: linuxhq-cluster-2

            - strategy: partition
              placement_groups:
                - name: linuxhq-partition-3
                  partition_count: 3
                - name: linuxhq-partition-5
                  partition_count: 5
                - name: linuxhq-partition-7
                  partition_count: 7

            - strategy: spread
              placement_groups:
                - name: linuxhq-spread-1
                - name: linuxhq-spread-2

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
