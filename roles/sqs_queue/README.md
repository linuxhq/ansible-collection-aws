# sqs\_queue

Manage aws simple queue service queues

## Requirements

None

## Role Variables

    sqs_queue_async: 300
    sqs_queue_batch: 10
    sqs_queue_delay: 3
    sqs_queue_list: []
    sqs_queue_poll: 0
    sqs_queue_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.sqs_queue
          sqs_queue_list:
            - name: molecule-bounce
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS:
                        - "arn:aws:iam::{{ _aws_caller_info_account }}:root"
                    Action:
                      - sqs:*
                    Resource:
                      - "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-bounce"
                  - Effect: Allow
                    Principal:
                      Service: sns.amazonaws.com
                    Action:
                      - sqs:SendMessage
                    Resource:
                      - "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-bounce"
                    Condition:
                      ArnEquals:
                        'aws:SourceArn':
                          "arn:aws:sns:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-bounce"

            - name: molecule-complaint
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS:
                        - "arn:aws:iam::{{ _aws_caller_info_account }}:root"
                    Action:
                      - sqs:*
                    Resource:
                      - "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-complaint"
                  - Effect: Allow
                    Principal:
                      Service: sns.amazonaws.com
                    Action:
                      - sqs:SendMessage
                    Resource:
                      - "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-complaint"
                    Condition:
                      ArnEquals:
                        'aws:SourceArn':
                          "arn:aws:sns:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-complaint"

            - name: molecule-delivery
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS:
                        - "arn:aws:iam::{{ _aws_caller_info_account }}:root"
                    Action:
                      - sqs:*
                    Resource:
                      - "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-delivery"
                  - Effect: Allow
                    Principal:
                      Service: sns.amazonaws.com
                    Action:
                      - sqs:SendMessage
                    Resource:
                      - "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-delivery"
                    Condition:
                      ArnEquals:
                        'aws:SourceArn':
                          "arn:aws:sns:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-delivery"
