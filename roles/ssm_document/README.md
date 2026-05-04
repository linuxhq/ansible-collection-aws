# ssm\_document

Manage aws systems manager documents

## Role Variables

    ssm_document_async: 300
    ssm_document_batch: 10
    ssm_document_delay: 3
    ssm_document_list: []
    ssm_document_poll: 0
    ssm_document_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_document
          ssm_document_list:
            - name: SSM-SessionManagerRunShell
              document_type: Session
              content:
                schemaVersion: '1.0'
                description: Document to hold regional settings for Session Manager
                sessionType: Standard_Stream
                inputs:
                  idleSessionTimeout: 60
