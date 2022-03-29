# Sample objects used in various tests.
# flake8: noqa: W291,W293

SAMPLE_AS_BLOCK = """as-block:       AS65536 - as065538
descr:          TEST ASN block
remarks:        test remark
mnt-by:         TEST-MNT
changed:        changed@example.com  # only changed line without date
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
source:         TEST
remarks:        remark
"""

SAMPLE_AS_SET = """as-set:         AS65537:AS-SETTEST
descr:          description
members:        AS65538, AS65539
members:        AS65537
members:        AS-OTHERSET
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
notify:         notify@example.com
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_AUT_NUM = """aut-num:        as065537
as-name:        TEST-AS
descr:          description
+               foo
remarks:        ---> Uplinks
export:         to AS3356 announce AS-SETTEST
import:         from AS3356 accept ANY
export:         to AS174 announce AS-SETTEST
import:         from AS174 accept ANY
mp-export:      afi ipv6.unicast to AS174 announce AS-SETTEST
mp-import:      afi ipv6.unicast from AS174 accept ANY
export:         to AS8359 announce AS-SETTEST
import:         from AS8359 accept ANY
export:         to AS3257 announce AS-SETTEST
import:         from AS3257 accept ANY
export:         to AS3549 announce AS-SETTEST
import:         from AS3549 accept ANY
export:         to AS9002 announce AS-SETTEST
import:         from AS9002 accept ANY
mp-export:      afi ipv6.unicast to AS9002 announce AS-SETTEST
mp-import:      afi ipv6.unicast from AS9002 accept ANY
remarks:        ---> Peers
export:         to AS31117 announce AS-SETTEST AS-UAIX
import:         from AS31117 accept AS-ENERGOTEL
export:         to AS8501 announce AS-SETTEST AS-UAIX
import:         from AS8501 accept AS-PLNET
export:         to AS35297 announce AS-SETTEST
import:         from AS35297 accept AS-DL-WORLD
export:         to AS13188 announce AS-SETTEST
import:         from AS13188 accept AS-BANKINFORM
export:         to AS12389 announce AS-SETTEST
import:         from AS12389 accept AS-ROSTELECOM
export:         to AS35395 announce AS-SETTEST
import:         from AS35395 accept AS-GECIXUAIX
export:         to AS50952 announce AS-SETTEST
import:         from AS50952 accept AS-DATAIX
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_DOMAIN = """domain:         2.0.192.in-addr.arpa
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
zone-c:         PERSON-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
                # foo
remarks:        remark
"""

