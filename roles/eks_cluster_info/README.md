# eks\_cluster\_info

Gather information about aws eks clusters

## Requirements

None

## Role Variables

    eks_cluster_info_filters: {}
    eks_cluster_info_include: []
    eks_cluster_info_name: null

## Return Values

    _eks_cluster_info_dict
    _eks_cluster_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.eks_cluster_info
