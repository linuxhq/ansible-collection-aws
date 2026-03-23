# ec2\_vol

Manage aws ec2 volumes

## Requirements

None

## Role Variables

    ec2_vol_async: 300
    ec2_vol_batch: 10
    ec2_vol_delay: 3
    ec2_vol_list: []
    ec2_vol_poll: 0
    ec2_vol_retries: 100

## Return Values

None

## Dependencies

* [ec2\_instance\_info](../ec2_instance_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vol
          ec2_vol_list:
            - instance: "{{ _ec2_instance_info_dict['linuxhq-1'].instance_id }}"
              volumes:
                - name: linuxhq-vol-a-01
                  device_name: sdf
                  volume_size: 10
                - name: linuxhq-vol-a-02
                  device_name: sdg
                  volume_size: 50
