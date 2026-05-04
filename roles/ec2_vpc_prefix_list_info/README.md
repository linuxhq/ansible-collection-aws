# ec2\_vpc\_prefix\_list\_info

Gather information about virtual private cloud prefix lists

## Role Variables

    ec2_vpc_prefix_list_info_name: null

## Return Values

    _ec2_vpc_prefix_list_info_dict
    _ec2_vpc_prefix_list_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ec2_vpc_prefix_list_info
