# iam\_role

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws identity and access management roles

## Requirements

None

## Role Variables

    iam_role_list: []
    iam_role_async: 300
    iam_role_batch: 10
    iam_role_delay: 3
    iam_role_poll: 0
    iam_role_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_role
          iam_role_list:
            - name: LinuxHQEKSNodeGroup
              assume_role_policy_document:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      Service: ec2.amazonaws.com
                    Action:
                      - sts:AssumeRole
              managed_policies:
                - AmazonEC2ContainerRegistryReadOnly
                - AmazonEKS_CNI_Policy
                - AmazonEKSWorkerNodePolicy
                - AmazonSSMManagedInstanceCore
                - AmazonS3ReadOnlyAccess
                - CloudWatchAgentServerPolicy

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
