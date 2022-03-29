from collections import OrderedDict
from typing import Set, Dict, Optional, List

import ariadne
import graphql
from IPy import IP
from graphql import GraphQLResolveInfo, GraphQLError

from irrd.conf import get_setting, RPKI_IRR_PSEUDO_SOURCE
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import OBJECT_CLASS_MAPPING, lookup_field_names
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.server.access_check import is_client_permitted
from irrd.storage.queries import RPSLDatabaseQuery, RPSLDatabaseJournalQuery
from irrd.utils.text import snake_to_camel_case, remove_auth_hashes
from .schema_generator import SchemaGenerator
from ..query_resolver import QueryResolver

"""
Resolvers resolve GraphQL queries, usually by translating them
to a database query and then translating the results to an
appropriate format for GraphQL.
"""


schema = SchemaGenerator()
lookup_fields = lookup_field_names()


def resolve_rpsl_object_type(obj: Dict[str, str], *_) -> str:
    """
    Find the GraphQL name for an object given its object class.
    (GraphQL names match RPSL class names.)
    """
    return OBJECT_CLASS_MAPPING[obj.get('objectClass', obj.get('object_class', ''))].__name__


@ariadne.convert_kwargs_to_snake_case
def resolve_rpsl_objects(_, info: GraphQLResolveInfo, **kwargs):
    """
    Resolve a `rpslObjects` query. This query has a considerable
    number of parameters, each of which is applied to an RPSL
    database query.
    """
    low_specificity_kwargs = {
        'object_class', 'rpki_status', 'scope_filter_status', 'sources', 'sql_trace'
    }
    # A query is sufficiently specific if it has other fields than listed above,
    # except that rpki_status is sufficient if it is exclusively selecting on
    # valid or invalid.
    low_specificity = all([
        not (set(kwargs.keys()) - low_specificity_kwargs),
        kwargs.get('rpki_status', []) not in [[RPKIStatus.valid], [RPKIStatus.invalid]],
    ])
    if low_specificity:
        raise ValueError('Your query must be more specific.')

    if kwargs.get('sql_trace'):
        info.context['sql_trace'] = True

    query = RPSLDatabaseQuery(
        column_names=_columns_for_graphql_selection(info),
        ordered_by_sources=False,
        enable_ordering=False
    )

    if 'record_limit' in kwargs:
        query.limit(kwargs['record_limit'])
    if 'rpsl_pk' in kwargs:
        query.rpsl_pks(kwargs['rpsl_pk'])
    if 'object_class' in kwargs:
        query.object_classes(kwargs['object_class'])
    if 'asn' in kwargs:
        query.asns_first(kwargs['asn'])
    if 'text_search' in kwargs:
        query.text_search(kwargs['text_search'])
    if 'rpki_status' in kwargs:
        query.rpki_status(kwargs['rpki_status'])
    else:
        query.rpki_status([RPKIStatus.not_found, RPKIStatus.valid])
    if 'scope_filter_status' in kwargs:
        query.scopefilter_status(kwargs['scope_filter_status'])
    else:
        query.scopefilter_status([ScopeFilterStatus.in_scope])

    all_valid_sources = set(get_setting('sources', {}).keys())
    if get_setting('rpki.roa_source'):
        all_valid_sources.add(RPKI_IRR_PSEUDO_SOURCE)
    sources_default = set(get_setting('sources_default', []))

    if 'sources' in kwargs:
        query.sources(kwargs['sources'])
    elif sources_default and sources_default != all_valid_sources:
        query.sources(list(sources_default))

    # All other parameters are generic lookup fields, like `members`
    for attr, value in kwargs.items():
        attr = attr.replace('_', '-')
        if attr in lookup_fields:
            query.lookup_attrs_in([attr], value)

    ip_filters = [
        'ip_exact', 'ip_less_specific', 'ip_more_specific', 'ip_less_specific_one_level', 'ip_any'
    ]
    for ip_filter in ip_filters:
        if ip_filter in kwargs:
            getattr(query, ip_filter)(IP(kwargs[ip_filter]))

    return _rpsl_db_query_to_graphql_out(query, info)


def resolve_rpsl_object_mnt_by_objs(rpsl_object, info: GraphQLResolveInfo):
    """Resolve mntByObjs on RPSL objects"""
    return _resolve_subquery(rpsl_object, info, ['mntner'], pk_field='mntBy')


def resolve_rpsl_object_adminc_objs(rpsl_object, info: GraphQLResolveInfo):
    """Resolve adminCObjs on RPSL objects"""
    return _resolve_subquery(rpsl_object, info, ['role', 'person'], pk_field='adminC')


def resolve_rpsl_object_techc_objs(rpsl_object, info: GraphQLResolveInfo):
    """Resolve techCObjs on RPSL objects"""
    return _resolve_subquery(rpsl_object, info, ['role', 'person'], pk_field='techC')


