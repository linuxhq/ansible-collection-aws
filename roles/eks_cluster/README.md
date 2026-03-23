# eks\_cluster

Manage aws elastic kubernetes service clusters

## Requirements

None

## Role Variables

    eks_cluster_list: []

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

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
              wait: true

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
              wait: true
