# ec2\_placement\_group

Manage aws ec2 placement groups

## Requirements

None

## Role Variables

    ec2_placement_group_async: 300
    ec2_placement_group_batch: 10
    ec2_placement_group_delay: 3
    ec2_placement_group_list: []
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
