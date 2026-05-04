# sns\_topic

Manage aws simple notification service topics

## Role Variables

    sns_topic_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.sns_topic
          sns_topic_list:
            - name: molecule-bounce
              subscriptions:
                - endpoint: "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-bounce"
                  protocol: sqs
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      Service: ses.amazonaws.com
                    Action:
                      - sns:Publish
                    Resource:
                      - "arn:aws:sns:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-bounce"
                    Condition:
                      StringEquals:
                        'AWS:SourceAccount': "{{ _aws_caller_info_account }}"
                        'AWS:SourceArn':
                          - "arn:aws:ses:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:identity/molecule.org"

            - name: molecule-complaint
              subscriptions:
                - endpoint: "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-complaint"
                  protocol: sqs
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      Service: ses.amazonaws.com
                    Action:
                      - sns:Publish
                    Resource:
                      - "arn:aws:sns:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-complaint"
                    Condition:
                      StringEquals:
                        'AWS:SourceAccount': "{{ _aws_caller_info_account }}"
                        'AWS:SourceArn':
                          - "arn:aws:ses:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:identity/molecule.org"

            - name: molecule-delivery
              subscriptions:
                - endpoint: "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-delivery"
                  protocol: sqs
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      Service: ses.amazonaws.com
                    Action:
                      - sns:Publish
                    Resource:
                      - "arn:aws:sns:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-delivery"
                    Condition:
                      StringEquals:
                        'AWS:SourceAccount': "{{ _aws_caller_info_account }}"
                        'AWS:SourceArn':
                          - "arn:aws:ses:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:identity/molecule.org"
