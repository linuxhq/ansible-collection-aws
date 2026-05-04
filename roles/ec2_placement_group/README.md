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
                - name: molecule-cluster-1
                - name: molecule-cluster-2
                - name: molecule-cluster-3
                - name: molecule-cluster-4
                - name: molecule-cluster-5
                - name: molecule-cluster-6

            - strategy: partition
              placement_groups:
                - name: molecule-partition-1
                  partition_count: 3
                - name: molecule-partition-2
                  partition_count: 3
                - name: molecule-partition-3
                  partition_count: 3
                - name: molecule-partition-4
                  partition_count: 5
                - name: molecule-partition-5
                  partition_count: 5
                - name: molecule-partition-6
                  partition_count: 5
                - name: molecule-partition-7
                  partition_count: 7
                - name: molecule-partition-8
                  partition_count: 7
                - name: molecule-partition-9
                  partition_count: 7

            - strategy: spread
              placement_groups:
                - name: molecule-spread-1
                - name: molecule-spread-2
                - name: molecule-spread-3
                - name: molecule-spread-4
                - name: molecule-spread-5
                - name: molecule-spread-6
