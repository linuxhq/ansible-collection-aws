# s3\_lifecycle

Manage aws simple storage service bucket lifecycle rules

## Requirements

None

## Role Variables

    s3_lifecycle_async: 300
    s3_lifecycle_batch: 1
    s3_lifecycle_delay: 3
    s3_lifecycle_list: []
    s3_lifecycle_poll: 0
    s3_lifecycle_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_lifecycle
          s3_lifecycle_list:
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-00"
              wait: true
              lifecycle_rules:
                - rule_id: molecule-1d-glacier
                  transition_days: 1
                  prefix: 1d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-10d-glacier
                  transition_days: 10
                  prefix: 10d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-15d-glacier
                  transition_days: 15
                  prefix: 15d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-30d-glacier
                  transition_days: 30
                  prefix: 30d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-60d-glacier
                  transition_days: 60
                  prefix: 60d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-90d-glacier
                  transition_days: 90
                  prefix: 90d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-120d-glacier
                  transition_days: 120
                  prefix: 120d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-240d-glacier
                  transition_days: 240
                  prefix: 240d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-365d-glacier
                  transition_days: 365
                  prefix: 365d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-730d-glacier
                  transition_days: 730
                  prefix: 730d/
                  status: enabled
                  storage_class: glacier
                - rule_id: molecule-1095d-glacier
                  transition_days: 1095
                  prefix: 1095d/
                  status: enabled
                  storage_class: glacier
