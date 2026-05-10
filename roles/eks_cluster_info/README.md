# eks\_cluster\_info

Gather information about eks clusters

## Requirements

None

## Role Variables

    eks_cluster_info_filters: {}
    eks_cluster_info_include: []
    eks_cluster_info_names: []

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
