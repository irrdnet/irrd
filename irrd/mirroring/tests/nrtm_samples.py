SAMPLE_NRTM_V3 = """
% NRTM v3 contains serials per object.

% Another comment

%START Version: 3 TEST 11012700-11012701

ADD 11012700

person: NRTM test
address: NowhereLand
source: TEST

DEL 11012701

inetnum: 192.0.2.0 - 192.0.2.255
source: TEST

%END TEST
"""

# NRTM v1 has no serials per object
SAMPLE_NRTM_V1 = """%START Version: 1 TEST 11012700-11012701

ADD

person: NRTM test
address: NowhereLand
source: TEST

DEL

inetnum: 192.0.2.0 - 192.0.2.255
source: TEST

%END TEST
"""

SAMPLE_NRTM_V1_TOO_MANY_ITEMS = """
% The serial range is one item, but there are two items in here.

%START Version: 1 TEST 11012700-11012700 FILTERED

ADD

person: NRTM test
address: NowhereLand
source: TEST

DEL

inetnum: 192.0.2.0 - 192.0.2.255
source: TEST

%END TEST
"""
SAMPLE_NRTM_INVALID_VERSION = """%START Version: 99 TEST 11012700-11012700"""

SAMPLE_NRTM_V3_SERIAL_GAP = """
# NRTM v3 serials are allowed to have gaps per https://github.com/irrdnet/irrd/issues/85

%START Version: 3 TEST 11012699-11012703

ADD 11012700

person: NRTM test
address: NowhereLand
source: TEST


DEL 11012701

inetnum: 192.0.2.0 - 192.0.2.255
source: TEST

%END TEST
"""

SAMPLE_NRTM_V3_SERIAL_OUT_OF_ORDER = """
# NRTM v3 serials can have gaps, but must always increase.

%START Version: 3 TEST 11012699-11012703

ADD 11012701

person: NRTM test
address: NowhereLand
source: TEST

DEL 11012701

inetnum: 192.0.2.0 - 192.0.2.255
source: TEST

%END TEST
"""

SAMPLE_NRTM_V3_INVALID_MULTIPLE_START_LINES = """
%START Version: 3 TEST 11012700-11012700

%START Version: 3 ARIN 11012700-11012700

ADD 11012701

person: NRTM test
address: NowhereLand
source: TEST

%END TEST
"""

SAMPLE_NRTM_INVALID_NO_START_LINE = """
ADD 11012701

person: NRTM test
address: NowhereLand
source: TEST

DEL 11012700

inetnum: 192.0.2.0 - 192.0.2.255
source: TEST

%END TEST
"""

SAMPLE_NRTM_V3_NO_END = """%START Version: 3 TEST 11012700-11012701"""
