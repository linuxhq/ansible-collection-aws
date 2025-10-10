# ec2\_vol

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws ec2 volumes

## Requirements

None

## Role Variables

    ec2_vol_list: []
    ec2_vol_async: 300
    ec2_vol_batch: 10
    ec2_vol_delay: 3
    ec2_vol_poll: 0
    ec2_vol_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_instance\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_instance_info)

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

## License

Copyright (c) Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
