# ec2\_key

Manage aws ec2 keys

## Requirements

None

## Role Variables

    ec2_key_async: 300
    ec2_key_batch: 10
    ec2_key_delay: 3
    ec2_key_list: []
    ec2_key_poll: 0
    ec2_key_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_key
          ec2_key_list:
            - name: molecule-key-00
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBwCfEABKtScVJMqT8kH0rdaisRopPeLqAUnRz4BKM7S
            - name: molecule-key-01
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAV6GByXu+D2me8eLgy1ujOj/tFRFwKjluWn+lmWr9av
            - name: molecule-key-02
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKBH5OIuoGk2OTlwrhNKX9lGPDSXfVqY9OwQAMgLEfor
            - name: molecule-key-03
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINlCnrYPAfETJyDv/rKSRntSE/wqJUCDxn+QO2zOYHED
            - name: molecule-key-04
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGboQhfGPVzQPUtmVGFpLjQLtCgRxgQmEMDx+HdmPRTQ
            - name: molecule-key-05
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGpQiy2kRbAo+0LJfV4RHnuYyozFjHZn9c6cL6pVii+5
            - name: molecule-key-06
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAg+X8TSbLxRq2zRJbg0ZfYYmnqjtLUsHFtsfeMklOgX
            - name: molecule-key-07
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDFgaw1OtDFwiaY+lccD1UvXzEU5bNTdGQhOoyYyGcwo
            - name: molecule-key-08
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIRtpHq0ih6ZsXzskVMqHLc3bvCp82l1lS/V9i3wXwQQ
            - name: molecule-key-09
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEQYZwthruEeeRtn4QE2x5xeVosMNha99UOVptoNjVbs
            - name: molecule-key-10
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG1XSQ4t5M0dmwHv3CHWmQ5d+55DGxS0ehgip5JLHDpi
            - name: molecule-key-11
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGQ26Bz62FT0ugZBU5uqXzULR4LehVtRJkUp9FRUuxFk
            - name: molecule-key-12
              key_material: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINCvQSZAZdDyfA6uWBsQbuQwOxPQRT+aZWXY7wQjbXca