SAMPLE_FILTER_SET = """filter-set:     fltr-settest
descr:          Generic anti-bogons filter
remarks:        http://www.iana.org/assignments/ipv4-address-space
filter:         {
                1.0.0.0/8^- ,
                2.0.0.0/8^- ,
                5.0.0.0/8^- ,
                7.0.0.0/8^- ,
                10.0.0.0/8^- ,
                23.0.0.0/8^- ,
                27.0.0.0/8^- ,
                31.0.0.0/8^- ,
                36.0.0.0/8^- ,
                37.0.0.0/8^- ,
                39.0.0.0/8^- ,
                41.0.0.0/8^- ,
                42.0.0.0/8^- ,
                49.0.0.0/8^- ,
                50.0.0.0/8^- ,
                58.0.0.0/8^- ,
                59.0.0.0/8^- ,
                60.0.0.0/8^- ,
                70.0.0.0/8^- ,
                71.0.0.0/8^- ,
                72.0.0.0/8^- ,
                73.0.0.0/8^- ,
                74.0.0.0/8^- ,
                75.0.0.0/8^- ,
                76.0.0.0/8^- ,
                77.0.0.0/8^- ,
                78.0.0.0/8^- ,
                79.0.0.0/8^- ,
                83.0.0.0/8^- ,
                84.0.0.0/8^- ,
                85.0.0.0/8^- ,
                86.0.0.0/8^- ,
                87.0.0.0/8^- ,
                88.0.0.0/8^- ,
                89.0.0.0/8^- ,
                90.0.0.0/8^- ,
                91.0.0.0/8^- ,
                92.0.0.0/8^- ,
                93.0.0.0/8^- ,
                94.0.0.0/8^- ,
                95.0.0.0/8^- ,
                96.0.0.0/8^- ,
                97.0.0.0/8^- ,
                98.0.0.0/8^- ,
                99.0.0.0/8^- ,
                100.0.0.0/8^- ,
                101.0.0.0/8^- ,
                102.0.0.0/8^- ,
                103.0.0.0/8^- ,
                104.0.0.0/8^- ,
                105.0.0.0/8^- ,
                106.0.0.0/8^- ,
                107.0.0.0/8^- ,
                108.0.0.0/8^- ,
                109.0.0.0/8^- ,
                110.0.0.0/8^- ,
                111.0.0.0/8^- ,
                112.0.0.0/8^- ,
                113.0.0.0/8^- ,
                114.0.0.0/8^- ,
                115.0.0.0/8^- ,
                116.0.0.0/8^- ,
                117.0.0.0/8^- ,
                118.0.0.0/8^- ,
                119.0.0.0/8^- ,
                120.0.0.0/8^- ,
                121.0.0.0/8^- ,
                122.0.0.0/8^- ,
                123.0.0.0/8^- ,
                124.0.0.0/8^- ,
                125.0.0.0/8^- ,
                126.0.0.0/8^- ,
                127.0.0.0/8^- ,
                169.254.0.0/16^- ,  # The next two lines were introduced to test blank lines with correct cont. chars
                172.16.0.0/12^- ,   # Note that the trailing whitespace is significant.
\t               
+               
                192.0.2.0/24^- ,
                192.168.0.0/16^- ,
                197.0.0.0/8^- ,
                201.0.0.0/8^- ,
                222.0.0.0/8^- ,
                223.0.0.0/8^- ,
                224.0.0.0/3^-
                }
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_INET_RTR = """inet-rtr:       rtr.example.com
local-as:       AS65537
ifaddr:         192.0.2.1 masklen 30
peer:           BGP4 192.0.2.2 asno(as65530)
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_INET6NUM = """inet6num:       2001:db8::/48
netname:        NET-TEST-V6
country:        DE
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
mnt-by:         TEST-MNT
status:         ASSIGNED
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_INETNUM = """inetnum:        192.0.2.0 - 192.0.02.255
netname:        NET-TEST-V4
descr:          description
country:        IT
notify:         notify@example.com
geofeed:        https://example.com/geofeed
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
status:         ASSIGNED PA
mnt-by:         test-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_KEY_CERT = """key-cert:       PGPKEY-80F238C6
method:         PGP
owner:          Sasha Romijn <sasha@mxsasha.eu>
owner:          Sasha Romijn <sasha@dashcare.nl>
owner:          keybase.io/mxsasha <mxsasha@keybase.io>
owner:          Sasha Romijn <gpg@mxsasha.eu>
fingerpr:       8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6
certif:         -----BEGIN PGP PUBLIC KEY BLOCK-----
                
                mQINBFnY7YoBEADH5ooPsoR9G/dNxrdHRMJeDHXCSQbwgXWEez5/F8/BZKV9occ/
certif:         jZ7w2wH+Ghj4vTQl1DhuNcxi60qDv9DAPxG73DkBrK0I3fDUJUPrdOKW9SXvZCAq
certif:         LrVEdDVH+YEKhQLlGG7DTODGsfMglL98mn7GD/wD64LtRF3eBAucTIjaOl9hvoqX
certif:         RkH2pQnv/hZKARSS+CYeEpxxdphPM1gm21mSaPYNsKknCIVQsZhHub2PomQWX/AI
certif:         6ZXWmJWObwUlZWEb8CaVBY4+uq6D5sMzUfHsajVJcSHb7l7RnYtCoPaSI5Tj2g22
certif:         q960t9eMEMAtlKm5dvjBcFSQg6sLEJ8YAKa2nxeRyBiapb4kWxn3OhvpDp9XGs3p
certif:         ETyGlT1dUYKcg4QBFKo9x/XydWZRg/tVnZdJX3C8ix+svl4EpIWUowHeSTuQKFK7
certif:         WzS1LzAH6XOaXHRNBLTRYGqb6i/QI6u/hWKqYUu0PtBhu1k0tSmt02ve+YfL3WTZ
certif:         o8VIX2zUSxvnzA4X72Kmc/ni09nNUKlK6MlIAPUxM5cqbGwYRa7WteZCY0iQw+y7
certif:         yC/dNUMT1SrQciFIbd274Z1Mmq7JxxVAmTtQjhFl0dQ/B+PN2m3itm63HsAfiOe0
certif:         Pmj2nprctGShzT4wFrTqi/4NwN8MmEo8n8IHmOye42aLh/FUfso5o5GpPwARAQAB
certif:         tB9TYXNoYSBSb21pam4gPHNhc2hhQG14c2FzaGEuZXU+iQJTBBMBCAA9AhsDBwsJ
certif:         CAcDAgEGFQgCCQoLBBYCAwECHgECF4ACGQEWIQSGJh2Nvr2k9UaS1k2oODungPI4
certif:         xgUCWmh31QAKCRCoODungPI4xkZGD/9+lmMWXj8UgYvjNonad/hcZCjQrWmm+LJf
certif:         DLTS2ZBlNOlkp9rLp2wT+3eTRo2B+e9AlKPfCRTH3e3RRurjqFM5OfWUCLINbPMy
certif:         PfGU9kxCWGunA3mFn2lzAG671vGME7Wjgzga1IsjoIKeRDeFO8qrWBm76ntrXi6n
certif:         q2WB6sEiimrZFdC8DFzwJ4BGwx5GpfL857hlp+2MBCYyJgWOhhQCXVl3r/vcXGq1
certif:         W3qayl8ATASbvihUHLY13BeJIZz2rGKq0VHXAgghu2y42YbyXZji4u3o/Q6hGK/P
certif:         kYFRrJYzJgAVYL4/24xIjEBW381+TYnTzmwKkWYn8Npd5oo/c2ugInh+lr0NspQ5
certif:         vEoNuKgxqC2dS/bD+wH0eSvxQqJdy1eFM5DIxpaNuKc009tUcTBL9zuW4nVQ9fro
certif:         mILFDQeJMK3Ru2ui4hlRqpVTgoKhbnKC10QLjbSOEJSSLWr9kJJrBRbw37Fil/nB
certif:         IisGapf/6zR4C8vLK9Eyo0XdDK3WAimfOE57InuhTimns52R/MZQLnjwmstJmidG
certif:         N0ui29Q48GGbxpc5aXfqV7k5yPJadujKw3SGiRhspG1loQ6SSNacWKJceGS2oIo3
certif:         KVt7/yxkYu2Jn72Ba4FrASiSSmfe4YwySH4q4ru95Es/pp5JQepveg5vSNrOez+i
certif:         1zRcLUpp+4kCHAQTAQgABgUCWdjvjAAKCRCJbs//g9ixtGc+D/4nEFp/G7X/IvZI
certif:         rKiinj9tvSucLskcr3AWFPF7AXXEkc/PK6Ak0sFXUGncKULTy031tSK51mqf7khm
certif:         EUCmhip1h63cyCEbNVMvTyG3GxbKP2Zd1Hpj53qC66cqOfYjjWF1Xjhi2jjAFbaV
certif:         3evE3hdVC0f/1AdlWlueHT6oZHcN9AvXTEKTAalZKYUmjxHRaVsNXxJ/PYwDtC6L
certif:         Pr+tpCcXVqxdeggahse2mKu02CL2SW5YdMst6nsiDHlozk/04wAmwi1kpTy1ZRo9
certif:         V/dXR7qJp1D5SlnfJugAhKzllIx9NtROs1wH35FDnCElyRne1izUaAyEALjVCZ1S
certif:         CziBsNLSGweXDp+rHZf+vAxq7qg3rB1wAuc0i9MiXYuQObxzTPZGXk0BEzVbc83Z
certif:         nIA6LgF5K39z4VUmj37Pd5k/CCA5zQYd+bD74uXJ+5RcyyG7qb3hugiQarhDOWq8
certif:         nCNjTOjXFGke9/kyStszcTNdQ+0/2igr12gp1jWwFQBM5yUjGjaAtAwb4txeZ7U0
certif:         wx/+l8jvzzM7cMPhypmYvLpg/mV5QpImftpAnZ5pYOG/e3f1w6sOvHwYEwVG14yw
certif:         5ZyUOwv8cGCV99ziiKNnUOhp88qcag8Orw2+IdS6ErKZJRlHRMp40jjmoQ25zi5X
certif:         1PCW14mVRiqLmBaVx9n5r2A2YR5vsokCHAQTAQgABgUCWdjvlQAKCRBwjSLshNI3
certif:         AGoaEACkvIgtsA5CZG+CKAorgqcjXgd3J0JaOwoExbDjih9Tay+v1uCFB+AyRYPM
certif:         tOc+s+6gt1hLCUQgpurT/CwKK0gSdKkNAHHPmXa2s6HKreXwo5z6ROdWr456sFO8
certif:         N60QkF0q9G0InnGj+nykS+I3QmNy5W2k9wCyzr//J2FklS2oKMcrjiwWS2Z/+tC5
certif:         Llxmq2H/LDZEVi2PxU91JE8MYcCnLXO4ag2pP6FRyj5DJ8puT74fZ6Vs5mNIH1QB
certif:         /1eQY8XOgg3yyh5B+Tj5yEMJ3+ENxy/7zU2lgI7zGqhvCcqXcIGR/Rv5C14ErGBa
certif:         Ns/VEaQbPchq+4690AAyn+DlhPNBl4Za4SVtNc0a4UrR2x/p0H4uxN/KiLm/OdKu
certif:         61NU/rEsUudUf7Fz+3kMDrBl2dwIRUeNCqq0kr6gCfOxeb9+SIffOw0zJ8OQQrk3
certif:         sPji091smq4x8lOp9h47JSgyFwUN3PXYjrTL0I4KEdXFIViMcuEnLKfxmvXWaRnm
certif:         BndK8urxD+qQOYQOjpFCbuMYR7eBRJK2NSZtFaCIIwsJgfXC0QKwnEWO6DVe7LnK
certif:         20Us5hqA9XGAfoVpdezqmi+W5eesjr10KE0zHp5xMKr11AlEKChIGDWI8iKnEVfo
certif:         GV9Mb8S68wVBZDQA5nqE5zhTdw50N5ESlNGwg/Ln1Sfr/U6dLIkCHAQTAQgABgUC
certif:         WdjvoAAKCRCQW7mjgnYMYDo7EACBmTN1vUaTSWD7t5iyi0L6pu39MvhEv6U8jXxQ
certif:         yO7C2V9GXi4EJhRjmbZAjXOZKrYZ7vKU+ZkjxmAQBk7EGcVJOWl68CT8TNu56HgB
certif:         16idVq3JOQhhckhTFNrFoXE9KSf8nAW6IeTKbt35UjCQ5Dy0Y0q2CW57M5PxGsTW
certif:         3tbpScY6gOjpjcEu70Z0exn6W3GPQEYX1bXyIdnukQQLdPUKijCDBWih9f9X1ZoB
certif:         +L0rloLI3eQmIvojkPe2wVuQ+MdC2Zqdw+umgTSWYeRHawecuVxMKiMUHYlysp0T
certif:         w2Y/6d5nqhEmfZaS5U7C0S7ubGvGQMAA6UuYYYwNC2T0n5Gxvv0K/OwSU1uFlgAn
certif:         zTR9MUFx6qlFLfOvXaHQSd5bOWnGTk64UWvrsPxfrTQhogFtljHz4/Oag6Q7RC0W
certif:         YpgHeBdBEIjckmn7Jw9hYI0P09y/kLS6ecNV9TOL667Vd3bjJ8haSeyWSUfXil+j
certif:         Wt9uXVdojvzl3gXAeYRrJDI89V9owlOXw0bQ+Jod6EqCainY3WPN1AimIBsIomw/
certif:         Ol++RCa1+Wk6h1kRBWIqrIlpQyDLwJWBVed3EhZdO/laVV86jFphOzrkXSXZ2QUH
certif:         xiDju4grylqF3NgWwEvQ3mKxrqVzhlLbZbdP2S1nIGKs0Bw1SMhAj7khRzNAGkpJ
certif:         nd1BY4kCQgQTAQgALAIbAwUJB4YfgAcLCQgHAwIBBhUIAgkKCwQWAgMBAh4BAheA
certif:         BQJZ2O+BAhkBAAoJEKg4O6eA8jjGpyYQAJY2XbzrUJQRw6eQDMu/T2c45bnj4+Ld
certif:         yxowPsbwU7/YwH0871r6xWZBsQ7uQ1MjC1qt2vIutayqywb+Vszg5DtA3xyp97GS
certif:         cjILTd/iURhBYaqNPSUxFMXRl+J4zGwLlglFbdgextGBpx7z9GyfjrKxCflezpOO
certif:         dVc8AR2DS9+3rv/yFs/NNsZXsmhQ3EpwyehpQqH9ksYDwBmuf02KuaZPv1ONCbwF
certif:         t1KHB/JjQrRRJ85jC4uVkAhKY7isGdlh33X7tDi5xGTW2zMf0YCDmqlRmUBbUO8+
certif:         pmkYVWxBIHgF+7HOjwri9AIHWvW0oxSrh01PmiWLG0HgmoJgoumqtG4uJGYUTKAA
certif:         4DDJltd0xBxk8Mu2JQgQ1ZQLKTtxXYYJ5zlU4cC7LeuCFU6ZBV27G8y6yZ5H4HA4
certif:         hPdoxPH4xaPbsp+LXDWl3Ce46x41+IV5qdbTcJabUAynpDPYSKCd6bCeABReAaSU
certif:         Sf0JP3ZEESZGRHODbjiiiZBI6ImGTV8sv/VByJUT49m5hBmVO8e3cxhEoI01voOz
certif:         u1LGPokZ3ansF33vwaO1uEeLViHILFvfAiJ1/7dl5VJzYFe8rLIEHF688igv41eB
certif:         y8CFRjimQj0+tP43rzSxkUuv1aWMtmUkKMupE6349goBV/+XEJuEXHE7UqIiSJz5
certif:         5k+PTeTZhk6htCBTYXNoYSBSb21pam4gPHNhc2hhQGRhc2hjYXJlLm5sPokCUAQT
certif:         AQgAOgIbAwcLCQgHAwIBBhUIAgkKCwQWAgMBAh4BAheAFiEEhiYdjb69pPVGktZN
certif:         qDg7p4DyOMYFAlpod9UACgkQqDg7p4DyOMb9bg/+ORXZnO906haH0SsHxT/wPeba
certif:         zAFDgj27F8fKzoeM8JkqLtXpn+1U4oQIZL6/s61tvpjjdj30BKlqukCltF5R5Zn/
certif:         ItqYaOXteDA9sWIEluQWYZarkZoP9E/3D5OhTEQHhL2WHuSqu+ICUuJiMAFCzcBS
certif:         nEqlfFR5+aOuHBB4TwXjWZPWfWMSC2pSdcND0A8Dsb437dIBcoodLJuRZiKf9muP
certif:         egBDywvhdp9NfiIGpL39jDOeWtOlT5DLmenvmA/CBGQ6Jndz5aKX3njCAeF7YXM9
certif:         fLBpW4en+ZL+kogzulX6csILClLlo6I04FVm8DjogBDRg6cLT/0QcOf/SErDTBfq
certif:         HCy7+5Fh6I4B/YxJ7PltJhrTgR7+m9OjY0VzTJP5faCHu76tOIp4BSRyKIUgVSjU
certif:         TVurGHZUiZL+bKmIAkHIsLFSE+tFTpDxi+tir/o5eskO+gk+HGDnBSjhyqwGM/xC
certif:         T9tlGWDutwnB9kXIDNAp+Cw9l9Tu4T0tq17zNxcFOXsXl+6AhaWbxNtT+P2I5Du/
certif:         XH2p732EJGAGBxA1SZV1FW9swt3bX57mGLlavuP/urgE7phdcv15S1HjYxj/HvJ4
certif:         era0UVn67WMlE61SSIG0f2BS1FXygRCEPhFZmhAdOguIjMLqp5UpsJZvwfPX4I7U
certif:         wSFHhaNtMt+O9MnzL+aJAhwEEwEIAAYFAlnY7kMACgkQiW7P/4PYsbSK0g/+Py5t
certif:         AQwfykWs5LPb6cabXGHALWhhaHFQqf0eeLROsiByrzxY9ZO7n8CCd82JPPFGqpJ5
certif:         +s8auxQbh050Js3w675Mf+5Lnpx9iaa/OF9ku8lT+ktdSpin05Sr0oYsdvERsiP4
certif:         CXRxT4dQ/mUH2lbjGh3xa2FY8DDGMIoygp+Upw3B/fsAODv0g0oK0oKXRu7m3y27
certif:         HXCclR/EoHUqNgGbAChGz8c43z35/eIzh+IQFsdNkLJUHIclDNkZJMg1oMEzdZHM
certif:         J46Wcvs9Schh4uhDSHzlZPVR/8J0eLKvHlAhDqIkc66WjXA8CvFsfphqmU0cjNEE
certif:         ifTljwcYiVbHnlLqAEqwObWElXO8JAFQ37c9IMIjXGTstNGg4xuX6QahJn4JMwnf
certif:         5Xr62A0imPI3uo2r2b4q2Z2sdbMsQucsTdw1939ugAuOYFWYZR5cHrhvOLMxUD3D
certif:         otzjVzsyBoaV2/mdgOLXLyE8ip72XrmEzfSOYV/5BF/+PkPKUoJFiKawSSMKIUQ1
certif:         X8sx02tGHsPGqu3aASaJ7y+n+8aoT7f+oVJuR2SubstOqbi8ZIYrIqtsWmw4Otkw
certif:         hMsRMbNiYGL+ZWHD74++AszC+NVDPf3uO0qfF9uSFO9H5cBSdKG+jm3fJc5tRYnq
certif:         L+qoKUm69Sb9gI7Imhp38mSyIQs0w+JSZwH9OpiJAhwEEwEIAAYFAlnY7lMACgkQ
certif:         kFu5o4J2DGB3MhAAuo2ZjXQQVtgQyJ3rwORwfb8RmIECPHIv1hetgfLYRkJCP4Hz
certif:         WWsyPflKMvJuxbyc5aaDYbWWukqsTZBr+dARYfWmsP7tTNC1QblL5WsWNLwZHF2u
certif:         qWAi5X2kPgbSGb+zVC0KNEfB1yNfw41Fq7XGCK3K9zw/JZxGi8aYAczP7XbkYyGV
certif:         zikQZJTET1mlofzOnqgYoCh7C6/SmJvyY9o726R8Xp8dy7u8CcHkWYLKdoG6aze2
certif:         vi/4U2G25wiJBh2mNToTDaSMEF/8WCyGlxt4SemH1r0rxtpe/fAy/76pXalBSZZC
certif:         mWKxHoQHIvhJWhGqbjiXB9rPvc8d5rLXYzZSYLTq2nAhftygqWyIoS6U1TAs56wL
certif:         yYN0bkV+5yzHVKZ1CVu7LHrs0RKTfXY9JKHF0g+y9wCLLHEM68Rd9BhbIkcdudbN
certif:         T4FjTuKJ16dALHr/c5rLfqeS0dSN7iL/oWulLfs2K44CaGqEFlJmxbRTl/JnHMvq
certif:         igtxKtCzrRZZnHNwfQY6FTA+gn37UeCoNFbGQgIsyPomSOjJwzZRadEWjWg8fC+u
certif:         KOhYEIn3dCd9qXh/YPp7vyCY39IkYPPNbGtb0t6Ycwyuo/chijmcWGlAVXJQgpfk
certif:         sceKR7hKw3KsF2vR9wyjGmwcAwl9eRsKFGotEUG6CAkWPb9ewI94IeiGNSyJAhwE
certif:         EwEIAAYFAlnY7mcACgkQcI0i7ITSNwCBjg//YxHMIO0m1WbSToKwlzryxBWcFf46
certif:         Yq7C+jdeI+mIR3a6P+RJWUMIKIWqcdg/8EgS/lOYp/rsd4Lu5/07N8n2ppJ0BrqN
certif:         VcG0+Wld3f9ALXf4GWQ2JzHfBzGFcQ14gwLQSqTAWDAQw+iPuiqZD98q80NgmbE2
certif:         mgJhrwUiv5mMhARLlvFxZDGyzL2oob6DuNNYyucQLEgcpUbFWeLpgS6xegHXsIat
certif:         2YRkUXazJmeqmANipA4iUSqycYRGVWfQpcNWg0EehFMnLZNu1D3ZUe6/8E83PvqM
certif:         fKPIaIh+fwuEgLVC44tS+OOgstBAzJJ00tV4ESCZf9WjoBTrD6k66i6xONhzV/nv
certif:         YCOK5Z41zZN7l1X5oiq0J8OCDjXEaVi8SCmWOiJHULjMcIRo22BcFyl5W+1lH8zr
certif:         cLRWa43FFt/Ayu7s43KwOs+ILWAc/NxCH/Ri8CcxywMBSRLoWsMFByGNDv7rbpEM
certif:         yAGRQL3M/SDpBeQ2jaOvDpYjJ8vBhrhL8MCPTjXJEHxkY15uAhsW1FR1VYPRI6Yw
certif:         w99XH0ZkYg9GIxt/+hyI+TX/loyGmih/b3OAjEov/Cv34kzjMxewaoRHT3sow6gM
certif:         aJxVGNE1oN+XAYm+9Grsobb0IggV8f4LessNBgTerJn6P/XFfhQR33nbJE3AEn/w
certif:         dR084ZI9I9MlPiiJAj8EEwEIACkFAlnY7d0CGwMFCQeGH4AHCwkIBwMCAQYVCAIJ
certif:         CgsEFgIDAQIeAQIXgAAKCRCoODungPI4xujQD/9ycM82UCOv2kPa5GcHwhVYnK/V
certif:         l0reNViVwjamZ17V4q+H1UU2bXST3RlamLBH7XBwxso2HI3mGSPXs1OkczV1Xq1o
certif:         AH72f1/7lRCtm8VE6ef7ZaGh9yDJnCSG7l8beLoFm1qnSCeaxu28GQY6DP3c1OGZ
certif:         cimQ2v8Qoxx/sY44v8lSqOEbhdTbt2LuhMStWkI1/DiO+CN0FMMULWtXAqlhVvH2
certif:         rItVm/jImqV+TebdbFsq6JTEM8rrrfxBiQ3aV30uj4yKCBXDStiLcfyESGpy+BWh
certif:         nwRal/qI5b4ghAzpBwRED4KSJMW/8IrjMGif01B/iBiGOuEzIewsIJ6RfDuN2BXc
certif:         ovIucU4B7ZAIz4EWYZRNk4TnQBPD6z0bEOwuHmndOrLe1V1x441Kqmb2BvYWENOO
certif:         2euk2sEPo/ZXpNhLcMqijV7d7rJlx7P8NA1eJNz1+0hQBVcpUhGESvUvoVLZS0g+
certif:         KJly5bWJrQ/nEqhfzN1vweWm+houCjpI7cu4xL7uhk6kzaMm4mjXqIcKmOp/wj4v
certif:         sNUWlQinsf+I605FeAnwAZlViucDg8IlXBDq0nETlyyoKytkrnbX5aQtdpZNBglv
certif:         +Yr9tSKmnPV6WZKHDXWcLPPQBaL0dLgCrGlI5ClJPoTNwZSZ3+ibxQLYaMowt1Z/
certif:         sZ1EQUeCFSyHOgef9LQna2V5YmFzZS5pby9teHNhc2hhIDxteHNhc2hhQGtleWJh
certif:         c2UuaW8+iQJQBBMBCAA6AhsDBwsJCAcDAgEGFQgCCQoLBBYCAwECHgECF4AWIQSG
certif:         Jh2Nvr2k9UaS1k2oODungPI4xgUCWmh31QAKCRCoODungPI4xurLD/4tNzm6Y9WX
certif:         APUwsLv8wLokvZlENSvWr2gk157yEeBC7L7GAyq4BsZbCoiMggJMQLcdSaAEwEuS
certif:         hut+sdP8H+pZNXCTgyJ5TGgiUMkxgup+Tw/NlFu5Oe6wxd/XNt2W9NAvRsvYKN5g
certif:         NWsCbT6H9aWXdCXzzujtcczDzANLPHzSZtWoH1oRGoe4014Zl3qGeilAL52BVqaJ
certif:         rMDdw5WOCF7EFQxEWu0yKdBQPajX8Rr5Akq914fXKOBmVGeDhv2EQRUQbeo2gs52
certif:         n/Bwnl6g7YCXhljpejyvK9Pa8uvd6p3yh+WIdz29U7dI5a5MjrttuyFlqknn+ejK
certif:         Bc5AJYB+sWiPPSTwCGXo3gr1VZmlL78d0zmDaPIU5pFDfwNhxjPYKY6MTrqf5mlq
certif:         oHk8Uev1Qwe2Hsdov2JdLmv0Hda7bDsVSQQRp2tDwB23mfxm+jApchdOg7mVbmga
certif:         /V6yCu7/ZFYLYCzJoBToDna3IBElwPMGcNLjASRns6D0UjmJbWMVr+houmrUE/bx
certif:         QTQyAm77+bYJlyESciq8ER8J3uAdCL8+wQC35lzKOwZhF05/xY8qeYGEZfsFOpaZ
certif:         FcBIj4RWJcrX6a99TQkerwjVcRz/qD+wdfnd3aBAeHHUUnGhykWHt1d172Z4X7EW
certif:         VAjOmv1Gby4Kh4xJ8CRcoc6+Cb8lPWNSQIkCHAQTAQgABgUCWdjuQwAKCRCJbs//
certif:         g9ixtPi4EACzdy9asmUCwCw+zRaly9iNRO0BMX32P4za8oo4zEuZzKcnUgV9vGde
certif:         CR3CSfOXrKrITShHC+yOCQ6RAs6uZDZg3IdbiMxCAU/B7hJptOT3ZqrWQK/E6yKT
certif:         bFaFZXArKCBW8eNROLAYodaz4+RcR8ICUB5zfxpTiLVgIKf/uscN8WrxMsdfsNYL
certif:         Qqrd3ubxy9RID41WzaK6ZVgFUVmwP9FJYiDvDU3QRYESe8BcKeYFRAwe59tO+irL
certif:         rld81cnb3/xlifsmnZnuHXDszw0MDzK5/sM6iGktCMgRm4aKgGjLXghoEk3dPFbH
certif:         8NfS/5YQG/pLcsdCwG9GtWEsSUKdYVGvkeTeHHqDSR94ONLe3Yx2GBVplKuuP85I
certif:         DWyIyYrDsKNniSysTPX7sNllCJuS4fIGFuut/nWhi+ampHJ5Oulu6haUdSovMgcq
certif:         dX9uxB92CyyS2VDTo1TRTl4IoJSw2woDX6BRanSMqsqDQE2awHZNjeHqi5IUb0UI
certif:         pHTlAGNS7T4swKWo5P+yQDHcnBvlIsg+6xp4NxWw5QX+WNggzEOLRhsYDKWZ3ckC
certif:         RLGpH5007YGEWTnLCQU/pVn20aFXdvaxi1ZPt0UBPres3y25ObTUn2SfLVqqeCWi
certif:         JtV2MGNT9cbVF31GRVbLBfR+63eUEgwEvpAZ1LO4x5f6tdHwoiNxNYkCHAQTAQgA
certif:         BgUCWdjuUwAKCRCQW7mjgnYMYG2MEADQohyXXnNdZdUVmFt5yCG+hLsxebTWtl0G
certif:         hbPRRl8xO6e+nFRK199Jm1YgNovlWTMp3cLV/LCe5248wg9JjhMTNHtlHCq+l4Ih
certif:         Sm/rEKBY59HZYSVqS5t2ea6vHf0/WpLu0QLDFjGJaIKFBlHRGtwQuzERn1JxU+P6
certif:         j8804V3nPgaG+J0+RZS8YhYRCLz6g2O+1SpXrpMfaVRj1Xnb1Byv6YkWqb1lUdwT
certif:         wmoQKIM8dsykLJHTKv0+UO3bqudZewmY8enfPSzXfZq3YLWp625kRe0g4dzZczHm
certif:         HCoqMqReYmiHBGor8njcT/odmj4lMcr+1tKoybs2JAsz3nfGlsR2hpVdy7t8Vmgp
certif:         GTdsWMorTODV1V3MKGFQS+bky8KJm7mvcba+x+sa8ujIFp5QtP/KixAdCxjeIQDE
certif:         wmWENiZqkXljdxF176ode36HFo8+uZ47Q8TZ29NN2hDYmQe7wfohHV8/5rx6UKPB
certif:         m2JkpRaAZ152yfnK4+pE15xCfoK4831eGK4/ThpR6ZFfp7+V7YUGcg3I8uHV/fDK
certif:         lv+aePJdusWfi2O6NH79YILl3MczuIkgEXYWIUf+rKn3IuV0iQTfZV2bOh3q7LDR
certif:         lQ5w+3joerbZIYSI8JXm1FSdd3zQQma1isGq4Pom/9A5E9z7dRzq0uOAwiH20tOf
certif:         uWLBeQlIDokCHAQTAQgABgUCWdjuZwAKCRBwjSLshNI3AND2EAC7S0zQV/K7Y3oZ
certif:         DjQqUHhSe4kQnoPLHo+JBoX33nmkV7FIJ6rBaxLB4AZvzz3PiwbUc2o7q7g+n0nI
certif:         ejWpALiDhB59oa4ugoiPKcfl1hI1kY+LpbBI8wBrni0GjnlJZQW+7EPY11jyR0MM
certif:         3C8YrQ10EgMLdTuUoLNODmLbnS4U3hatuhkFSwTF1qciBH+DJXM585Ihr3uWkw/L
certif:         BiZz+0DBWfx+uvSOUVKV/tWgNIZkDS84aedVV3ySrmN/0FU66UqfDB7GJjfGoY5V
certif:         fHIzVif2LsypgGvUh3PcQ8gWwjLY6D36yH6oJaIOI1JpkmZgKChFJDfGBjStGg0Y
certif:         rEFira/c4oBUrebKFfipsQVorOVUK2WPP7u7QBB/OadPk1oH3OYWkEKV5wiqNr2A
certif:         bN5f1S94arfn9h+cylSPxDLhfcfAf0JbsH6kYd93q2M8hxhufi77LofgSeqlpKVg
certif:         T0iAuLZa1xfp65MjBhPePXhu4sLZxhBBSWJ1YihiU4g9jkEamGD/jjcI1AGAPiMB
certif:         capmfITMJj+OyPbT7x9XeeiWexKL1+Zo0VTvZ0rIE0OovZLloc9ercErq3e1DKdM
certif:         pOpyvFcps8KnlbvVhSNRYLQgtiI7aOp/yY7WqjwJaTlg3TTQAwfi2V0RGlgKWqSA
certif:         z21EQdrI2JtrKSxsCQLfJn8Gz3odZIkCPwQTAQgAKQUCWdjuNQIbAwUJB4YfgAcL
certif:         CQgHAwIBBhUIAgkKCwQWAgMBAh4BAheAAAoJEKg4O6eA8jjGA5EQALHaW/SJOQde
certif:         vKEzJ3UMTknd5p4uvyi6gEvy6bH9m/3+5CKHz1j1S8gJR/qacOefe+EYo7EElUSC
certif:         vK0Ooi5vJXKd89+SXpcss0g9j5vV+ooEYutDqBGAHI2zdb2cAlLP2aZ2uX/jh2/y
certif:         +bRZinIEDDX87UBwQrWCX0Sn0KWz8erdxkTnZreWRQJOjrG36JuYFTkN4eECvtR2
certif:         Lkfmu2d8tR6qav+psN2/YtQOEJ/pLUSNa3eaTbuaAYtnaTloXuXcWGgQ/hkFQ+R+
certif:         igky12dqSOXMBtQkAOUQrrcW4JlZR2GllI3fAJMAviacRXd32DlGOvtuShsY9Wxl
certif:         XSludWu7nhIhzM9i7ZAN48n1oSIDxkKHYvEaWsFQo2HxN3n1UR56cQk6JIurI5PF
certif:         SOKgv5LWxQZoJBMTAenpEcgFSPbPKw6tQrzmB90XT2rL2LoSMSI6xFEnmeIORtvi
certif:         h42feMahy0fJxW/lKz6EuNlTrtgZnl8wxva4latspM/aWP+cNaZBAh+aaF6kcfHh
certif:         gv2xff0jAC47sgN9k/MaOD5HV+TkJPj9mElzHzFjBGc5hK0I4nT5Ogyx0YhTw7C6
certif:         MpPu5Ia5p675lVQ32JBReAVX+XCp6dC5PVSIDUiHDSuSZQSU7LW5wbc9nPRqrWXU
certif:         f1+YEzT1LM1U3MJJP7K2pJ/g8vopxVc5tB1TYXNoYSBSb21pam4gPGdwZ0BteHNh
certif:         c2hhLmV1PokCUwQTAQgAPQIbAwcLCQgHAwIBBhUIAgkKCwQWAgMBAh4BAheAAhkB
certif:         FiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlpod9UACgkQqDg7p4DyOMat3RAAgtqq
certif:         kiPg1J5shmWkD9Hc+Xnq6bFoPneDI0WYbJZueodBHU4ww64+KPINuJkJWPZku5hg
certif:         3S7Mns1szWd3KEtSrU+DHPyXsBKQ77Lh8KYaygW8QN3qyfaPk5461vXshYPC4K4G
certif:         uzTTMt3bKg5sfC/Sdkn8W16D2EFU/m2iDuYFhlcVHu6NxViMe7w2CF8uBln65299
certif:         D5INCUSHazht7dpkvViiSXx1cpemaOrOwciHnODgatqM9+X7wa/5st5Vzm+nByxH
certif:         fYttl6dJy2rPhLtd5mDE7/jQm8y590km3F2B0ExMjt2qYhnUEWtbzAm1MyWQy90W
certif:         ni9w/795HBofYHE96+Mr7mnBDJCRpwdxzGqkpX2jiXjpTJEybqFS4jcdP6X2oXFJ
certif:         9aTUO1mugpQ3WCIe4BvOCaof5ueSISkccUGotH6MWGzetkVbLpFQKEJzQFwsSYyE
certif:         2Bck5H3CZEqWeUC5cGHD4K5KeRVe3okMwrsWKEgxKxWuN8Mn7eULsxv0NVRkecRL
certif:         Yds21McnVNKRAs+a42VkG6DR3vXeFE1lgc604wU0RyB2mp1W0w/0/k3Eybgtm42j
certif:         zIEdzhPlylkaaLau8Gbdp1diYMwdqiEP6bMAXUEBVuH3eTp1ihvyWXAd/UiWmuVR
certif:         htK8c83KFzw10k8ljpTiKfLpSu9DphbAWzozJxSJAhwEEwEIAAYFAlnY7aYACgkQ
certif:         iW7P/4PYsbT3Lw//UzAPBV5m3DwtPg6argz03KWq6DFt8jIba4RWJnbJ7K6mNslY
certif:         CcaO4aZiMVmhd9KaeSW67m3XzyvLisLaOF2xSwxdAFkhOZqlnPf/p+EhflN7OVL4
certif:         vdGCULefmTL1j1nGlUbbZz13aevI5t4DXbLY3J5uTBcQBn5N8J1JKlzLNMJ+iAua
certif:         sGjGbs0Qb2R7dIYGB2d+qoX5VlwQIY5IlglPf9RJCzMaOcpBxjRmiUstblrDNUMH
certif:         SdI//143w+b4D5dIJ/ykskmadjaQy7k+B9jiSA62zSN6LVIeb2wOJBxigQ9/D05Q
certif:         cmCbbbaDAw0RMzYU9MMrkJHRO3ppEUDPQWaJ1nogR7JXZOuBuDCKiZfNcpbQXo8j
certif:         ZuBrXol/nCUBMzEJVEuKSzjiu28vZ8jyPL7ZgKc+mm1ZkRj7FyoIx4ZCWvvF30RB
certif:         QkSB9LQ1jLC2V9g2NgnveYPgxpx2J9slb0KeVimw3wj0jOnJHsPhMBJd8JPHNXA8
certif:         RUrtjGYO8Epc7TWBrOcsjmIOZ2PBQ8irwQpK5tDA3ml/AAJ+D6r3Z4/MdMWtzFTV
certif:         7a2u0wm838cABz566YQ3jkkve2lLfcaYpImz4ooiZYl1xvjLMrTu0jzYpChpTBCk
certif:         V6o2wCpjXD38VVHdgGe4XBXLJL/gB/ZZjs1z+uRjucP/tqobyUCvmHwAoN6JAhwE
certif:         EwEIAAYFAlnY7k0ACgkQkFu5o4J2DGDogQ//a+s89OuUUA/ro3qMbP52Igxc+A0f
certif:         a8kPIUE6sCtiS1RQkVbEMcdYG4O+PDakEymiWLgt1xy+/Nx+t8AmfyQ5a5ai9OmH
certif:         9Iwe0CkbqjEX0yUfV8QwlHuPHAaaAqHbqIay6X0zyB0aDWSsKDu1zsV2KTh5kuy5
certif:         IsGbbCQk4EBRqhGA27fQIm0bcjW0MB86BpxCwpDhnNE/2bA1/UY9NXemaeZc1XE1
certif:         QD3q74NANEPjYNbdQxDsXGxD1ctpWvcZW8Vkx5JyKD4bZ7FyoJnw90nv8EJZcdxi
certif:         J2VZDwKvyRP1CiqRI0+XsPcf0iiEWMMGSMDWOIpc8CYvcvUlJK/emPwtMTxJ6yU9
certif:         FKs2P/Oi3WcTnS6xeEDkTucoVyopcT5/bM6eBREdG08RVYpxqNIa1rrwxnWoaun5
certif:         5gqM3ifMibTg12KQ4RIKGKD6ezzwGLhaBHhwOXbJ2ahLDUfCP/we66sZJxRxi6Ef
certif:         Xtwt3fISUDBcbAYpj6vexd+Jqle8YTXe0/h0488kw9s8oBdddH1vsGxFpBJfHmOj
certif:         Sz2pJPaPjZMHMfSBB9COL/fCSiolhbQ8KNatKjv/682SqrZ1ufGDqFb2JQR6/pb9
certif:         78BsVRo3G45KVKZG1Ac526CR3BVRUyJKctCwOO9sW5IUGbpsvlWTA5WmdGBTPiGn
certif:         n5Xby1PIudk5ttKJAhwEEwEIAAYFAlnY7mEACgkQcI0i7ITSNwDNYg//aVAF1gW9
certif:         ZhXyKHvc9kKa4VCthOH+avg+j+YXrzDRP/KIVIokYlNVlg0MutSUbFT37ceUwYTJ
certif:         LuVPxQIe5VYl5kDrl4Ft2nnpoYmumicdbhhstR6PTBjxwQzWcapzc8R/Mvn4xII1
certif:         Rwb0rUDl08/Ezb9H5HWCV1/iusVQRHOsp/klL5QRB9OPAYRL4ZhqSaLiPz9YFVHt
certif:         i2zQl1yjW5iaayfajEIvEWKoZJE9eQ0HX/Uk9mtiTrUO/VZ1IGr8II2Kpb2/vxaL
certif:         0iZQIop7KxPM6rmXzxVymFo3DYQc1LzNs47RcmOMP+Ivsqu2W3QmIrOaSXtBbcLj
certif:         B9SRQGKgelU3qfU5cbQVwiB/R68kU/Xi5V/g3BlH49mshIcUDzU7b0dtxQx7Om2Q
certif:         6+BJCWKo4Q6kzf/ePQr2Heq0GZHpJw5Dv+3yAzAuqQadFFEklq+m3hGWAtZXaSXa
certif:         /c5+IS3+HHfz9o2bc7t/qW7+I6JZC0E6gw/tW8yQZN55J8hVsbHwHBCphxN2IMRC
certif:         u9c4G+14zPrpqB2jAbHrI7iAMhSJa/9OkdA5wuaR1+Hv1Xsx/AVu9h+BWtWrZgjs
certif:         S2p5kwz1MfMZtDhfXjF8y3YPPmQeZl7twxrvYqvFjTq22k5epwYuGPl2JMuV6bwO
certif:         Q2UjMec0MrNbNlq4T3YkGKcTy+4sFIq+rMG5Ag0EWdjtigEQANA0pA0XaEugl04H
certif:         m00lQO0qbSVS6uZXRXsguPiP6LbBLWE/VBg2Dm0rhs5/Ev9wRhOwE1IEKJkn+OqJ
certif:         yJiMebp6rPY+tMplVIKINlaWIMFN9UoMKm72IzY4o/b+YUuWwPMMCgK4Bqd3jzop
certif:         sMVOKn9GX8Pz/hDX+iDQG10IZSzi9fpQZzBk+UmzZqwP+/i4tXxEjfCqnrlwmh0B
certif:         pS1vecaqgRkrTvD3AcTVJVbSekQa4jR292ebRWBIWZm4nATbOf4kVF/DHKuXZIPX
                fXe0acKuNUTfFEDCAM65X7AmVqVx7fcAA9zfei2bWxzDq0wkDE1eEmmfUCvrjdyH
certif:         ensRKKLs8dJWtrB/FB90rsn8FbZUnyXJ9C4BHR4F9zubqj0+B1DQrOl7Hf7hgd6x
certif:         QZpPZ0IxIdECESPRr7yNH9IvMf44N8Zp/zjvD6zwdoIpPiD5ld89a5+xXyYgd7Zr
certif:         MpB5GcRA6cfLETQLXqIoyQWtvtijAbf2oV1xkMxj25LcFRvPBRnF7Qt49U7dsWDt
certif:         AmgXjQnuDvvA0Y4F5NlTiU5kFSOV34I+8l2tHl7Ff0OMcNtdknEX+XPmgTR1x2CE
certif:         4BhFwcBrfFAJghaJ0nCQhPlGTDLraoaBW+9krjeC/YGacUZX28YP044txSlRUzmW
certif:         8+cSao/2yBVljyRq5c85YMk/lK3TABEBAAGJAjYEGAEIACACGwwWIQSGJh2Nvr2k
certif:         9UaS1k2oODungPI4xgUCWpW3SQAKCRCoODungPI4xqLaEACbXTFJEEVnQBeTTTaw
certif:         UQNAyGP41NK/VsxrYbpCs7B6K3HDgTuyTtqsJ3DBR7xl88J3Rj1JYVLfOApalnF5
certif:         6XEwBNBdzQcn10RGo5gIbhvwVMF0RbnSDo9wvwB5Mbdu1F5Mr5mwj9pArGp7z8TY
+               JknUEE/E5krYCZ8HSSSJe5r83uklDR9397+nX/Op0bd/URFJ8ipOxYQPkYJnewxS
certif:         P2pquVrJDBtHPfzXyuVmK4vf2fDa1KX+XSy/JtaUjETebagxBrGQeWdErDHaQtUJ
certif:         U1DS2xGLF2WhirvmmEFDOWKwnmO1HdUSFMGJ1V2LzfkCC1s1OTc3mcYuzzGoM1F7
certif:         TDnLQ9PJqGNqUAHozFuhWfAkX4j5w6k8C3Jb7T7ZhuSswAzEmSfdkg3FHtwQrjXM
certif:         fhbS7tnkmDobMvm7Jo77Lr1CotFBUjUhsR691fA6HATE5svH+CUF0Uq9iPiNIhqK
certif:         4XA9deUxoYxK6InyZS+LI8cKTDjqSzQLBdA65IGmS1K11e5SiK7m7DPO/IH4w/Jd
certif:         M6Ou3r6guvVecNLh42XlKCN2EMew6kKD7GV5MUsvk8w6dlBZAQ12uQadx/BtqhzD
+               NYMaJx7AqP/3hfUjzP1sxnS/HlypR5ULU+H/C0uhTcWbClJ1B1J9MZXUHgjHf2l1
certif:         lxEK/ng5MnwCg1JvzWabWeMR2Q==
certif:         =rpYI
certif:         -----END PGP PUBLIC KEY BLOCK-----
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_MNTNER = """mntner:         TEST-MNT
admin-c:        PERSON-TEST
notify:         notify@example.net
upd-to:         upd-to@example.net
mnt-nfy:        mnt-nfy@example.net
mnt-nfy:        mnt-nfy2@example.net
auth:           PGPKey-80F238C6
auth:           CRYPT-Pw LEuuhsBJNFV0Q  # crypt-password
auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
mnt-by:         TEST-MNT
mnt-by:         OTHER1-MNT,OTHER2-MNT
changed:        changed@example.com 20190701 # comment
remarks:        unįcöde tæst 🌈🦄
source:         TEST
remarks:        remark
"""

SAMPLE_PEERING_SET = """peering-set:    prng-settest
descr:          test data for peering-set
peering:        AS65537 at 192.0.2.1
remarks:        MEDIAFAX
tech-c:         PERSON-TEST
tech-c:         DUMY2-TEST
admin-c:        PERSON-TEST
notify:         hostmaster@dnt.ro
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_PERSON = """person:         Test person
address:        DashCare BV
address:        Amsterdam
address:        The Netherlands
phone:          +31 20 000 0000
nic-hdl:        PERSON-TEST
mnt-by:         TEST-MNT
e-mail:         email@example.com
notify:         notify@example.com
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_ROLE = """role:           DashCare BV
address:        address
phone:          +31200000000
fax-no:         +31200000000
e-mail:         unread@example.com
admin-c:        PERSON-TEST
tech-c:         PERSON-TEST
nic-hdl:        ROLE-TEST
notify:         notify@example.com
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_ROUTE = """route:          192.0.02.0/24
descr:          example route
descr:          the route attribute should have the extra zero removed,
+               but this value should not: 192.0.02.0/24
origin:         AS65537
member-of:      RS-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
rpki-ov-state: valid  # should be discarded
"""

