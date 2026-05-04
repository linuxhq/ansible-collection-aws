# eks\_cluster\_info

Gather information about eks clusters

## Requirements

None

## Role Variables

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

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.eks_cluster_info
          eks_cluster_info_name: molecule-eks1
