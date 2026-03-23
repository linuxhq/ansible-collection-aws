# s3\_website

Manage aws simple storage service bucket websites

## Requirements

None

## Role Variables

    s3_website_async: 300
    s3_website_batch: 10
    s3_website_delay: 3
    s3_website_list: []
    s3_website_poll: 0
    s3_website_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_website
          s3_website_list:
            - name: "molecule-bucket-{{ ansible_facts.date_time.date }}-00"
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
