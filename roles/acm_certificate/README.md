# acm\_certificate

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws certificate manager certificates

## Requirements

None

## Role Variables

    acm_certificate_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.acm_certificate
          acm_certificate_list:
            - domain_name: molecule.aws.linuxhq.dev
              type: amazon_issued
              zone: aws.linuxhq.dev

            - domain_name: molecule.aws.linuxhq.net
              subject_alternative_names:
                - molecule-san.aws.linuxhq.net
              type: amazon_issued
              zone: aws.linuxhq.net

            - domain_name: molecule.aws.linuxhq.org
              subject_alternative_names:
                - molecule-san1.aws.linuxhq.org
                - molecule-san2.aws.linuxhq.org
              type: amazon_issued
              zone: aws.linuxhq.org

            - domain_name: molecule-import.linuxhq.net
              certificate: |
                -----BEGIN CERTIFICATE-----
                MIID5TCCAs2gAwIBAgIUOxpEK/lMH4aydk2fnVuhDrj6xBIwDQYJKoZIhvcNAQEL
                BQAwgYExCzAJBgNVBAYTAlVTMRMwEQYDVQQIDApDYWxpZm9ybmlhMRQwEgYDVQQH
                DAtMb3MgQW5nZWxlczEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRk
                MSQwIgYDVQQDDBttb2xlY3VsZS1pbXBvcnQubGludXhocS5uZXQwHhcNMjYwMjI1
                MDAzNTE4WhcNMjcwMjI1MDAzNTE4WjCBgTELMAkGA1UEBhMCVVMxEzARBgNVBAgM
                CkNhbGlmb3JuaWExFDASBgNVBAcMC0xvcyBBbmdlbGVzMSEwHwYDVQQKDBhJbnRl
                cm5ldCBXaWRnaXRzIFB0eSBMdGQxJDAiBgNVBAMMG21vbGVjdWxlLWltcG9ydC5s
                aW51eGhxLm5ldDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJVwuqrL
                N3QVVQo9PDXiD0UmBLAiRXocAx+sz8hmawsZeRmAqKmAy0njqHsB2jwiLgx/eXZW
                mx/aIzVNxPOkVJXyEqvn001Ei3sgWDaNZO85j+vw8IkpsC6yQhenPoNDG+m9WuFO
                QiF4b4v1BGXyEllwfkwxiF1xOyH/z+DMjEa+jqGIL4hqhxUxVMrTxmwkG55hLFKM
                go66ovJrIAv+WtAX0Ngnxl6tL1VxfyNfvNmIPwCZ6WcefMjbKMz8GD9iaV/b7bR5
                DsqbKJjEy3leUw1zrij0iaC6gVBuRqXtNe0qDGZezOQrBILlT5u49nzcMUBh70vm
                FY3b/iXu2wNCdb0CAwEAAaNTMFEwHQYDVR0OBBYEFLNQTwWm0mhsOv1UkbuwVfkT
                uAfEMB8GA1UdIwQYMBaAFLNQTwWm0mhsOv1UkbuwVfkTuAfEMA8GA1UdEwEB/wQF
                MAMBAf8wDQYJKoZIhvcNAQELBQADggEBACLcq1CRM87cBsyLJkNtW0TWzKHQ59n4
                Nhjvqeet5tdwlSxbPjdUKhC0l5y2zAteg4lIkf60EyfprOD+DGEf1ofoDbIbRU4U
                CnVGYO9wNMeqzGoVi2eRqUiauRn/waXCWKA+3Twjq4HjLWBtw3VT/ChtwZhp6M5u
                KdoZo0egL2QBRZUvz55dHehomakiHU6ZlxL1YOi6xmEzYTUTX3yHFxiTcuqJPkQR
                3mF9yUcwxmG/lOb4YZoF0V6tskbFpN89WGZQZD/rHPhQJQBqCTRbdFjdWfMJpiD4
                CDpHgK4TTu+DeJfAuQ9eoIpNAXBSKxItKOnc+uuhElgFbFxFdemfqEs=
                -----END CERTIFICATE-----
              private_key: |
                -----BEGIN PRIVATE KEY-----
                MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCVcLqqyzd0FVUK
                PTw14g9FJgSwIkV6HAMfrM/IZmsLGXkZgKipgMtJ46h7Ado8Ii4Mf3l2Vpsf2iM1
                TcTzpFSV8hKr59NNRIt7IFg2jWTvOY/r8PCJKbAuskIXpz6DQxvpvVrhTkIheG+L
                9QRl8hJZcH5MMYhdcTsh/8/gzIxGvo6hiC+IaocVMVTK08ZsJBueYSxSjIKOuqLy
                ayAL/lrQF9DYJ8ZerS9VcX8jX7zZiD8AmelnHnzI2yjM/Bg/Ymlf2+20eQ7KmyiY
                xMt5XlMNc64o9ImguoFQbkal7TXtKgxmXszkKwSC5U+buPZ83DFAYe9L5hWN2/4l
                7tsDQnW9AgMBAAECggEAB4ZZn+gDrtC0K4PR2FS9uBml+sh+/xsR/TJSdCDUGwb5
                VhNoasCVe+7+uNLrDkQaVX7FuvO5c+0kALcdx7bqm3JJBmbx+N4Ot/B1AKo1/uXD
                HXpQYle7C17mfRJqz2k9qpNiVB4ArnbGByIbSpbZ3a8QbP3BhBMDiz66VPN3zMgP
                45FDJA/SX1jaLyLO77qya/ORTwSyiG7aggvO3+Hjbp3NinWp834nz173B6CIgL5u
                RTU5KLP51o+KgtdpeOvXJEKDn/9j5Nifh4cQi3pkaOIVHIYVNaBLzdlK4jlaxbki
                6wa//ieehJQ5E2Dd1U9BVHAo6wGL63xkt+8kzlH4AQKBgQDPKpMeZH+kw4T1eOpS
                +PivxTl/1KRDNmb1QufqvU6S22E9mZfd1hkyWhT+pz/oowG7zlBP2gX6j53yEs5z
                gKb0omBKnx+g8Ty9rOoCTnItGJcnTznF7fTvV3+lc51cYsHGbzkc0Ic70MA1GMjG
                hudMZkwNNtAPXcLKgwhZjTz8gQKBgQC4qrBHpqK0dWsXBTCo73lzZn+zvQ2se+d3
                AKHbV+/Bte+oooqZ7+aVOOV4N0VdlAJmXcTqs3w6qDh54NEmHZVIq1tf3PNZCltJ
                Fio3v6PbOsvtDF8XMUIzeVACDG+70rcKX+Z2SkiAsLDr/zgVaovOiKunf/MLEpho
                +6hjP4DLPQKBgHhNtwWNQvrBd/K89wacAn7AP3XWXFWTwBJpehg9OuXZdAy7pw9y
                B0vQOCTxpxFHp/gSBV15tMMep5AuD6nPaiTiLpzm7w0dSjKzuWkBeRhrEUwIm/ov
                B2/+FehUzWsbBoBfkoEDL6UywouTCvUO3j7loQCDdiuWPUow8aZfeK0BAoGBALZ7
                pbsIRdxB89NJw64NB10sOqFo/qwlvLNyIn/YRAqOOQfRp1k7IgbvtIK5S4iPjFeP
                7dloCCkGtthpewRJU43+F0uB0c95Vn/AsXNpowgu7/mNsiH/AUZQaOm9VGSsc0iD
                QABAo6jX8d0j1U4EfadYkxfwbkHQ3F9R4DJDPIiZAoGADQ4mMQee19GIvTs1Yy/a
                036r0Zha5WQZG8JMoI8fPrOW6U/zsCr8pWCsESklrF/axJF8ag9vGP4nbU9OYGh0
                xxp4XTP5Q4/pqjllwBJ7MqiLgHZwwEUdt3OINuZZVzXdpfZEFKQCX0HP5hGjvBHp
                JQOfaHvZxdSrflrp+mOC3y8=
                -----END PRIVATE KEY-----
              type: imported

            - domain_name: molecule-import.linuxhq.org
              certificate: |
                -----BEGIN CERTIFICATE-----
                MIID5TCCAs2gAwIBAgIUO2VZAdD82B+mSggcXw6LFVBrWBEwDQYJKoZIhvcNAQEL
                BQAwgYExCzAJBgNVBAYTAlVTMRMwEQYDVQQIDApDYWxpZm9ybmlhMRQwEgYDVQQH
                DAtMb3MgQW5nZWxlczEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRk
                MSQwIgYDVQQDDBttb2xlY3VsZS1pbXBvcnQubGludXhocS5vcmcwHhcNMjYwMjI1
                MDAzNTM3WhcNMjcwMjI1MDAzNTM3WjCBgTELMAkGA1UEBhMCVVMxEzARBgNVBAgM
                CkNhbGlmb3JuaWExFDASBgNVBAcMC0xvcyBBbmdlbGVzMSEwHwYDVQQKDBhJbnRl
                cm5ldCBXaWRnaXRzIFB0eSBMdGQxJDAiBgNVBAMMG21vbGVjdWxlLWltcG9ydC5s
                aW51eGhxLm9yZzCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJ5x4cbF
                Tq8k69YkiPv6Kyhzm//IIGJ9s/dAJjZKT+V1OBr1/GJgdgl+E2AzUqX0pis2cHL3
                PL/nJLG6RfMEeZKUjkItTUOHbAOsJlre0jp13bS5ZSJ3xvdJUm1b9RSbUIwBBguj
                td1+krQVFRkL6YIV5vnzYZPQjQakS+oQFa66xihUnAa0Cu2qnhH23wTDJFbhvYq7
                y+mM9zOwKJxeGKfevbcwJMwKDDIczQkY0CZ6y19dm/B17fdtdAfR+LA68PqwoWOK
                bPaQ4KRZP867ya99BX+WsioRgBXs+yHdCiLcUoFghmQ1v3NOvUPky8/l07+E4ONQ
                cc9FMgOvLbO4GAsCAwEAAaNTMFEwHQYDVR0OBBYEFEyl/FqLLWGZm41STbV12GrM
                VRFeMB8GA1UdIwQYMBaAFEyl/FqLLWGZm41STbV12GrMVRFeMA8GA1UdEwEB/wQF
                MAMBAf8wDQYJKoZIhvcNAQELBQADggEBABa9u+7bjNIAYLMoJx5c9uJpkgby+3fx
                giyl817INPxTbbwC2sz0DrB+ZVwnr8AATquhvcaP8rFDSNVd6w3K7arA7necvTM/
                yYJy79EeaQhLRA9t3DsioVeSYAp4wCpQm24K7MOaCXnhD2ZtBwWtpxY1doDW+NdG
                5QWwDbmb6TYb+5vGDSkoy4+DzrHnY6jvRTJEKtBsOI07UfkRUibmvDzH/JkU1fzJ
                KqOUV63QTBuqsNgR47hbivUoYoLjexwrOO0RWHPdKOMjihjs1Vp8xXfitRWzbdog
                tlGJsn0Uf/BDK9PuMG9THLt6wfAB7kapcDbMJRL0eBFEGrOiar8L6I0=
                -----END CERTIFICATE-----
              private_key: |
                -----BEGIN PRIVATE KEY-----
                MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCeceHGxU6vJOvW
                JIj7+isoc5v/yCBifbP3QCY2Sk/ldTga9fxiYHYJfhNgM1Kl9KYrNnBy9zy/5ySx
                ukXzBHmSlI5CLU1Dh2wDrCZa3tI6dd20uWUid8b3SVJtW/UUm1CMAQYLo7XdfpK0
                FRUZC+mCFeb582GT0I0GpEvqEBWuusYoVJwGtArtqp4R9t8EwyRW4b2Ku8vpjPcz
                sCicXhin3r23MCTMCgwyHM0JGNAmestfXZvwde33bXQH0fiwOvD6sKFjimz2kOCk
                WT/Ou8mvfQV/lrIqEYAV7Psh3Qoi3FKBYIZkNb9zTr1D5MvP5dO/hODjUHHPRTID
                ry2zuBgLAgMBAAECggEAGGHD8ZeJPTB8Ti6/Ga9slsP7nIfKW/2mBQVNHAuhcdjw
                8k0qMmVPpLRO/P3I2Rrluz6cXUSoh4tlPShB/VyR7LmJjqtz+VFMkOAb4t3pEe/z
                Vw00f/JYntMcqRF+jFY+Nd0udfoSUWxZ3PZlkb4gh9EhAxOtz1ZHbV85A2LIQ2Pi
                ei1R9gzzyWp0ujzGfV5ERvKByHsoO4ExmRrw9kNnLQRlY2FaxbHLYk+8GRLOEEeO
                iTrODnVbO8Wyn+WLM5z9URfVY+xrvD3yAmubrlUwdjY7bQYOTl6Oie6boQctEo2o
                DAoZHVaAynJjhnE9kgWUEGELDV6rMV7+vqPYE0hX8QKBgQDPFxpBfN2bD2DMuDdp
                wONdn91l13XgGVvS09lh0jbMnHJVbYUrCMpRwF8Mv79w8G4dcWzH5M1pwdN4ZgIz
                d/oaJJLD8DWv86HG62UkG0hwzy/mLkWRR5St+LCRw98daZwyUYaW6RS/RvAafHh0
                UuBEdmJxWG2ezL78Icu46qyZmQKBgQDD3aB/DpLxxoXFjgBSW7DTC9THhKTQjyWQ
                c+3524hN8BHz+54tmJbLUnb+r5LqHIxKZz5LMURoqgpszidRcDH9v5JXTQ5uwqtR
                dPv5iQlsie0t2zeb4suxIK88UcL63pj7DrigoGCVvQ4kpiaCaAzxwJCKpHR9dsd+
                7A15bWwtQwKBgQDGB+OVqCAJ/WSln6ttt4Q0rYD7uFQCHn3OV8NSZcD9XMWAp6Bm
                jJtcHcdG273n9CJ4iVRquoMrlKvyQCnuqdZCVaL7N6M/RIz5OXSYWHanWZkGVk00
                Je0ph9zhJxsedzVkcM1xViX+24kS6uAM7IuFLGfq15LL/iLL3E2B4Pd4UQKBgHpv
                ZO9npdV62o5GmM7iwCL9B1J9CSXSBZJJ1Z3VbFwD0MUqKZOpCcIpV3cXO4gatlug
                NCF+t5uRh5jCOXO/5ZAQG6N06Ku2Bq+RqB0xW3G8ukVq/lT0rY2Yt9HF7lMxqIFv
                j1vhRN71Ygzoy7PC5SyNygzQhn0TLduaJUYdb3zPAoGAH//ZVHb44EYSYTKXJK3o
                XDKKOfAZ3aaCZbBA3xNBW3/YaKThKeulFGqKLbxF6ZAohneBVeCcjfbuT0FtCchU
                Nyx2cqcXXL9uIx0ISzf3MgdVBPcKlfK0eiUzwqZK8Jgleaox9gfz7v7YiWJV393g
                zFnNQFIRbIXCNJFLkHQcrEM=
                -----END PRIVATE KEY-----
              type: imported

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
