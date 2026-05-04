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
            - name: molecule-command-shell
              document_type: Command
              content:
                schemaVersion: '2.2'
                description: Run a shell command
                mainSteps:
                  - action: aws:runShellScript
                    name: runShellScript
                    inputs:
                      runCommand:
                        - echo molecule
            - name: molecule-command-env
              document_type: Command
              content:
                schemaVersion: '2.2'
                description: Print environment
                mainSteps:
                  - action: aws:runShellScript
                    name: printEnvironment
                    inputs:
                      runCommand:
                        - env | sort
            - name: molecule-session-shell
              document_type: Session
              content:
                schemaVersion: '1.0'
                description: Session Manager shell preferences
                sessionType: Standard_Stream
                inputs:
                  idleSessionTimeout: 60
                  runAsEnabled: false
                  shellProfile:
                    linux: cd
                    windows: ''