SAMPLE_ROUTE_SET = """route-set:      RS-TEST
descr:          TEST route set
mbrs-by-ref:    TEST-MNT
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
mnt-by:         TEST-MNT
members:        RS-OTHER-SET
mp-members:     2001:0dB8::/48
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_ROUTE6 = """route6:         2001:db8::/48
descr:          test route6
origin:         AS65537
mnt-by:         test-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_RTR_SET = """rtr-set:        rtrs-settest
descr:          rtr-set test
members:        rtr.example.com
members:        rtrs-settest
remarks:
tech-c:         PERSON-TEST
admin-c:        PERSON-TEST
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
remarks:        remark
"""

SAMPLE_UNKNOWN_CLASS = """foo-block:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_MALFORMED_EMPTY_LINE = """route:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT

changed:        changed@example.com 20190701 # comment
source:         TEST
"""

# https://github.com/irrdnet/irrd/issues/232
SAMPLE_LEGACY_IRRD_ARTIFACT = """*xxte:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_MALFORMED_ATTRIBUTE_NAME = """route:          192.0.2.0/24
origin:         AS65537
$$$-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_MISSING_MANDATORY_ATTRIBUTE = """route:          192.0.2.0/24
origin:         AS65537
source:         TEST
"""

SAMPLE_UNKNOWN_ATTRIBUTE = """route:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
foo: bar
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_INVALID_MULTIPLE_ATTRIBUTE = """route:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
source:         NOT-TEST
"""

