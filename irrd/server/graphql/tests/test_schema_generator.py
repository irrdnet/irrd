from ..schema_generator import SchemaGenerator


def test_schema_generator():
    # This test will need updating if changes are made to RPSL types.
    generator = SchemaGenerator()
    assert generator.graphql_types["RPSLAsBlock"]["descr"] == "[String!]"
    assert generator.graphql_types["RPSLAsBlock"]["techCObjs"] == "[RPSLContactUnion!]"
    assert generator.graphql_types["RPSLRtrSet"]["rtr-set"] == "String"
    assert (
        generator.type_defs
        == """enum RPKIStatus {
    valid
    invalid
    not_found
}

enum ScopeFilterStatus {
    in_scope
    out_scope_as
    out_scope_prefix
}

enum RoutePreferenceStatus {
    visible
    suppressed
}


            scalar ASN
            scalar IP

            schema {
              query: Query
            }

            type Query {
              rpslObjects(adminC: [String!], mbrsByRef: [String!], memberOf: [String!], members: [String!], mntBy: [String!], mpMembers: [String!], objectClass: [String!], origin: [String!], person: [String!], role: [String!], rpslPk: [String!], sources: [String!], techC: [String!], zoneC: [String!], ipExact: IP, ipLessSpecific: IP, ipLessSpecificOneLevel: IP, ipMoreSpecific: IP, ipAny: IP, asn: [ASN!], rpkiStatus: [RPKIStatus!], scopeFilterStatus: [ScopeFilterStatus!], routePreferenceStatus: [RoutePreferenceStatus!], textSearch: String, recordLimit: Int, sqlTrace: Boolean): [RPSLObject!]
              databaseStatus(sources: [String!]): [DatabaseStatus]
              asnPrefixes(asns: [ASN!]!, ipVersion: Int, sources: [String!]): [ASNPrefixes!]
              asSetPrefixes(setNames: [String!]!, ipVersion: Int, sources: [String!], excludeSets: [String!], sqlTrace: Boolean): [AsSetPrefixes!]
              recursiveSetMembers(setNames: [String!]!, depth: Int, sources: [String!], excludeSets: [String!], sqlTrace: Boolean): [SetMembers!]
            }

            type DatabaseStatus {
                source: String!
                authoritative: Boolean!
                objectClassFilter: [String!]
                rpkiRovFilter: Boolean!
                scopefilterEnabled: Boolean!
                routePreference: Int
                localJournalKept: Boolean!
                serialOldestJournal: Int
                serialNewestJournal: Int
                serialLastExport: Int
                serialNewestMirror: Int
                lastUpdate: String
                synchronisedSerials: Boolean!
            }

            type RPSLJournalEntry {
                rpslPk: String!
                source: String!
                serialNrtm: Int!
                operation: String!
                origin: String
                objectClass: String!
                objectText: String!
                timestamp: String!
            }

            type ASNPrefixes {
                asn: ASN!
                prefixes: [IP!]
            }

            type AsSetPrefixes {
                rpslPk: String!
                prefixes: [IP!]
            }

            type SetMembers {
                rpslPk: String!
                rootSource: String!
                members: [String!]
            }
        interface RPSLObject {
  changed: [String!]
  mntByObjs: [RPSLMntner!]
  mntBy: [String!]
  notify: [String!]
  objectClass: String
  objectText: String
  remarks: [String!]
  rpslPk: String
  source: String
  updated: String
  journal: [RPSLJournalEntry]
}

interface RPSLContact {
  address: [String!]
  changed: [String!]
  eMail: [String!]
  faxNo: [String!]
  mntByObjs: [RPSLMntner!]
  mntBy: [String!]
  nicHdl: String
  notify: [String!]
  objectClass: String
  objectText: String
  phone: [String!]
  remarks: [String!]
  rpslPk: String
  source: String
  updated: String
}

type RPSLAsBlock implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  asBlock: String
  descr: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
  asnFirst: ASN
  asnLast: ASN
}

type RPSLAsSet implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  asSet: String
  descr: [String!]
  members: [String!]
  membersObjs: [RPSLAsSet!]
  mbrsByRef: [String!]
  mbrsByRefObjs: [RPSLMntner!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLAutNum implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  autNum: String
  asName: String
  descr: [String!]
  memberOf: [String!]
  memberOfObjs: [RPSLAsSet!]
  import: [String!]
  mpImport: [String!]
  importVia: [String!]
  export: [String!]
  mpExport: [String!]
  exportVia: [String!]
  default: [String!]
  mpDefault: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
  asn: ASN
}

type RPSLDomain implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  domain: String
  descr: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  zoneC: [String!]
  zoneCObjs: [RPSLContactUnion!]
  nserver: [String!]
  subDom: [String!]
  domNet: [String!]
  refer: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLFilterSet implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  filterSet: String
  descr: [String!]
  filter: String
  mpFilter: String
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLInetRtr implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  inetRtr: String
  descr: [String!]
  alias: [String!]
  localAs: String
  ifaddr: [String!]
  interface: [String!]
  peer: [String!]
  mpPeer: [String!]
  memberOf: [String!]
  memberOfObjs: [RPSLRtrSet!]
  rsIn: String
  rsOut: String
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLInet6Num implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  inet6num: String
  netname: String
  descr: [String!]
  country: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  revSrv: [String!]
  status: String
  geofeed: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
  ipFirst: String
  ipLast: String
  prefix: IP
  prefixLength: Int
}

type RPSLInetnum implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  inetnum: String
  netname: String
  descr: [String!]
  country: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  revSrv: [String!]
  status: String
  geofeed: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
  ipFirst: String
  ipLast: String
}

type RPSLKeyCert implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  keyCert: String
  method: String
  owner: [String!]
  fingerpr: String
  certif: [String!]
  remarks: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLMntner implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  mntner: String
  descr: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  updTo: [String!]
  mntNfy: [String!]
  auth: [String!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLPeeringSet implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  peeringSet: String
  descr: [String!]
  peering: [String!]
  mpPeering: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLPerson implements RPSLContact & RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  person: String
  address: [String!]
  phone: [String!]
  faxNo: [String!]
  eMail: [String!]
  nicHdl: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLRole implements RPSLContact & RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  role: String
  trouble: [String!]
  address: [String!]
  phone: [String!]
  faxNo: [String!]
  eMail: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  nicHdl: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLRoute implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  route: String
  descr: [String!]
  origin: String
  holes: [String!]
  memberOf: [String!]
  memberOfObjs: [RPSLRouteSet!]
  inject: [String!]
  aggrBndry: String
  aggrMtd: String
  exportComps: String
  components: String
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  geoidx: [String!]
  roaUri: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
  ipFirst: String
  ipLast: String
  prefix: IP
  prefixLength: Int
  asn: ASN
  rpkiStatus: RPKIStatus
  rpkiMaxLength: Int
  routePreferenceStatus: RoutePreferenceStatus
}

type RPSLRouteSet implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  routeSet: String
  members: [String!]
  mpMembers: [String!]
  mbrsByRef: [String!]
  mbrsByRefObjs: [RPSLMntner!]
  descr: [String!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

type RPSLRoute6 implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  route6: String
  descr: [String!]
  origin: String
  holes: [String!]
  memberOf: [String!]
  memberOfObjs: [RPSLRouteSet!]
  inject: [String!]
  aggrBndry: String
  aggrMtd: String
  exportComps: String
  components: String
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  geoidx: [String!]
  roaUri: String
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
  ipFirst: String
  ipLast: String
  prefix: IP
  prefixLength: Int
  asn: ASN
  rpkiStatus: RPKIStatus
  rpkiMaxLength: Int
  routePreferenceStatus: RoutePreferenceStatus
}

type RPSLRtrSet implements RPSLObject {
  rpslPk: String
  objectClass: String
  objectText: String
  updated: String
  journal: [RPSLJournalEntry]
  rtrSet: String
  descr: [String!]
  members: [String!]
  membersObjs: [RPSLRtrSet!]
  mpMembers: [String!]
  mpMembersObjs: [RPSLRtrSet!]
  mbrsByRef: [String!]
  mbrsByRefObjs: [RPSLMntner!]
  adminC: [String!]
  adminCObjs: [RPSLContactUnion!]
  techC: [String!]
  techCObjs: [RPSLContactUnion!]
  remarks: [String!]
  notify: [String!]
  mntBy: [String!]
  mntByObjs: [RPSLMntner!]
  changed: [String!]
  source: String
}

union RPSLContactUnion = RPSLPerson | RPSLRole"""
    )