def resolve_rpsl_object_members_by_ref_objs(rpsl_object, info: GraphQLResolveInfo):
    """Resolve mbrsByRefObjs on RPSL objects"""
    return _resolve_subquery(rpsl_object, info, ['mntner'], pk_field='mbrsByRef')


def resolve_rpsl_object_member_of_objs(rpsl_object, info: GraphQLResolveInfo):
    """Resolve memberOfObjs on RPSL objects"""
    object_klass = OBJECT_CLASS_MAPPING[rpsl_object['objectClass']]
    sub_object_classes = object_klass.fields['member-of'].referring   # type: ignore
    return _resolve_subquery(rpsl_object, info, sub_object_classes, pk_field='memberOf')


def resolve_rpsl_object_members_objs(rpsl_object, info: GraphQLResolveInfo):
    """Resolve membersObjs on RPSL objects"""
    object_klass = OBJECT_CLASS_MAPPING[rpsl_object['objectClass']]
    sub_object_classes = object_klass.fields['members'].referring   # type: ignore
    # The reference to an aut-num should not be fully resolved, as the
    # reference is very weak.
    if 'aut-num' in sub_object_classes:
        sub_object_classes.remove('aut-num')
    if 'inet-rtr' in sub_object_classes:
        sub_object_classes.remove('inet-rtr')
    return _resolve_subquery(rpsl_object, info, sub_object_classes, 'members', sticky_source=False)


def _resolve_subquery(rpsl_object, info: GraphQLResolveInfo, object_classes: List[str], pk_field: str, sticky_source=True):
    """
    Resolve a subquery, like techCobjs, on an RPSL object, considering
    a number of object classes, extracting the PK from pk_field.
    If sticky_source is set, the referred object must be from the same source.
    """
    pks = rpsl_object.get(pk_field)
    if not pks:
        return []
    if not isinstance(pks, list):
        pks = [pks]
    query = RPSLDatabaseQuery(
        column_names=_columns_for_graphql_selection(info),
        ordered_by_sources=False,
        enable_ordering=False
    )
    query.object_classes(object_classes).rpsl_pks(pks)
    if sticky_source:
        query.sources([rpsl_object['source']])
    return _rpsl_db_query_to_graphql_out(query, info)


def resolve_rpsl_object_journal(rpsl_object, info: GraphQLResolveInfo):
    """
    Resolve a journal subquery on an RPSL object.
    """
    database_handler = info.context['request'].app.state.database_handler
    access_list = f"sources.{rpsl_object['source']}.nrtm_access_list"
    if not is_client_permitted(info.context['request'].client.host, access_list):
        raise GraphQLError(f"Access to journal denied for source {rpsl_object['source']}")

    query = RPSLDatabaseJournalQuery()
    query.sources([rpsl_object['source']]).rpsl_pk(rpsl_object['rpslPk'])
    for row in database_handler.execute_query(query, refresh_on_error=True):
        response = {snake_to_camel_case(k): v for k, v in row.items()}
        response['operation'] = response['operation'].name
        if response['origin']:
            response['origin'] = response['origin'].name
        if response['objectText']:
            response['objectText'] = remove_auth_hashes(response['objectText'])
        yield response


def _rpsl_db_query_to_graphql_out(query: RPSLDatabaseQuery, info: GraphQLResolveInfo):
    """
    Given an RPSL database query, execute it and clean up the output
    to be suitable to return to GraphQL.

    Main changes are:
    - Enum handling
    - Adding the asn and prefix fields if applicable
    - Ensuring the right fields are returned as a list of strings or a string
    """
    database_handler = info.context['request'].app.state.database_handler
    if info.context.get('sql_trace'):
        if 'sql_queries' not in info.context:
            info.context['sql_queries'] = [repr(query)]
        else:
            info.context['sql_queries'].append(repr(query))

    for row in database_handler.execute_query(query, refresh_on_error=True):
        graphql_result = {snake_to_camel_case(k): v for k, v in row.items() if k != 'parsed_data'}
        if 'object_text' in row:
            graphql_result['objectText'] = remove_auth_hashes(row['object_text'])
        if 'rpki_status' in row:
            graphql_result['rpkiStatus'] = row['rpki_status']
        if row.get('ip_first') is not None and row.get('prefix_length'):
            graphql_result['prefix'] = row['ip_first'] + '/' + str(row['prefix_length'])
        if row.get('asn_first') is not None and row.get('asn_first') == row.get('asn_last'):
            graphql_result['asn'] = row['asn_first']

        object_type = resolve_rpsl_object_type(row)
        for key, value in row.get('parsed_data', dict()).items():
            if key == 'auth':
                value = [remove_auth_hashes(v) for v in value]
            graphql_type = schema.graphql_types[object_type][key]
            if graphql_type == 'String' and isinstance(value, list):
                value = '\n'.join(value)
            graphql_result[snake_to_camel_case(key)] = value
        yield graphql_result


@ariadne.convert_kwargs_to_snake_case
def resolve_database_status(_, info: GraphQLResolveInfo, sources: Optional[List[str]]=None):
    """Resolve a databaseStatus query"""
    query_resolver = QueryResolver(
        info.context['request'].app.state.preloader,
        info.context['request'].app.state.database_handler
    )
    for name, data in query_resolver.database_status(sources=sources).items():
        camel_case_data = OrderedDict(data)
        camel_case_data['source'] = name
        for key, value in data.items():
            camel_case_data[snake_to_camel_case(key)] = value
        yield camel_case_data


@ariadne.convert_kwargs_to_snake_case
def resolve_asn_prefixes(_, info: GraphQLResolveInfo, asns: List[int], ip_version: Optional[int]=None, sources: Optional[List[str]]=None):
    """Resolve an asnPrefixes query"""
    query_resolver = QueryResolver(
        info.context['request'].app.state.preloader,
        info.context['request'].app.state.database_handler
    )
    query_resolver.set_query_sources(sources)
    for asn in asns:
        yield dict(
            asn=asn,
            prefixes=list(query_resolver.routes_for_origin(f'AS{asn}', ip_version))
        )


@ariadne.convert_kwargs_to_snake_case
def resolve_as_set_prefixes(_, info: GraphQLResolveInfo, set_names: List[str], sources: Optional[List[str]]=None, ip_version: Optional[int]=None, exclude_sets: Optional[List[str]]=None, sql_trace: bool=False):
    """Resolve an asSetPrefixes query"""
    query_resolver = QueryResolver(
        info.context['request'].app.state.preloader,
        info.context['request'].app.state.database_handler
    )
    if sql_trace:
        query_resolver.enable_sql_trace()
    set_names_set = {i.upper() for i in set_names}
    exclude_sets_set = {i.upper() for i in exclude_sets} if exclude_sets else set()
    query_resolver.set_query_sources(sources)
    for set_name in set_names_set:
        prefixes = list(query_resolver.routes_for_as_set(set_name, ip_version, exclude_sets=exclude_sets_set))
        yield dict(rpslPk=set_name, prefixes=prefixes)
    if sql_trace:
        info.context['sql_queries'] = query_resolver.retrieve_sql_trace()


@ariadne.convert_kwargs_to_snake_case
def resolve_recursive_set_members(_, info: GraphQLResolveInfo, set_names: List[str], depth: int=0, sources: Optional[List[str]]=None, exclude_sets: Optional[List[str]]=None, sql_trace: bool=False):
    """Resolve an recursiveSetMembers query"""
    query_resolver = QueryResolver(
        info.context['request'].app.state.preloader,
        info.context['request'].app.state.database_handler
    )
    if sql_trace:
        query_resolver.enable_sql_trace()
    set_names_set = {i.upper() for i in set_names}
    exclude_sets_set = {i.upper() for i in exclude_sets} if exclude_sets else set()
    query_resolver.set_query_sources(sources)
    for set_name in set_names_set:
        results = query_resolver.members_for_set_per_source(set_name, exclude_sets=exclude_sets_set, depth=depth, recursive=True)
        for source, members in results.items():
            yield dict(rpslPk=set_name, rootSource=source, members=members)
    if sql_trace:
        info.context['sql_queries'] = query_resolver.retrieve_sql_trace()


def _columns_for_graphql_selection(info: GraphQLResolveInfo) -> Set[str]:
    """
    Based on the selected GraphQL fields, determine which database
    columns should be retrieved.
    """
    # Some columns are always retrieved
    columns = {'object_class', 'source', 'parsed_data', 'rpsl_pk'}
    fields = _collect_predicate_names(info.field_nodes[0].selection_set.selections)  # type: ignore
    requested_fields = {ariadne.convert_camel_case_to_snake(f) for f in fields}

    for field in requested_fields:
        if field in RPSLDatabaseQuery().columns:
            columns.add(field)
        if field == 'asn':
            columns.add('asn_first')
            columns.add('asn_last')
        if field == 'prefix':
            columns.add('ip_first')
            columns.add('prefix_length')
    return columns


# https://github.com/mirumee/ariadne/issues/287
def _collect_predicate_names(selections):  # pragma: no cover
    predicates = []
    for selection in selections:
        if isinstance(selection, graphql.InlineFragmentNode):
            predicates.extend(_collect_predicate_names(selection.selection_set.selections))
        else:
            predicates.append(selection.name.value)

    return predicates
