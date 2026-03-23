# ecs\_ecr

Manage aws elastic container registry repositories

## Requirements

None

## Role Variables

    ecs_ecr_async: 300
    ecs_ecr_batch: 10
    ecs_ecr_delay: 3
    ecs_ecr_list: []
    ecs_ecr_poll: 0
    ecs_ecr_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ecs_ecr
          ecs_ecr_list:
            - name: molecule-00
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-01
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-02
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-03
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-04
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-05
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-06
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-07
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-08
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-09
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-10
              image_tag_mutability: immutable
              scan_on_push: true
            - name: molecule-11
              image_tag_mutability: immutable
              scan_on_push: true
