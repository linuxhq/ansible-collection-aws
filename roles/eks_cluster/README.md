# eks\_cluster

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws elastic kubernetes service clusters

## Requirements

None

## Role Variables

    eks_cluster_list: []

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)
* [linuxhq.aws.ec2\_vpc\_subnet\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.eks_cluster
          eks_cluster_list:
            - name: molecule-eks1
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-c'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-d'].id }}"
              version: 1.34
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

            - name: molecule-eks2
              iam_managed_policies:
                - AmazonEKSClusterPolicy
                - AmazonS3FullAccess
              iam_role_name: MoleculeEksClusterRole
              rules:
                - cidr_ip: 10.0.0.0/8
                  ports:
                    - 443
                  proto: tcp
              rules_egress:
                - cidr_ip: 10.0.0.0/8
                  ports:
                    - 0-65535
                  proto: tcp
              subnets:
                - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-c'].id }}"
                - "{{ _ec2_vpc_subnet_info_dict['molecule-d'].id }}"
              version: 1.35
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

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
