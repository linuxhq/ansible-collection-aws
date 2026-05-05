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
                schema_version: '2.2'
                description: Run a shell command
                main_steps:
                  - action: aws:runShellScript
                    name: runShellScript
                    inputs:
                      run_command:
                        - echo molecule
            - name: molecule-command-env
              document_type: Command
              content:
                schema_version: '2.2'
                description: Print environment
                main_steps:
                  - action: aws:runShellScript
                    name: printEnvironment
                    inputs:
                      run_command:
                        - env | sort
            - name: molecule-session-shell
              document_type: Session
              content:
                schema_version: '1.0'
                description: Session Manager shell preferences
                session_type: Standard_Stream
                inputs:
                  idle_session_timeout: 60
                  run_as_enabled: false
                  shell_profile:
                    linux: cd
                    windows: ''
