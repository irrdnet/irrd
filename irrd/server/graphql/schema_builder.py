from IPy import IP
from ariadne import make_executable_schema
from asgiref.sync import sync_to_async as sta
from graphql import GraphQLError

from .resolvers import (resolve_rpsl_objects, resolve_rpsl_object_type,
                        resolve_database_status, resolve_rpsl_object_mnt_by_objs,
                        resolve_rpsl_object_member_of_objs, resolve_rpsl_object_members_by_ref_objs,
                        resolve_rpsl_object_members_objs, resolve_rpsl_object_adminc_objs,
                        resolve_asn_prefixes, resolve_as_set_prefixes,
                        resolve_recursive_set_members, resolve_rpsl_object_techc_objs,
                        resolve_rpsl_object_journal)
from .schema_generator import SchemaGenerator
from ...utils.text import clean_ip_value_error


def build_executable_schema():
    """
    Build an executable schema.
    This takes the schema from the schema generator, and attaches
    the resolvers for each field. It also sets up custom parsing
    for IP and ASN input fields.
    """
    schema = SchemaGenerator()

    schema.rpsl_object_type.set_type_resolver(sta(resolve_rpsl_object_type, False))
    schema.rpsl_contact_union_type.set_type_resolver(sta(resolve_rpsl_object_type, False))

    schema.query_type.set_field("rpslObjects", sta(resolve_rpsl_objects, False))
    schema.query_type.set_field("databaseStatus", sta(resolve_database_status, False))
    schema.query_type.set_field("asnPrefixes", sta(resolve_asn_prefixes, False))
    schema.query_type.set_field("asSetPrefixes", sta(resolve_as_set_prefixes, False))
    schema.query_type.set_field("recursiveSetMembers", sta(resolve_recursive_set_members, False))

    schema.rpsl_object_type.set_field("mntByObjs", sta(resolve_rpsl_object_mnt_by_objs, False))
    schema.rpsl_object_type.set_field("journal", sta(resolve_rpsl_object_journal, False))
    for object_type in schema.object_types:
        if 'adminCObjs' in schema.graphql_types[object_type.name]:
            object_type.set_field("adminCObjs", sta(resolve_rpsl_object_adminc_objs, False))
    for object_type in schema.object_types:
        if 'techCObjs' in schema.graphql_types[object_type.name]:
            object_type.set_field("techCObjs", sta(resolve_rpsl_object_techc_objs, False))
    for object_type in schema.object_types:
        if 'mbrsByRefObjs' in schema.graphql_types[object_type.name]:
            object_type.set_field("mbrsByRefObjs", sta(resolve_rpsl_object_members_by_ref_objs, False))
    for object_type in schema.object_types:
        if 'memberOfObjs' in schema.graphql_types[object_type.name]:
            object_type.set_field("memberOfObjs", sta(resolve_rpsl_object_member_of_objs, False))
    for object_type in schema.object_types:
        if 'membersObjs' in schema.graphql_types[object_type.name]:
            object_type.set_field("membersObjs", sta(resolve_rpsl_object_members_objs, False))

    @schema.asn_scalar_type.value_parser
    def parse_asn_scalar(value):
        try:
            return int(value)
        except ValueError:
            raise GraphQLError(f'Invalid ASN: {value}; must be numeric')

    @schema.ip_scalar_type.value_parser
    def parse_ip_scalar(value):
        try:
            return IP(value)
        except ValueError as ve:
            raise GraphQLError(f'Invalid IP: {value}: {clean_ip_value_error(ve)}')

    return make_executable_schema(schema.type_defs, *schema.object_types)