SAMPLE_MALFORMED_PK = """route:          not-a-prefix
origin:         AS65537
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

SAMPLE_MALFORMED_SOURCE = """route:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
source:         +TEST$$$
"""

SAMPLE_MISSING_SOURCE = """route:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
changed:        changed@example.com 20190701 # comment
"""

SAMPLE_LINE_NEITHER_CONTINUATION_NOR_ATTR = """route:          192.0.2.0/24
origin:         AS65537
mnt-by:         TEST-MNT
or
changed:        changed@example.com 20190701 # comment
source:         TEST
"""

KEY_CERT_SIGNED_MESSAGE_VALID = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

This example was signed with 8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6.
-----BEGIN PGP SIGNATURE-----

iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlrMv68ACgkQqDg7p4Dy
OMbnqhAAnT1H22a+CvSWCjG9Hn7Of+bfr5gpbPNTMlACq4T21rriRWw2EBvERWuH
0FZ02Jwn6tvrw1iXdGuB+BifB7RnB6+B3dfeuKAX0R7D6BdOsJiofv/IopIKAVAC
k7y2t2nRhIG+Q4Fk8/58yVh1Y/axkZZQMhpzUgXhN6eyH+yH1IFkrIc6PUJqfn98
gLkTxhF6Vpy7BhfaHakC4dLVVpE/AfRgf4V2Q6vW5cL4DaRg1uFb29A1Nb9R48kn
X6y8wPcP0rgW73OsEly3buNiogxfPWW+ur0P08do442U1SrnOy/0Vb+cWsvun1R0
AugSbIqneJfkDfrT+hgEGadEsmDbgTTTIGM5EawSCsvG0p0Uzs4gzlPwqebeq/T1
k+9Q4hifIvYFVtZrsjJwuGcs09ps5KYvf6Ps78gT8MssKi7oXS/QRdJUuNFBWWa/
j6nTtsYVerOWL1v1flWkSHrvWQklBOwqqvLHhdG0MFEOx33JTk9kKK+ynysZjMiV
HRJVYrPoCztKU8BA3eAeU1XICWfNPuGXh5LOndgKTzv0urcZkdP84cQmlAe89whD
8bVm0pUkwi2jbzjrXAv6gn+3ecP4ls7pAPJNFPWhuIPuMTmnC3w5AsGGGEzu7EWp
WJUlY+ptExGqyZNT9CJVzVMaZcJEanSnhOsF3G23ObB0Hkz3gLg=
=iSrO
-----END PGP SIGNATURE-----"""

KEY_CERT_SIGNED_MESSAGE_INVALID = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

This example was signed with 8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6.
This line was added to invalidate the signature.
-----BEGIN PGP SIGNATURE-----

iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlrMv68ACgkQqDg7p4Dy
OMbnqhAAnT1H22a+CvSWCjG9Hn7Of+bfr5gpbPNTMlACq4T21rriRWw2EBvERWuH
0FZ02Jwn6tvrw1iXdGuB+BifB7RnB6+B3dfeuKAX0R7D6BdOsJiofv/IopIKAVAC
k7y2t2nRhIG+Q4Fk8/58yVh1Y/axkZZQMhpzUgXhN6eyH+yH1IFkrIc6PUJqfn98
gLkTxhF6Vpy7BhfaHakC4dLVVpE/AfRgf4V2Q6vW5cL4DaRg1uFb29A1Nb9R48kn
X6y8wPcP0rgW73OsEly3buNiogxfPWW+ur0P08do442U1SrnOy/0Vb+cWsvun1R0
AugSbIqneJfkDfrT+hgEGadEsmDbgTTTIGM5EawSCsvG0p0Uzs4gzlPwqebeq/T1
k+9Q4hifIvYFVtZrsjJwuGcs09ps5KYvf6Ps78gT8MssKi7oXS/QRdJUuNFBWWa/
j6nTtsYVerOWL1v1flWkSHrvWQklBOwqqvLHhdG0MFEOx33JTk9kKK+ynysZjMiV
HRJVYrPoCztKU8BA3eAeU1XICWfNPuGXh5LOndgKTzv0urcZkdP84cQmlAe89whD
8bVm0pUkwi2jbzjrXAv6gn+3ecP4ls7pAPJNFPWhuIPuMTmnC3w5AsGGGEzu7EWp
WJUlY+ptExGqyZNT9CJVzVMaZcJEanSnhOsF3G23ObB0Hkz3gLg=
=iSrO
-----END PGP SIGNATURE-----"""

KEY_CERT_SIGNED_MESSAGE_CORRUPT = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

This example was signed with 8626 1D8D BEBD A4F5 4692  D64D A838 3BA7 80F2 38C6.
-----BEGIN PGP SIGNATURE-----

iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlrMv68ACgkQqDg7p4Dy
0FZ02Jwn6tvrw1iXdGuB+BifB7RnB6+B3dfeuKAX0R7D6BdOsJiofv/IopIKAVAC
8bVm0pUkwi2jbzjrXAv6gn+3ecP4ls7pAPJNFPWhuIPuMTmnC3w5AsGGGEzu7EWp
WJUlY+ptExGqyZNT9CJVzVMaZcJEanSnhOsF3G23ObB0Hkz3gLg
=iSrO
-----END PGP SIGNATURE-----"""

