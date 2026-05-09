# eks\_cluster

Manage aws elastic kubernetes service clusters

## Requirements

None

## Role Variables

    eks_cluster_async: 1200
    eks_cluster_batch: 10
    eks_cluster_delay: 30
    eks_cluster_list: []
    eks_cluster_poll: 0
    eks_cluster_retries: 40

## Return Values

None

## Dependencies

* [ec2\_security\_group\_info](../ec2_security_group_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.eks_cluster
          eks_cluster_list:
            - name: molecule-eks1
              resources_vpc_config:
                security_group_ids:
                  - "{{ _ec2_security_group_info_dict['molecule-eks1'].group_id }}"
                subnet_ids:
                  - "{{ _ec2_vpc_subnet_info_dict['molecule-a'].id }}"
                  - "{{ _ec2_vpc_subnet_info_dict['molecule-c'].id }}"
                  - "{{ _ec2_vpc_subnet_info_dict['molecule-d'].id }}"
              role_arn: "arn:aws:iam::{{ _aws_caller_info_account }}:role/molecule-eks1"
              version: '1.34'
              wait: true
