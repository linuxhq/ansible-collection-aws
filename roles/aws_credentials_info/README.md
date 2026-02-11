# aws\_credentials\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about aws credentials

## Requirements

None

## Role Variables

    aws_credentials_info_file: ~/.aws/credentials
    aws_credentials_info_keys:
      - aws_access_key_id
      - aws_secret_access_key
      - aws_security_token
      - aws_session_token
    aws_credentials_info_profile: default

## Return Values

    _aws_credentials_info_aws_access_key_id
    _aws_credentials_info_aws_secret_access_key
    _aws_credentials_info_aws_security_token
    _aws_credentials_info_aws_session_token
    _aws_credentials_info_{{ key }}

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.aws_credentials_info

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
