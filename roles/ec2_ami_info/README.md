# ec2\_ami\_info

Gather information about ec2 amazon machine images

## Requirements

None

## Role Variables

    ec2_ami_info_list: []

## Return Values

    _ec2_ami_info_dict
    _ec2_ami_info_latest
    _ec2_ami_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_ami_info
          ec2_ami_info_list:
            - name: 'AlmaLinux OS 8'
              filters:
                owner-alias: aws-marketplace
                product-code: be714bpjscoj5uvqz0of5mscl
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm

            - name: 'AlmaLinux OS 9'
              filters:
                owner-alias: aws-marketplace
                product-code: 3kukoxmnoighcsbjd0u4nq9ds
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm
