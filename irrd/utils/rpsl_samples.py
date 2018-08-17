# Sample objects used in various tests.
# flake8: noqa: W291,W293

SAMPLE_AS_BLOCK = """as-block:       AS2043 - as02043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT
changed:        2014-02-24T13:15:13Z
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
source:         RIPE
remarks:        remark
"""

SAMPLE_AS_SET = """as-set:         AS-RESTENA
descr:          Reseau Teleinformatique de l"Education Nationale
descr:          Educational and research network for Luxembourg
members:        AS2602, AS42909, AS51966
members:        AS49624
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
notify:         noc@restena.lu
mnt-by:         AS2602-MNT
changed:        2017-05-19T12:22:08Z
source:         RIPE
remarks:        remark
"""

SAMPLE_AUT_NUM = """aut-num:        as03255
as-name:        UARNET-AS
descr:          UARNet
descr:          EARN-Ukraine
remarks:        ---> Uplinks
export:         to AS3356 announce AS-UARNET
import:         from AS3356 accept ANY
export:         to AS174 announce AS-UARNET
import:         from AS174 accept ANY
mp-export:      afi ipv6.unicast to AS174 announce AS-UARNET
mp-import:      afi ipv6.unicast from AS174 accept ANY
export:         to AS8359 announce AS-UARNET
import:         from AS8359 accept ANY
export:         to AS3257 announce AS-UARNET
import:         from AS3257 accept ANY
export:         to AS3549 announce AS-UARNET
import:         from AS3549 accept ANY
export:         to AS9002 announce AS-UARNET
import:         from AS9002 accept ANY
mp-export:      afi ipv6.unicast to AS9002 announce AS-UARNET
mp-import:      afi ipv6.unicast from AS9002 accept ANY
remarks:        ---> Peers
export:         to AS31117 announce AS-UARNET AS-UAIX
import:         from AS31117 accept AS-ENERGOTEL
export:         to AS8501 announce AS-UARNET AS-UAIX
import:         from AS8501 accept AS-PLNET
export:         to AS35297 announce AS-UARNET
import:         from AS35297 accept AS-DL-WORLD
export:         to AS13188 announce AS-UARNET
import:         from AS13188 accept AS-BANKINFORM
export:         to AS12389 announce AS-UARNET
import:         from AS12389 accept AS-ROSTELECOM
export:         to AS35395 announce AS-UARNET
import:         from AS35395 accept AS-GECIXUAIX
export:         to AS50952 announce AS-UARNET
import:         from AS50952 accept AS-DATAIX
remarks:        ---> UA-IX
export:         to AS15645 announce AS-UARNET AS-PLNET AS-ENERGOTEL
import:         from AS15645 accept AS-UAIX
mp-export:      afi ipv6.unicast to AS15645 announce AS-UARNET
mp-import:      afi ipv6.unicast from AS15645 accept AS-UAIX-v6
remarks:        ---> DE-CIX
export:         to AS6695 announce AS-UARNET
import:         from AS6695 accept AS-DECIX
mp-export:      afi ipv6.unicast to AS6695 announce AS-UARNET
mp-import:      afi ipv6.unicast from AS6695 accept AS-DECIX-V6
export:         to AS6939 announce AS-UARNET
import:         from AS6939 accept AS-HURRICANE
export:         to AS20940 announce AS-UARNET
import:         from AS20940 accept AS-AKAMAI
export:         to AS13030 announce AS-UARNET
import:         from AS13030 accept AS-INIT7
export:         to AS5588 announce AS-UARNET
import:         from AS5588 accept AS-GTS-CE
export:         to AS6730 announce AS-UARNET
import:         from AS6730 accept AS-GLOBAL
export:         to AS29208 announce AS-UARNET
import:         from AS29208 accept AS-DIALTELECOM
export:         to AS42 announce AS-UARNET
import:         from AS42 accept AS-PCH
export:         to AS3856 announce AS-UARNET
import:         from AS3856 accept AS-PCH
export:         to AS19151 announce AS-UARNET
import:         from AS19151 accept AS-WVFIBER
export:         to AS5430 announce AS-UARNET
import:         from AS5430 accept AS-FREENETDE
export:         to AS6805 announce AS-UARNET
import:         from AS6805 accept AS-TDDE
export:         to AS8365 announce AS-UARNET
import:         from AS8365 accept AS-MANDA
export:         to AS13285 announce AS-UARNET
import:         from AS13285 accept AS-OPAL
export:         to AS22822 announce AS-UARNET
import:         from AS22822 accept AS-LLNW
export:         to AS4788 announce AS-UARNET
import:         from AS4788 accept AS-TMNET-CUSTOMERS
export:         to AS8966 announce AS-UARNET
import:         from AS8966 accept AS-EMIX
remarks:        ---> PL-IX
export:         to AS8545 announce AS-UARNET
import:         from AS8545 accept AS-PLIX
remarks:        ---> Other Peers
export:         to AS25229 announce AS-UARNET
import:         from AS25229 accept AS25229:AS-CUST
export:         to AS31210 announce AS-UARNET
import:         from AS31210 accept AS-DTEL-IX
remarks:        ---
export:         to AS3319 announce ANY
import:         from AS3319 accept AS-KSNET
export:         to AS13249 announce AS-UARNET
import:         from AS13249 accept ANY
export:         to AS6849 announce AS-UARNET
import:         from AS6849 accept ANY
export:         to AS25462 announce AS-UARNET
import:         from AS25462 accept ANY
export:         to AS6807 announce ANY
import:         from AS6807 accept AS6807
export:         to AS6846 announce ANY
import:         from AS6846 accept AS6846
export:         to AS12700 announce ANY
import:         from AS12700 accept AS12700
export:         to AS15626 announce ANY
import:         from AS15626 accept AS-ITL
export:         to AS41166 announce ANY
import:         from AS41166 accept AS41166
export:         to AS15772 announce AS-UARNET
import:         from AS15772 accept ANY
export:         to AS13307 announce ANY
import:         from AS13307 accept AS-SKIF
mp-export:      afi ipv6.unicast to AS13307 announce ANY
mp-import:      afi ipv6.unicast from AS13307 accept AS-SKIF-V6
export:         to AS35004 announce ANY
import:         from AS35004 accept AS-NETGRUP
export:         to AS16324 announce ANY
import:         from AS16324 accept AS16324
export:         to AS20754 announce ANY
import:         from AS20754 accept AS20754
export:         to AS20873 announce ANY
import:         from AS20873 accept AS-P5
export:         to AS21131 announce ANY
import:         from AS21131 accept AS21131
mp-export:      afi ipv6.unicast to AS21131 announce ANY
mp-import:      afi ipv6.unicast from AS21131 accept AS21131
export:         to AS21256 announce ANY
import:         from AS21256 accept AS21256
export:         to AS21488 announce ANY
import:         from AS21488 accept AS-EMPLOT
export:         to AS24893 announce ANY
import:         from AS24893 accept AS24893
export:         to AS25119 announce ANY
import:         from AS25119 accept AS25119
export:         to AS25143 announce ANY
import:         from AS25143 accept AS-IU
export:         to AS28776 announce ANY
import:         from AS28776 accept AS28776
export:         to AS29044 announce ANY
import:         from AS29044 accept AS-IF-INFOCOM
export:         to AS29375 announce ANY
import:         from AS29375 accept AS29375
export:         to AS29442 announce ANY
import:         from AS29442 accept AS-INETCOM
export:         to AS31145 announce ANY
import:         from AS31145 accept AS31145
export:         to AS31556 announce ANY
import:         from AS31556 accept AS-ARKADAX
export:         to AS24962 announce ANY
import:         from AS24962 accept AS24962
export:         to AS25521 announce ANY
import:         from AS25521 accept AS25521
export:         to AS28858 announce ANY
import:         from AS28858 accept AS-LECOS
export:         to AS34046 announce ANY
import:         from AS34046 accept AS-SHIELD
export:         to AS35412 announce ANY
import:         from AS35412 accept AS-SET-DCS
export:         to AS35409 announce ANY
import:         from AS35409 accept AS-UPLINK
export:         to AS6884 announce ANY
import:         from AS6884 accept AS-EURONET-UA
export:         to AS31062 announce ANY
import:         from AS31062 accept AS31062
export:         to AS20950 announce ANY
import:         from AS20950 accept AS20950
export:         to AS21075 announce ANY
import:         from AS21075 accept AS21075
export:         to AS21151 announce ANY
import:         from AS21151 accept AS21151:AS-CUSTOMERS
export:         to AS24896 announce ANY
import:         from AS24896 accept AS24896 AS35362
export:         to AS34251 announce ANY
import:         from AS34251 accept AS-IMC
export:         to AS34399 announce ANY
import:         from AS16223 accept AS-BITTERNET
export:         to AS16223 announce ANY
import:         from AS35345 accept AS35345
export:         to AS25282 announce ANY
import:         from AS25282 accept AS-KS
export:         to AS30886 announce ANY
import:         from AS30886 accept AS-KOMITEX
mp-export:      afi ipv6.unicast to AS30886 announce ANY
mp-import:      afi ipv6.unicast from AS30886 accept AS-KOMITEX
export:         to AS39066 announce ANY
import:         from AS39066 accept AS39066
export:         to AS34323 announce ANY
import:         from AS34323 accept AS-IPCOM
export:         to AS39127 announce ANY
import:         from AS39127 accept AS39127
export:         to AS34118 announce ANY
import:         from AS34118 accept AS34118
export:         to AS39247 announce ANY
import:         from AS39247 accept AS-LVIVNET
export:         to AS24593 announce ANY
import:         from AS24593 accept AS-MOBICOM
export:         to AS39084 announce ANY
import:         from AS39084 accept AS39084
export:         to AS34672 announce ANY
import:         from AS34672 accept AS-ELHIM
export:         to AS35296 announce ANY
import:         from AS35296 accept AS35296
export:         to AS39399 announce ANY
import:         from AS39399 accept AS-FENIXVT
export:         to AS39431 announce ANY
import:         from AS39431 accept AS-ARGOCOM
export:         to AS41619 announce ANY
import:         from AS41619 accept AS41619
export:         to AS41649 announce ANY
import:         from AS41649 accept AS-ROYAL
export:         to AS42381 announce ANY
import:         from AS42381 accept AS42381
export:         to AS42501 announce ANY
import:         from AS42501 accept AS42501
export:         to AS43206 announce ANY
import:         from AS43206 accept AS43206
export:         to AS43880 announce ANY
import:         from AS43880 accept AS-LITECH
export:         to AS43864 announce ANY
import:         from AS43864 accept AS-INTEGRA-MEDIA
export:         to AS44318 announce ANY
import:         from AS44318 accept AS44318
export:         to AS44411 announce ANY
import:         from AS44411 accept AS44411
export:         to AS44629 announce ANY
import:         from AS44616 accept AS44616
export:         to AS44616 announce ANY
import:         from AS44629 accept AS44629
export:         to AS47266 announce ANY
import:         from AS47266 accept AS47266
export:         to AS31725 announce ANY
import:         from AS31725 accept AS-SHTORM
export:         to AS28996 announce ANY
import:         from AS28996 accept AS-IMPULS_ZT
export:         to AS47800 announce ANY
import:         from AS47800 accept AS47800
export:         to AS42112 announce ANY
import:         from AS42112 accept AS42112
export:         to AS41435 announce ANY
import:         from AS41435 accept AS41435 AS-NETUNDER
export:         to AS48082 announce ANY
import:         from AS48082 accept AS48082
export:         to AS39065 announce ANY
import:         from AS39065 accept AS-SOHO-TO-ANY
export:         to AS35067 announce ANY
import:         from AS35067 accept AS-PROKK
export:         to AS34187 announce ANY
import:         from AS34187 accept AS-RENOME
export:         to AS43613 announce ANY
import:         from AS43613 accept AS-SOWA
export:         to AS47985 announce ANY
import:         from AS47985 accept AS47985
export:         to AS35688 announce ANY
import:         from AS35688 accept AS35688
export:         to AS42802 announce ANY
import:         from AS42802 accept AS42802
export:         to AS48420 announce ANY
import:         from AS48420 accept AS48420
export:         to AS48006 announce ANY
import:         from AS48006 accept AS-LANGATE-NET
export:         to AS6876 announce ANY
import:         from AS6876 accept AS-TENET-UA
export:         to AS41867 announce ANY
import:         from AS41867 accept AS-GEONIC
export:         to AS24945 announce ANY
import:         from AS24945 accept AS-VNTP
export:         to AS48589 announce ANY
import:         from AS48589 accept AS48589
export:         to AS6789 announce ANY
import:         from AS6789 accept AS-CRELCOM
export:         to AS34661 announce ANY
import:         from AS34661 accept AS-BRIZ-TO-ODIX
export:         to AS8654 announce ANY
import:         from AS8654 accept AS-CRIMEAINFOCOM
export:         to AS43802 announce ANY
import:         from AS43802 accept AS-MYST
export:         to AS43258 announce ANY
import:         from AS43258 accept AS43258
export:         to AS48957 announce ANY
import:         from AS48957 accept AS-LVIV
export:         to AS43103 announce ANY
import:         from AS43103 accept AS-ONETELECOM
export:         to AS12545 announce ANY
import:         from AS12545 accept AS-TCOM-UZH
export:         to AS31234 announce ANY
import:         from AS31234 accept AS-KRAM-UZH
export:         to AS15461 announce ANY
import:         from AS15461 accept AS-SOLVER
export:         to AS21437 announce ANY
import:         from AS21437 accept AS-AVITI
export:         to AS25498 announce ANY
import:         from AS25498 accept AS-MOBICOM-UA
export:         to AS42239 announce ANY
import:         from AS42239 accept AS-FARLINE
export:         to AS25132 announce ANY
import:         from AS25132 accept AS25132
export:         to AS196740 announce ANY
import:         from AS196740 accept AS196740
export:         to AS31272 announce ANY
import:         from AS31272 accept AS-WILDPARK
mp-export:      afi ipv6.unicast to AS31272 announce ANY
mp-import:      afi ipv6.unicast from AS31272 accept AS-WILDPARK-V6
export:         to AS49183 announce ANY
import:         from AS49183 accept AS49183:AS-CUSTOMERS
export:         to AS48323 announce ANY
import:         from AS48323 accept AS-NEIRON
export:         to AS44533 announce ANY
import:         from AS44533 accept AS44533
export:         to AS49125 announce ANY
import:         from AS49125 accept AS-UTEAM
export:         to AS49356 announce ANY
import:         from AS49356 accept AS49356
export:         to AS48094 announce ANY
import:         from AS48094 accept AS-ELECTRA
export:         to AS34715 announce ANY
import:         from AS34715 accept AS34715
export:         to AS28761 announce ANY
import:         from AS28761 accept AS28761:AS-CUSTOMERS
export:         to AS49480 announce ANY
import:         from AS49480 accept AS49480
export:         to AS8788 announce ANY
import:         from AS8788 accept AS-ADAM-UA
import:         from AS8788 accept AS-ADAM
export:         to AS41665 announce ANY
import:         from AS41665 accept AS41665
export:         to AS28907 announce ANY
import:         from AS28907 accept AS-MIROHOST
mp-export:      afi ipv6.unicast to AS28907 announce ANY
mp-import:      afi ipv6.unicast from AS28907 accept AS-MIROHOST-v6
export:         to AS43266 announce ANY
import:         from AS43266 accept AS-ABSET
export:         to AS21312 announce ANY
import:         from AS21312 accept AS-CHEREDA-SM
export:         to AS47743 announce ANY
import:         from AS47743 accept AS-IRENASU
export:         to AS42896 announce ANY
import:         from AS42896 accept AS-ACSGROUP
export:         to AS41972 announce ANY
import:         from AS41972 accept AS-MAYCOM
export:         to AS49827 announce ANY
import:         from AS49827 accept AS49827
export:         to AS40965 announce ANY
import:         from AS40965 accept AS-RISE
export:         to AS35680 announce ANY
import:         from AS35680 accept AS35680
export:         to AS15595 announce ANY
import:         from AS15595 accept AS-SKYLINE-TO-UAIX
export:         to AS44722 announce ANY
import:         from AS44722 accept AS44722
export:         to AS39728 announce ANY
import:         from AS39728 accept AS-LUGANET
export:         to AS35649 announce ANY
import:         from AS35649 accept AS-DILINES
export:         to AS39769 announce ANY
import:         from AS39769 accept AS39769
export:         to AS49984 announce ANY
import:         from AS49984 accept AS49984
export:         to AS41161 announce ANY
import:         from AS41161 accept AS-REALWEB
export:         to AS12986 announce ANY
import:         from AS12986 accept AS-UKRSC AS12963:AS-CUST2UPD
mp-export:      afi ipv6.unicast to AS12986 announce ANY
mp-import:      afi ipv6.unicast from AS12986 accept AS12986
export:         to AS49883 announce ANY
import:         from AS49883 accept AS49883
export:         to AS6886 announce ANY
import:         from AS6886 accept AS-INTS
export:         to AS43764 announce ANY
import:         from AS43764 accept AS43764
export:         to AS13103 announce ANY
import:         from AS13103 accept AS-VALOR
export:         to AS50392 announce ANY
import:         from AS50392 accept AS-CAMPUS-RV
mp-export:      afi ipv6.unicast to AS50392 announce ANY
mp-import:      afi ipv6.unicast from AS50392 accept AS-CAMPUS-RV
export:         to AS44894 announce ANY
import:         from AS44894 accept AS-UCMA
export:         to AS48533 announce ANY
import:         from AS48533 accept AS-TANGRAM
export:         to AS49491 announce ANY
import:         from AS49491 accept AS49491
export:         to AS196790 announce ANY
import:         from AS196790 accept AS196790
export:         to AS25403 announce ANY
import:         from AS25403 accept AS25403
remarks:        ---> Test
export:         to AS43110 announce ANY
import:         from AS43110 accept AS-ROSTNET
export:         to AS8343 announce ANY
import:         from AS8343 accept AS-DORIS
export:         to AS50569 announce ANY
import:         from AS50569 accept AS-ISOFTS2
export:         to AS35362 announce ANY
import:         from AS35362 accept AS-35362
export:         to AS50211 announce ANY
import:         from AS50211 accept AS50211
export:         to AS15738 announce ANY
import:         from AS15738 accept AS-EXPRESSUA
export:         to AS50579 announce ANY
import:         from AS50579 accept AS-SIM-LTD
export:         to AS50662 announce ANY
import:         from AS50662 accept AS50662
export:         to AS50297 announce ANY
import:         from AS50297 accept AS-CITONET
export:         to AS30822 announce ANY
import:         from AS30822 accept AS30822
export:         to AS196975 announce ANY
import:         from AS196975 accept AS196975
export:         to AS49223 announce ANY
import:         from AS49223 accept AS-EVEREST
export:         to AS41709 announce ANY
import:         from AS41709 accept AS-LDS-UA
export:         to AS197073 announce ANY
import:         from AS197073 accept AS197073
export:         to AS47898 announce ANY
import:         from AS47898 accept AS47898
export:         to AS28804 announce ANY
import:         from AS28804 accept AS28804
export:         to AS50012 announce ANY
import:         from AS50012 accept AS50012
export:         to AS50325 announce ANY
import:         from AS50325 accept AS-ASV-UARNET
export:         to AS29576 announce ANY
import:         from AS29576 accept AS-POISK-UA
export:         to AS49706 announce ANY
import:         from AS49706 accept AS49706
export:         to AS6723 announce ANY
import:         from AS6723 accept AS-6723
mp-export:      afi ipv6.unicast to AS6723 announce ANY
mp-import:      afi ipv6.unicast from AS6723 accept AS-6723-v6
export:         to AS39512 announce ANY
import:         from AS39512 accept AS39512
export:         to AS44171 announce ANY
import:         from AS44171 accept AS44171
export:         to as47702 announce ANY
import:         from as47702 accept AS-DISCOVERY
export:         to AS51622 announce ANY
import:         from AS51622 accept AS51622
export:         to AS197348 announce ANY
import:         from AS197348 accept AS197348
export:         to AS6702 announce ANY
import:         from AS6702 accept AS-APEX
export:         to AS197327 announce ANY
import:         from AS197327 accept AS197327
export:         to AS48117 announce ANY
import:         from AS48117 accept AS48117
export:         to AS51858 announce ANY
import:         from AS51858 accept AS51858
export:         to AS49332 announce ANY
import:         from AS49332 accept AS49332
export:         to AS12687 announce ANY
import:         from AS12687 accept AS-URAN-INET
mp-export:      afi ipv6.unicast to AS12687 announce ANY
mp-import:      afi ipv6.unicast from AS12687 accept AS-URAN-INET-v6
export:         to AS48964 announce ANY
import:         from AS48964 accept AS-ENTERRA
export:         to AS52074 announce ANY
import:         from AS52074 accept AS52074
export:         to AS52071 announce ANY
import:         from AS52071 accept AS-PIEOC
export:         to AS43022 announce ANY
import:         from AS43022 accept AS-UASEECH
export:         to AS35816 announce ANY
import:         from AS35816 accept AS-LANCOM
export:         to AS44921 announce ANY
import:         from AS44921 accept AS-STIKONET
export:         to AS197131 announce ANY
import:         from AS197131 accept AS197131
export:         to AS56429 announce ANY
import:         from AS56429 accept AS56429
export:         to AS197610 announce ANY
import:         from AS197610 accept AS197610
export:         to AS51314 announce ANY
import:         from AS51314 accept AS51314
export:         to AS197158 announce ANY
import:         from AS197158 accept AS197158
export:         to AS56394 announce ANY
import:         from AS56394 accept AS56394
export:         to AS34814 announce ANY
import:         from AS34814 accept AS-DYTYNETS
export:         to AS31593 announce ANY
import:         from AS31593 accept AS31593
export:         to AS29685 announce ANY
import:         from AS29685 accept AS-OKNET
export:         to AS34448 announce ANY
import:         from AS34448 accept AS-SNTUA
export:         to AS50803 announce ANY
import:         from AS50803 accept AS50803
export:         to AS21310 announce ANY
import:         from AS21310 accept AS-SATELLITE
export:         to AS43781 announce ANY
import:         from AS43781 accept AS43781
export:         to AS49131 announce ANY
import:         from AS49131 accept AS-INTELEKT
export:         to AS41009 announce ANY
import:         from AS41009 accept AS41009
export:         to AS51930 announce ANY
import:         from AS51930 accept AS51930
export:         to AS16327 announce ANY
import:         from AS16327 accept AS16327
export:         to AS20539 announce ANY
import:         from AS20539 accept AS-RS
export:         to AS31305 announce ANY
import:         from AS31305 accept AS-ALBA
export:         to AS3254 announce ANY
import:         from AS3254 accept AS-LUCKY
export:         to AS50380 announce ANY
import:         from AS50380 accept AS50380
export:         to AS41631 announce ANY
import:         from AS41631 accept AS-SOBORKA
export:         to AS34355 announce ANY
import:         from AS34355 accept AS-INFOSFERA
export:         to as39422 announce ANY
import:         from as39422 accept as39422
export:         to AS47799 announce ANY
import:         from AS47799 accept AS-ONU
export:         to AS20934 announce ANY
import:         from AS20934 accept AS-Maket
export:         to AS39315 announce ANY
import:         from AS39315 accept AS39315
export:         to AS43320 announce ANY
import:         from AS43320 accept AS-ASTRATELCOM
export:         to AS50161 announce ANY
import:         from AS50161 accept AS-VELES-EXT
mp-export:      afi ipv6.unicast to AS50161 announce ANY
mp-import:      afi ipv6.unicast from AS50161 accept AS50161
export:         to AS50487 announce ANY
import:         from AS50487 accept AS50487
export:         to AS50479 announce ANY
import:         from AS50479 accept AS50479
export:         to AS29439 announce ANY
import:         from AS29439 accept AS-RIFT
export:         to AS56400 announce ANY
import:         from AS56400 accept AS56400
export:         to AS50027 announce ANY
import:         from AS50027 accept AS-KREMEN-NET-CUSTOMERS
export:         to AS198323 announce ANY
import:         from AS198323 accept AS198323
export:         to AS198251 announce ANY
import:         from AS198251 accept AS-LEOTEL
export:         to AS48229 announce ANY
import:         from AS48229 accept AS-STARLIGHT
export:         to AS42702 announce ANY
import:         from AS42702 accept AS-DICS
export:         to AS50861 announce ANY
import:         from AS50861 accept AS50861
export:         to AS50648 announce ANY
import:         from AS50648 accept AS50648
export:         to AS58021 announce ANY
import:         from AS58021 accept AS58021
export:         to AS58309 announce ANY
import:         from AS58309 accept AS58309
export:         to AS58332 announce ANY
import:         from AS58332 accept AS58332
export:         to AS39680 announce ANY
import:         from AS39680 accept AS39680
export:         to AS42458 announce ANY
import:         from AS42458 accept AS42458
export:         to AS59492 announce ANY
import:         from AS59492 accept AS-TELEFAX
export:         to AS57582 announce ANY
import:         from AS57582 accept AS57582
export:         to AS47361 announce ANY
import:         from AS47361 accept AS47361
export:         to AS51672 announce ANY
import:         from AS51672 accept AS51672
export:         to AS196953 announce ANY
import:         from AS196953 accept AS-MALTAPLUS_IN
export:         to AS41871 announce ANY
import:         from AS41871 accept AS-ORG-TR2-RIPE
export:         to AS39445 announce ANY
import:         from AS39445 accept AS-LIS
export:         to AS50115 announce ANY
import:         from AS50115 accept AS50115
export:         to AS49461 announce ANY
import:         from AS49461 accept AS-KAMPOD
export:         to AS199351 announce ANY
import:         from AS199351 accept AS199351
export:         to AS47245 announce ANY
import:         from AS47245 accept AS-NTLINE
export:         to AS56543 announce ANY
import:         from AS56543 accept AS56543
export:         to AS60386 announce ANY
import:         from AS60386 accept AS60386
export:         to AS41278 announce ANY
import:         from AS41278 accept AS41278
export:         to AS21131 announce ANY
import:         from AS21131 accept AS-SACURA
export:         to AS196808 announce ANY
import:         from AS196808 accept AS196808
export:         to AS41360 announce ANY
import:         from AS41360 accept AS-NEOCOM
export:         to AS15577 announce ANY
import:         from AS15577 accept AS-RNS
export:         to AS197035 announce ANY
import:         from AS197035 accept AS197035
mp-export:      afi ipv6.unicast to AS60334 announce ANY
mp-import:      afi ipv6.unicast from AS60334 accept AS60334
export:         to AS16038 announce ANY
import:         from AS16038 accept AS16038
export:         to AS34278 announce ANY
import:         from AS34278 accept AS34278
export:         to AS198720 announce ANY
import:         from AS198720 accept AS-MOBIKOM
export:         to AS44686 announce ANY
import:         from AS44686 accept AS44686
export:         to AS44800 announce ANY
import:         from AS44800 accept AS44800
import:         from AS44800 accept AS42905
export:         to AS51784 announce ANY
import:         from AS51784 accept AS-XCITY
export:         to AS48589 announce ANY
import:         from AS48589 accept AS-SOWA
export:         to AS56823 announce ANY
import:         from AS56823 accept AS56823
export:         to AS50130 announce ANY
import:         from AS50130 accept AS50130
export:         to AS57944 announce ANY
import:         from AS57944 accept AS-IPC
export:         to AS58015 announce ANY
import:         from AS58015 accept AS58015
export:         to AS8461 announce ANY
import:         from AS8461 accept AS8461
export:         to AS31633 announce ANY
import:         from AS31633 accept AS-LANTELECOM-ANY
mp-export:      afi ipv6.unicast to AS57944 announce ANY
mp-import:      afi ipv6.unicast from AS57944 accept AS-IPC6
export:         to AS30891 announce ANY
import:         from AS30891 accept AS30891
export:         to AS20897 announce ANY
import:         from AS20897 accept AS20897
export:         to AS49204 announce ANY
import:         from AS49204 accept AS-ITT
export:         to AS39822 announce ANY
import:         from AS39822 accept AS-FOBOS1
export:         to AS39471 announce ANY
import:         from AS39471 accept AS39471
export:         to AS44209 announce ANY
import:         from AS44209 accept AS-FINACTIVE
export:         to AS59671 announce ANY
import:         from AS59671 accept AS59671
export:         to AS59564 announce ANY
import:         from AS59564 accept AS-Unit-IS
export:         to AS57060 announce ANY
import:         from AS57060 accept AS57060
export:         to AS29213 announce ANY
import:         from AS29213 accept AS29213
export:         to AS47673 announce ANY
import:         from AS47673 accept AS47673
export:         to AS41285 announce ANY
import:         from AS41285 accept AS41285
export:         to AS201094 announce ANY
import:         from AS201094 accept AS201094
export:         to AS59468 announce ANY
import:         from AS59468 accept AS59468
export:         to AS60134 announce ANY
import:         from AS60134 accept AS60134
export:         to AS200510 announce ANY
import:         from AS200510 accept AS200510
export:         to AS49620 announce ANY
import:         from AS49620 accept AS49620
export:         to AS21354 announce ANY
import:         from AS21354 accept AS21354
export:         to AS20536 announce ANY
import:         from AS20536 accept AS20536
export:         to AS61986 announce ANY
import:         from AS61986 accept AS61986
export:         to AS197522 announce ANY
import:         from AS197522 accept AS-KIM
export:         to AS24812 announce ANY
import:         from AS24812 accept AS-HOME-NET
export:         to AS2864 announce ANY
import:         from AS2864 accept AS2864
export:         to AS57519 announce ANY
import:         from AS57519 accept AS57519
export:         to AS59497 announce ANY
import:         from AS59497 accept AS-BUKNET-EXT
export:         to AS198820 announce ANY
import:         from AS198820 accept AS198820
export:         to AS43175 announce ANY
import:         from AS43175 accept AS43175
export:         to AS56522 announce ANY
import:         from AS56522 accept AS56522
export:         to AS43418 announce ANY
import:         from AS43418 accept AS-ANTIDOT
export:         to AS203830 announce ANY
import:         from AS203830 accept AS203830
export:         to AS34058 announce ANY
import:         from AS34058 accept AS34058
export:         to AS31388 announce ANY
import:         from AS31388 accept AS-ICONNECT
export:         to AS39762 announce ANY
import:         from AS39762 accept AS-VAK
export:         to AS50303 announce ANY
import:         from AS50303 accept AS-TECC
export:         to AS51500 announce ANY
import:         from AS51500 accept AS51500
export:         to AS13032 announce ANY
import:         from AS13032 accept AS13032
export:         to AS45043 announce ANY
import:         from AS45043 accept AS45043
export:         to AS42504 announce ANY
import:         from AS42504 accept AS-UKRBIT
export:         to AS49824 announce ANY
import:         from AS49824 accept AS-ACTPA
export:         to AS41018 announce ANY
import:         from AS41018 accept AS-OMNILANCE
mp-export:      afi ipv6.unicast to AS41018 announce ANY
mp-import:      afi ipv6.unicast from AS41018 accept AS-OMNILANCE-V6
export:         to AS47725 announce ANY
import:         from AS47725 accept AS47725:AS-CUSTOMERS
mp-export:      afi ipv6.unicast to AS47725 announce ANY
mp-import:      afi ipv6.unicast from AS47725 accept AS47725:AS-CUSTOMERS
export:         to AS43656 announce ANY
import:         from AS43656 accept AS43656
export:         to AS44340 announce ANY
import:         from AS44340 accept AS44340
export:         to AS64490 announce ANY
import:         from AS64490 accept AS64490
export:         to AS57479 announce ANY
import:         from AS57479 accept AS-RIFT
export:         to AS50594 announce ANY
import:         from AS50594 accept AS-VINFAST
export:         to AS42563 announce ANY
import:         from AS42563 accept AS42563
export:         to AS59577 announce ANY
import:         from AS59577 accept AS59577
export:         to AS9098 announce ANY
import:         from AS9098 accept AS-SETFKTR
export:         to AS41323 announce ANY
import:         from AS41323 accept AS41323
export:         to AS39027 announce ANY
import:         from AS39027 accept AS-BATYEVKA
export:         to AS205127 announce ANY
import:         from AS205127 accept AS205127
export:         to AS60777 announce ANY
import:         from AS60777 accept AS60777
export:         to AS39530 announce ANY
import:         from AS39530 accept AS39530
export-via:     AS6777 to AS-ANY announce AS-UARNET
import-via:     AS6777 from AS-ANY accept ANY
export:         to AS39443 announce ANY
import:         from AS39443 accept AS39443
mp-import:      afi ipv6.unicast from AS9098 accept AS-SETFKTRv6
export:         to AS15169 announce ANY
import:         from AS15169 accept AS15169
export:         to AS16509 announce ANY
import:         from AS16509 accept AS16509
export:         to AS196844 announce ANY
import:         from AS196844 accept AS196844
export:         to AS32934 announce ANY
import:         from AS32934 accept AS32934
export:         to AS46489 announce ANY
import:         from AS46489 accept AS46489
export:         to AS48850 announce ANY
import:         from AS48850 accept AS48850
export:         to AS207085 announce ANY
import:         from AS207085 accept AS207085
export:         to AS205420 announce ANY
import:         from AS205420 accept AS205420
export:         to AS204584 announce ANY
import:         from AS204584 accept AS204584
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
mnt-by:         RIPE-NCC-END-MNT
notify:         lir@uar.net
mnt-by:         AS3255-MNT
changed:        2018-03-13T19:16:16Z
source:         RIPE
remarks:        remark
"""

SAMPLE_DOMAIN = """domain:         200.193.193.in-addr.arpa
descr:          Splitblock-200
descr:          Lucky Line, Ltd.
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
zone-c:         DUMY-RIPE
nserver:        ns.lucky.net
nserver:        ns.gu.kiev.ua
mnt-by:         AS3254-MNT
changed:        2011-02-04T10:33:38Z
source:         RIPE
                # foo
remarks:        remark
"""

SAMPLE_FILTER_SET = """filter-set:     fltr-bogons-integra-it
descr:          Generic anti-bogons filter
remarks:        adapted by Secure BGP Template Version 2.1 robt@cymru.com
remarks:        http://www.enteract.com/~robt/Docs/Articles
remarks:        see also:
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
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
mnt-by:         AS12784-MNT
changed:        2002-12-04T11:34:27Z
source:         RIPE
remarks:        remark
"""

SAMPLE_INET_RTR = """inet-rtr:       kst1-core.swip.net
local-as:       AS1257
ifaddr:         146.188.49.14 masklen 30
ifaddr:         195.158.247.62 masklen 30
peer:           BGP4 146.188.49.13 asno(AS702)
peer:           BGP4 195.158.247.61 asno(AS1755)
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
mnt-by:         AS1257-MNT
changed:        2001-09-21T22:07:57Z
source:         RIPE
remarks:        remark
"""

SAMPLE_INET6NUM = """inet6num:       2001:638:501::/48
netname:        UNI-ESSEN
descr:          Universitaet Duisburg-Essen
descr:          Zentrum fuer Informations- und Mediendienste
descr:          Schuetzenbahn 70
descr:          45127 Essen
descr:          Germany
country:        DE
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
notify:         netadm@netz.uni-essen.de
mnt-by:         DFN-HM-MNT
status:         ASSIGNED
changed:        2011-10-14T15:05:09Z
source:         RIPE
remarks:        remark
"""

SAMPLE_INETNUM = """inetnum:        80.16.151.184 - 80.016.151.191
netname:        NETECONOMY-MG41731
descr:          TELECOM ITALIA LAB SPA
country:        IT
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
status:         ASSIGNED PA
notify:         neteconomy.rete@telecomitalia.it
mnt-by:         INTERB-MNT
changed:        2001-09-21T22:08:01Z
source:         RIPE
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
certif:         
certif:         mQINBFnY7YoBEADH5ooPsoR9G/dNxrdHRMJeDHXCSQbwgXWEez5/F8/BZKV9occ/
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
admin-c:        SR13427-RIPE
tech-c:         SR13427-RIPE
mnt-by:         SR42-MNT
changed:        2018-04-10T13:39:39Z
source:         RIPE
"""

SAMPLE_MNTNER = """mntner:         AS760-MNt
admin-c:        DUMY-RIPE
upd-to:         unread@ripe.net
auth:           PGPKey-80F238C6
auth:           CRYPT-PW LEuuhsBJNFV0Q  # crypt-password
auth:           MD5-pw $1$fgW84Y9r$kKEn9MUq8PChNKpQhO6BM.  # md5-password
mnt-by:         AS760-MNT
mnt-by:         ACONET-LIR-MNT,ACONET2-LIR-MNT
changed:        2016-10-05T10:41:15Z
source:         RIPE
remarks:        remark
"""

SAMPLE_PEERING_SET = """peering-set:    prng-MEDIAFAX
descr:          DNT peering with MEDIAFAX
peering:        AS8930 at 194.102.255.254
remarks:        MEDIAFAX
tech-c:         DUMY-RIPe
tech-c:         DUMY2-RIPe
admin-c:        DUMY-RIPE
notify:         hostmaster@dnt.ro
mnt-by:         AS6746-MNT
changed:        2001-09-21T23:07:39Z
source:         RIPE
remarks:        remark
"""

SAMPLE_PERSON = """person:         Placeholder Person Object
address:        RIPE Network Coordination Centre
address:        P.O. Box 10096
address:        1001 EB Amsterdam
address:        The Netherlands
phone:          +31 20 535 4444
nic-hdl:        DUMY-RIPe
mnt-by:         RIPE-DBM-MNT
e-mail:         bitbucket@ripe.net
remarks:        **********************************************************
remarks:        * This is a placeholder object to protect personal data.
remarks:        * To view the original object, please query the RIPE
remarks:        * Database at:
remarks:        * http://www.ripe.net/whois
remarks:        **********************************************************
changed:        2009-07-24T17:00:00Z
source:         RIPE
"""

SAMPLE_ROLE = """role:           Bisping Und Bisping Contact
address:        Dummy address for BISP-RIPE
phone:          +31205354444
fax-no:         +31205354444
e-mail:         unread@ripe.net
admin-c:        DUMY-RIPE
tech-c:         DUMY-RIPE
nic-hdl:        BISP-RIPE
notify:         netmaster@bisping.de
mnt-by:         BISPING-MNT
changed:        2017-11-21T15:56:58Z
source:         RIPE
remarks:        remark
"""

SAMPLE_ROUTE = """route:          193.254.030.00/24
descr:          Lufthansa Airplus Servicekarten GmbH
origin:         AS12726
mnt-by:         AS12312-MNT
changed:        2009-10-15T09:32:17Z
source:         RIPE
remarks:        remark
"""

SAMPLE_ROUTE_SET = """route-set:      RS-TEST
descr:          TEST Community for development
mbrs-by-ref:    UUNET-MNT
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
mnt-by:         UUNET-MNT
mp-members:     2001:1578:0200:0::/040
changed:        2001-09-22T09:34:03Z
source:         RIPE
remarks:        remark
"""

SAMPLE_ROUTE6 = """route6:         2001:1578:200::/40
descr:          GEFOEKOM-DE-ALLOC
origin:         AS12817
mnt-by:         EXAmple-MNT
changed:        2004-12-29T21:30:40Z
source:         RIPE
remarks:        remark
"""

SAMPLE_RTR_SET = """rtr-set:        rtrs-mways-callback
descr:          mediaWays GmbH
descr:          Huelshorstweg 30
descr:          D-33415 Verl
descr:          DE
members:        rmws-brln-de07.nw.mediaWays.net
members:        rmws-brmn-de02.nw.mediaWays.net
members:        rmws-dsdn-de01.nw.mediaWays.net
members:        rmws-dtmd-de02.nw.mediaWays.net
members:        rmws-essn-de03.nw.mediaWays.net
members:        rmws-frnk-de03.nw.mediaWays.net
members:        rmws-gtso-de11.nw.mediaWays.net
members:        rmws-gtso-de13.nw.mediaWays.net
members:        rmws-hmbg-de07.nw.mediaWays.net
members:        rmws-hnvr-de04.nw.mediaWays.net
members:        rmws-koln-de02.nw.mediaWays.net
members:        rmws-mnch-de03.nw.mediaWays.net
members:        rmws-nrbg-de02.nw.mediaWays.net
members:        rmws-srbk-de02.nw.mediaWays.net
members:        rtrs-other-set
remarks:        -------------------------------------------------------
remarks:        The mediaWays NCC is reachable any time at ncc@mediaWays.net or
remarks:        phone: +49 5241 80 1701
remarks:        -------------------------------------------------------
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
mnt-by:         MDA-Z
changed:        2001-09-22T09:34:04Z
source:         RIPE
remarks:        remark
"""

SAMPLE_UNKNOWN_CLASS = """foo-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT
changed:        2014-02-24T13:15:13Z
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
source:         RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_MALFORMED_EMPTY_LINE = """as-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT

tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
source:         RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_MALFORMED_ATTRIBUTE_NAME = """as-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
$t-by:         RIPE-NCC-HM-MNT
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
source:         RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_MISSING_MANDATORY_ATTRIBUTE = """as-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
mnt-by:         RIPE-NCC-HM-MNT
admin-c:        DUMY-RIPE
source:         RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_UNKNOWN_ATTRIBUTE = """as-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
tech-c:         DUMY-RIPE
foo: bar
mnt-by:         RIPE-NCC-HM-MNT
admin-c:        DUMY-RIPE
source:         RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_INVALID_MULTIPLE_ATTRIBUTE = """as-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
tech-c:         DUMY-RIPE
mnt-by:         RIPE-NCC-HM-MNT
admin-c:        DUMY-RIPE
source:         RIPE
source:         NOT-RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_MALFORMED_PK = """as-block:       AS2043 - ASX
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
mnt-by:         RIPE-NCC-HM-MNT
source:         RIPE
changed:        2001-09-22T09:34:04Z
"""

SAMPLE_MALFORMED_SOURCE = """as-block:       AS2043 - AS2043
descr:          RIPE NCC ASN block
remarks:        These AS Numbers are assigned to network operators in the RIPE NCC service region.
tech-c:         DUMY-RIPE
admin-c:        DUMY-RIPE
mnt-by:         RIPE-NCC-HM-MNT
source:         +FOO$$$
changed:        2001-09-22T09:34:04Z
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

object_sample_mapping = {
    "as-block": SAMPLE_AS_BLOCK,
    "as-set": SAMPLE_AS_SET,
    "aut-num": SAMPLE_AUT_NUM,
    "domain": SAMPLE_DOMAIN,
    "filter-set": SAMPLE_FILTER_SET,
    "inet-rtr": SAMPLE_INET_RTR,
    "inet6num": SAMPLE_INET6NUM,
    "inetnum": SAMPLE_INETNUM,
    "key-cert": SAMPLE_KEY_CERT,
    "mntner": SAMPLE_MNTNER,
    "peering-set": SAMPLE_PEERING_SET,
    "person": SAMPLE_PERSON,
    "role": SAMPLE_ROLE,
    "route": SAMPLE_ROUTE,
    "route-set": SAMPLE_ROUTE_SET,
    "route6": SAMPLE_ROUTE6,
    "rtr-set": SAMPLE_RTR_SET,
}

TEMPLATE_ROUTE_OBJECT = """route:          [mandatory]  [single]    [primary/look-up key]
descr:          [optional]   [multiple]  []
origin:         [mandatory]  [single]    [primary key]
holes:          [optional]   [multiple]  []
member-of:      [optional]   [multiple]  [look-up key]
inject:         [optional]   [multiple]  []
aggr-bndry:     [optional]   [single]    []
aggr-mtd:       [optional]   [single]    []
export-comps:   [optional]   [single]    []
components:     [optional]   [single]    []
admin-c:        [optional]   [multiple]  [look-up key]
tech-c:         [optional]   [multiple]  [look-up key]
geoidx:         [optional]   [multiple]  []
roa-uri:        [optional]   [single]    []
remarks:        [optional]   [multiple]  []
notify:         [optional]   [multiple]  []
mnt-by:         [mandatory]  [multiple]  [look-up key]
changed:        [mandatory]  [multiple]  []
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
mnt-by:    [mandatory]  [multiple]  [look-up key]
changed:   [mandatory]  [multiple]  []
source:    [mandatory]  [single]    []
"""

# The object samples above were originally generated from a 2018 RIPE split db dump, with the shell one-liner:
# for i in as-block as-set aut-num domain filter-set inet-rtr inet6num inetnum key-cert mntner peering-set person role route route-set route6 rtr-set; do label="SAMPLE_"`echo $i|sed -e "s/-/_/"|tr "[:lower:]" "[:upper:]"`; echo -n "$label = \"\"\""; head -n 10000 ripe.db.$i|egrep -v "^#"|tail -n +2|sed -e "/^$/,$d; "; echo -e """""\n"; done | tr -cd "\11\12\15\40-\176"
# Subsequently, they were modified to match IRRDs expected format in attribute names,
# and some variation was introduced to test obscure parts of the syntax.