KEY_CERT_SIGNED_MESSAGE_WRONG_KEY = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

This example was signed with F18F59F232CE9A840D20597B708D22EC84D23700.
-----BEGIN PGP SIGNATURE-----

iQIzBAEBCAAdFiEE8Y9Z8jLOmoQNIFl7cI0i7ITSNwAFAlrN7tkACgkQcI0i7ITS
NwDUWxAAof/us3p+XubKAENmslLPBVqbNjp1uROI3ikWKj469cqNIAjg+HXTnRQe
43KK2VjSxMbgaku531D9iEAilK0tQbOAXmV5FsWFKFZtWh0rxhv9Gu9+jKEkYj8P
YZo8tt3PMKLIejhw26DpTj6Fpq3rUKqsVB+cG/1/P/8zdLEoIUwers9FyAS257Qn
46LCXIwindYv4bkYqqFLMZ1uPVwcfOCuDJ6HE8E3uOytjgi9yKWY1nmjvTA9CwEF
zjeXM6lI4sgctyxmdJyMlh0C5hL0JquB5zeEkGAh03kVxvnPXa1gyrjXhGYCyn5j
dYi8vVI0TBCGr2/jugknJTSU7+rZoySWfF8ZX72AiXrzOXnhc4TkA9nAVwUsoqw5
npHfcc4ilRxUWYQua+dNI2G4d18HKkKWi6d4q9xzdxMPsZBGgaiZ/13o493yocYE
FH/AuTfTK28KJXK9GZpuF787QltjXOc98cijUmvni/6QWfxNAKluYU16/FBGTvV8
6pAcB7E6/95qBdtwomtekOcn3ab+2y8OvZrG3626DB9reGw1wrEkMqb76LjqJ5xS
tVgmazoi0z61pc6BUCdaeSitq3NKzDCYghB9DWBrE3IatIjwWOqPmLYMDkUnp7jl
NW7fkcpU3eaA9cSqZxUaTfUCAYgHNO8wd7sqjWfdMNxVZXTDH48=
=SsN9
-----END PGP SIGNATURE-----"""

SIGNED_PERSON_UPDATE_VALID = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

person: Test person changed by PGP signed update
address: DashCare BV
address: Amsterdam
address: The Netherlands
phone: +31 20 000 0000
nic-hdl: PERSON-TEST
mnt-by: TEST-MNT
e-mail: email@example.com
changed: changed@example.com 20190701 # comment
source: TEST
-----BEGIN PGP SIGNATURE-----

iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAl0jNUQACgkQqDg7p4Dy
OMabkBAAq5gCcytpw9UwXMOkLXS2Fd0QfgVRpnc6l0aBmi7uWU6xWe72GU+LaNcC
1vi/OQqT38hXKtDmPMeItPhy5MHanagZZL+ZtVK3SGUaG3rV560Mna2sEnNTeJcb
OvMEg8JXDUP3O4T3kNudTCnBj2d1JhQUNfm7CivWMFe9dxfw+rvirzUnWlhKUZY/
93FGZ1/FpjlAOrLpcFTdvBXajBgpCCHTyTSWBs2KuR2gEWOzIzkyWXIHupwym671
nTg++M/ziPyYJXDv7PqKiBU3DnvSAAOialhk1fse9YW1Dj2dcHz8s2Ex8gv2TcLi
9e6gCF2rOBnusO3yVcqKNBEbpqB+wCbLPGG1C+8n177opTxUipm5kadDBRQy/sZA
P6740cd5Jky1gzWDykch+8ttd8MNVFoNotk1MpauU2zP5/agPuDJuoF6RbCMqX62
MsWp+9c1rlNNUTgQfqxTaEZ+oIj/mLK36iiMQzy0ey9GT/Viuow2WYDjDI5P+OB2
mZp0grLzKK07KdTf/+1WYZb09GhSYzPlKyg12KP3Zoaklh83uYn06mqaeN6YEXYE
zwBzW+p+qqN0rNRMFTNy3WnVVzZY5UWljU83jMBQkXiOSxo72/yIpG89xzi24Bqp
+pewy9PIcK1JBKvGyeO2Gh1K2tsrVYzs7aP5/RmkmUyrQeXa3l4=
=FLEo
-----END PGP SIGNATURE-----
"""

