# s3\_bucket

Manage aws simple storage service buckets

## Requirements

None

## Role Variables

    s3_bucket_async: 300
    s3_bucket_batch: 10
    s3_bucket_delay: 3
    s3_bucket_list: []
    s3_bucket_poll: 0
    s3_bucket_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_bucket
          s3_bucket_list:
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-00"
              accelerate_enabled: true
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Deny
                    Action: s3:*
                    Principal: '*'
                    Resource:
                      - "arn:aws:s3:::molecule-bucket-{{ ansible_facts.date_time.date }}-00"
                      - "arn:aws:s3:::molecule-bucket-{{ ansible_facts.date_time.date }}-00/*"
                    Condition:
                      Bool:
                        aws:SecureTransport: false
              public_access:
                block_public_acls: true
                block_public_policy: true
                ignore_public_acls: true
                restrict_public_buckets: true

            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-01"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-02"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-03"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-04"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-05"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-06"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-07"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-08"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-09"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-10"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-11"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-12"
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-13"
