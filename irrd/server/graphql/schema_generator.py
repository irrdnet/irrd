from collections import OrderedDict, defaultdict
from typing import Optional, Dict, Tuple, List

import ariadne

from irrd.rpki.status import RPKIStatus
from irrd.rpsl.fields import RPSLFieldListMixin, RPSLTextField, RPSLReferenceField
from irrd.rpsl.rpsl_objects import (lookup_field_names, OBJECT_CLASS_MAPPING, RPSLAutNum,
                                    RPSLInetRtr, RPSLPerson, RPSLRole)
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.text import snake_to_camel_case


class SchemaGenerator:
    def __init__(self):
        """
        The schema generator generates a GraphQL schema.
        The purpose is to provide a schema to which resolvers are then
        attached, which is then given to Ariadne, and for resolvers to
        have information about expected types.

        For RPSL queries and types, this is dynamically generated based on
        the RPSL objects from irrd.rpsl. Other parts are fixed.
        This means that the schema is always the same for a given IRRd
        codebase - there are no runtime or user configurable parts.

        Along with generating the schema, some metadata is saved, e.g.
        self.graphql_types which allows resolvers to learn the GraphQL
        type for a certain field.

        This generator also creates Ariadne object types on self, which
        are used to attach resolvers to them.
        """
        self._set_rpsl_query_fields()
        self._set_rpsl_object_interface_schema()
        self._set_rpsl_contact_schema()
        self._set_rpsl_object_schemas()
        self._set_enums()

        schema = self.enums
        schema += """
            scalar ASN
            scalar IP

            schema {
              query: Query
            }

            type Query {
              rpslObjects(""" + self.rpsl_query_fields + """): [RPSLObject!]
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
        """
        schema += self.rpsl_object_interface_schema
        schema += self.rpsl_contact_schema
        schema += ''.join(self.rpsl_object_schemas.values())
        schema += 'union RPSLContactUnion = RPSLPerson | RPSLRole'

        self.type_defs = ariadne.gql(schema)

        self.query_type = ariadne.QueryType()
        self.rpsl_object_type = ariadne.InterfaceType("RPSLObject")
        self.rpsl_contact_union_type = ariadne.UnionType("RPSLContactUnion")
        self.asn_scalar_type = ariadne.ScalarType("ASN")
        self.ip_scalar_type = ariadne.ScalarType("IP")
        self.object_types = [self.query_type, self.rpsl_object_type, self.rpsl_contact_union_type,
                             self.asn_scalar_type, self.ip_scalar_type]

        for name in self.rpsl_object_schemas.keys():
            self.object_types.append(ariadne.ObjectType(name))

        self.object_types.append(ariadne.ObjectType("ASNPrefixes"))
        self.object_types.append(ariadne.ObjectType("AsSetPrefixes"))
        self.object_types.append(ariadne.ObjectType("SetMembers"))
        self.object_types.append(ariadne.EnumType("RPKIStatus", RPKIStatus))
        self.object_types.append(ariadne.EnumType("ScopeFilterStatus", ScopeFilterStatus))

    def _set_rpsl_query_fields(self):
        """
        Create a sub-schema for the fields that can be queried for RPSL objects.
        This includes all fields from all objects, along with a few
        special fields.
        """
        string_list_fields = {'rpsl_pk', 'sources', 'object_class'}.union(lookup_field_names())
        params = [snake_to_camel_case(p) + ': [String!]' for p in sorted(string_list_fields)]
        params += [
            'ipExact: IP',
            'ipLessSpecific: IP',
            'ipLessSpecificOneLevel: IP',
            'ipMoreSpecific: IP',
            'ipAny: IP',
            'asn: [ASN!]',
            'rpkiStatus: [RPKIStatus!]',
            'scopeFilterStatus: [ScopeFilterStatus!]',
            'textSearch: String',
            'recordLimit: Int',
            'sqlTrace: Boolean',
        ]
        self.rpsl_query_fields = ', '.join(params)

    def _set_enums(self):
        """
        Create the schema for enums, current RPKI and scope filter status.
        """
        self.enums = ''
        for enum in [RPKIStatus, ScopeFilterStatus]:
            self.enums += f'enum {enum.__name__} {{\n'
            for value in enum:
                self.enums += f'    {value.name}\n'
            self.enums += '}\n\n'

    def _set_rpsl_object_interface_schema(self):
        """
        Create the schema for RPSLObject, which contains only fields that
        are common to every known RPSL object, along with meta
        """
        common_fields = None
        for rpsl_object_class in OBJECT_CLASS_MAPPING.values():
            if common_fields is None:
                common_fields = set(rpsl_object_class.fields.keys())
            else:
                common_fields = common_fields.intersection(set(rpsl_object_class.fields.keys()))
        common_fields = list(common_fields)
        common_fields = ['rpslPk', 'objectClass', 'objectText', 'updated'] + common_fields
        common_field_dict = self._dict_for_common_fields(common_fields)
        common_field_dict['journal'] = '[RPSLJournalEntry]'
        schema = self._generate_schema_str('RPSLObject', 'interface', common_field_dict)
        self.rpsl_object_interface_schema = schema

    def _set_rpsl_contact_schema(self):
        """
        Create the schema for RPSLContact. This contains shared fields between
        RPSLPerson and RPSLRole, as they are so similar.
        """
        common_fields = set(RPSLPerson.fields.keys()).intersection(set(RPSLRole.fields.keys()))
        common_fields = common_fields.union({'rpslPk', 'objectClass', 'objectText', 'updated'})
        common_field_dict = self._dict_for_common_fields(list(common_fields))
        schema = self._generate_schema_str('RPSLContact', 'interface', common_field_dict)
        self.rpsl_contact_schema = schema

    def _dict_for_common_fields(self, common_fields: List[str]):
        common_field_dict = OrderedDict()
        for field_name in sorted(common_fields):
            try:
                # These fields are present in all relevant object, so this is a safe check
                rpsl_field = RPSLPerson.fields[field_name]
                graphql_type = self._graphql_type_for_rpsl_field(rpsl_field)

                reference_name, reference_type = self._grapql_type_for_reference_field(
                    field_name, rpsl_field)
                if reference_name and reference_type:
                    common_field_dict[reference_name] = reference_type
            except KeyError:
                graphql_type = 'String'
            common_field_dict[snake_to_camel_case(field_name)] = graphql_type
        return common_field_dict

    def _set_rpsl_object_schemas(self):
        """
        Create the schemas for each specific RPSL object class.
        Each of these implements RPSLObject, and RPSLPerson/RPSLRole
        implement RPSLContact as well.
        """
        self.graphql_types = defaultdict(dict)
        schemas = OrderedDict()
        for object_class, klass in OBJECT_CLASS_MAPPING.items():
            object_name = klass.__name__
            graphql_fields = OrderedDict()
            graphql_fields['rpslPk'] = 'String'
            graphql_fields['objectClass'] = 'String'
            graphql_fields['objectText'] = 'String'
            graphql_fields['updated'] = 'String'
            graphql_fields['journal'] = '[RPSLJournalEntry]'
            for field_name, field in klass.fields.items():
                graphql_type = self._graphql_type_for_rpsl_field(field)
                graphql_fields[snake_to_camel_case(field_name)] = graphql_type
                self.graphql_types[snake_to_camel_case(object_name)][field_name] = graphql_type

                reference_name, reference_type = self._grapql_type_for_reference_field(field_name, field)
                if reference_name and reference_type:
                    graphql_fields[reference_name] = reference_type
                    self.graphql_types[object_name][reference_name] = reference_type

            for field_name in klass.field_extracts:
                if field_name.startswith('asn'):
                    graphql_type = 'ASN'
                elif field_name == 'prefix':
                    graphql_type = 'IP'
                elif field_name == 'prefix_length':
                    graphql_type = 'Int'
                else:
                    graphql_type = 'String'
                graphql_fields[snake_to_camel_case(field_name)] = graphql_type
            if klass.rpki_relevant:
                graphql_fields['rpkiStatus'] = 'RPKIStatus'
                graphql_fields['rpkiMaxLength'] = 'Int'
                self.graphql_types[object_name]['rpki_max_length'] = 'Int'
            implements = 'RPSLContact & RPSLObject' if klass in [RPSLPerson, RPSLRole] else 'RPSLObject'
            schema = self._generate_schema_str(object_name, 'type', graphql_fields, implements)
            schemas[object_name] = schema
        self.rpsl_object_schemas = schemas

    def _graphql_type_for_rpsl_field(self, field: RPSLTextField) -> str:
        """
        Return the GraphQL type for a regular RPSL field.
        This is always a list of strings if the field is a list and/or
        can occur multiple times.
        """
        if RPSLFieldListMixin in field.__class__.__bases__ or field.multiple:
            return '[String!]'
        return 'String'

    def _grapql_type_for_reference_field(self, field_name: str, rpsl_field: RPSLTextField) -> Tuple[Optional[str], Optional[str]]:
        """
        Return the GraphQL name and type for a reference field.
        For example, for a field "admin-c" that refers to person/role,
        returns ('adminC', '[RPSLContactUnion!]').
        Some fields are excluded because they are syntactical references,
        not real references.
        """
        if isinstance(rpsl_field, RPSLReferenceField) and getattr(rpsl_field, 'referring', None):
            rpsl_field.resolve_references()
            graphql_name = snake_to_camel_case(field_name) + 'Objs'
            grapql_referring = set(rpsl_field.referring_object_classes)
            if RPSLAutNum in grapql_referring:
                grapql_referring.remove(RPSLAutNum)
            if RPSLInetRtr in grapql_referring:
                grapql_referring.remove(RPSLInetRtr)
            if grapql_referring == {RPSLPerson, RPSLRole}:
                graphql_type = '[RPSLContactUnion!]'
            else:
                graphql_type = '[' + grapql_referring.pop().__name__ + '!]'
            return graphql_name, graphql_type
        return None, None

    def _generate_schema_str(self, name: str, graphql_type: str, fields: Dict[str, str], implements: Optional[str]=None) -> str:
        """
        Generate a schema string for a given name, object type and dict of fields.
        """
        schema = f'{graphql_type} {name} '
        if implements:
            schema += f'implements {implements} '
        schema += '{\n'

        for field, field_type in fields.items():
            schema += f'  {field}: {field_type}\n'
        schema += '}\n\n'
        return schema
