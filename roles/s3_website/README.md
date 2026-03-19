# s3\_website

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

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
