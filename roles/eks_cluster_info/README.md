# eks\_cluster\_info

Gather information about eks clusters

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

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
