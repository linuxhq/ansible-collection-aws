# eks\_cluster\_info

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Gather information about eks clusters

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _eks_cluster_info_arn
    _eks_cluster_info_endpoint
    _eks_cluster_info_identity_oidc_issuer
    _eks_cluster_info_kubernetes_network_config
    _eks_cluster_info_list
    _eks_cluster_info_logging
    _eks_cluster_info_names
    _eks_cluster_info_platform_version
    _eks_cluster_info_resources_vpc_config
    _eks_cluster_info_role_arn
    _eks_cluster_info_status
    _eks_cluster_info_version

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.eks_cluster_info

## License

Copyright (C) 2023 Linux HeadQuarters

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