object_sample_mapping = {
    'as-block': SAMPLE_AS_BLOCK,
    'as-set': SAMPLE_AS_SET,
    'aut-num': SAMPLE_AUT_NUM,
    'domain': SAMPLE_DOMAIN,
    'filter-set': SAMPLE_FILTER_SET,
    'inet-rtr': SAMPLE_INET_RTR,
    'inet6num': SAMPLE_INET6NUM,
    'inetnum': SAMPLE_INETNUM,
    'key-cert': SAMPLE_KEY_CERT,
    'mntner': SAMPLE_MNTNER,
    'peering-set': SAMPLE_PEERING_SET,
    'person': SAMPLE_PERSON,
    'role': SAMPLE_ROLE,
    'route': SAMPLE_ROUTE,
    'route-set': SAMPLE_ROUTE_SET,
    'route6': SAMPLE_ROUTE6,
    'rtr-set': SAMPLE_RTR_SET,
}

TEMPLATE_ROUTE_OBJECT = """route:          [mandatory]  [single]    [primary/look-up key]
descr:          [optional]   [multiple]  []
origin:         [mandatory]  [single]    [primary key]
holes:          [optional]   [multiple]  []
member-of:      [optional]   [multiple]  [look-up key, weak references route-set]
inject:         [optional]   [multiple]  []
aggr-bndry:     [optional]   [single]    []
aggr-mtd:       [optional]   [single]    []
export-comps:   [optional]   [single]    []
components:     [optional]   [single]    []
admin-c:        [optional]   [multiple]  [look-up key, strong references role/person]
tech-c:         [optional]   [multiple]  [look-up key, strong references role/person]
geoidx:         [optional]   [multiple]  []
roa-uri:        [optional]   [single]    []
remarks:        [optional]   [multiple]  []
notify:         [optional]   [multiple]  []
mnt-by:         [mandatory]  [multiple]  [look-up key, strong references mntner]
changed:        [optional]   [multiple]  []
source:         [mandatory]  [single]    []
"""

TEMPLATE_PERSON_OBJECT = """person:    [mandatory]  [single]    [look-up key]
address:   [mandatory]  [multiple]  []
phone:     [mandatory]  [multiple]  []
fax-no:    [optional]   [multiple]  []
e-mail:    [mandatory]  [multiple]  []
nic-hdl:   [mandatory]  [single]    [primary/look-up key]
remarks:   [optional]   [multiple]  []
notify:    [optional]   [multiple]  []
mnt-by:    [mandatory]  [multiple]  [look-up key, strong references mntner]
changed:   [optional]   [multiple]  []
source:    [mandatory]  [single]    []
"""
