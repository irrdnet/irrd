import itertools
import logging
from collections import defaultdict
from typing import Dict, List, Set

from irrd.conf import get_setting
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.parser import RPSLObject
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.email import send_email

logger = logging.getLogger(__name__)


def notify_rpki_invalid_owners(database_handler: DatabaseHandler,
                               rpsl_dicts_now_invalid: List[Dict[str, str]]) -> int:
    """
    Notify the owners/contacts of newly RPKI invalid objects.

    Expects a list of objects, each a dict with their properties.
    Contacts are resolved as any mnt-nfy, or any email address on any
    tech-c or admin-c, of any maintainer of the object.
    One email is sent per email address.
    """
    if not get_setting('rpki.notify_invalid_enabled'):
        return 0

    rpsl_objs = []
    for obj in rpsl_dicts_now_invalid:
        source = obj['source']
        authoritative = get_setting(f'sources.{source}.authoritative')
        if authoritative and obj['rpki_status'] == RPKIStatus.invalid:
            rpsl_objs.append(rpsl_object_from_text(obj['object_text']))

    if not rpsl_objs:
        return 0

    sources = set([obj.parsed_data['source'] for obj in rpsl_objs])
    mntner_emails_by_source = {}
    for source in sources:
        # For each source, a multi-step process is run to fill this
        # dict with the contact emails for each mntner.
        mntner_emails = defaultdict(set)

        # Step 1: retrieve all relevant maintainers from the DB
        mntner_pks = set(itertools.chain(*[
            obj.parsed_data.get('mnt-by', [])
            for obj in rpsl_objs
            if obj.parsed_data['source'] == source
        ]))
        query = RPSLDatabaseQuery(['rpsl_pk', 'parsed_data']).sources([source]).rpsl_pks(mntner_pks).object_classes(['mntner'])
        mntners = list(database_handler.execute_query(query))

        # Step 2: any mnt-nfy on these maintainers is a contact address
        for mntner in mntners:
            mntner_emails[mntner['rpsl_pk']].update(mntner['parsed_data'].get('mnt-nfy', []))

        # Step 3: extract the contact handles for each maintainer
        mntner_contacts = {
            m['rpsl_pk']: m['parsed_data'].get('tech-c', []) + m['parsed_data'].get('admin-c', [])
            for m in mntners
        }

        # Step 4: retrieve all these contacts from the DB in bulk,
        # and extract their e-mail addresses
        contact_pks = set(itertools.chain(*mntner_contacts.values()))
        query = RPSLDatabaseQuery(['rpsl_pk', 'parsed_data']).sources([source]).rpsl_pks(contact_pks).object_classes(['role', 'person'])
        contacts = {
            r['rpsl_pk']: r['parsed_data'].get('e-mail', [])
            for r in database_handler.execute_query(query)
        }

        # Step 5: use the contacts per maintainer, and emails per contact
        # to create a flattened list of emails per maintainer
        for mntner_pk, mntner_contacts in mntner_contacts.items():
            for contact_pk in mntner_contacts:
                try:
                    mntner_emails[mntner_pk].update(contacts[contact_pk])
                except KeyError:
                    pass

        mntner_emails_by_source[source] = mntner_emails

    # With mntners_emails_by_source filled with per source, per maintainer,
    # all relevant emails, categorise the RPSL objects on which email
    # addresses they need to be sent to.
    objs_per_email: Dict[str, Set[RPSLObject]] = defaultdict(set)
    for rpsl_obj in rpsl_objs:
        mntners = rpsl_obj.parsed_data.get('mnt-by', [])
        source = rpsl_obj.parsed_data['source']
        for mntner_pk in mntners:
            try:
                for email in mntner_emails_by_source[source][mntner_pk]:
                    objs_per_email[email].add(rpsl_obj)
            except KeyError:  # pragma: no cover
                pass

    header_template = get_setting('rpki.notify_invalid_header', '')
    subject_template = get_setting('rpki.notify_invalid_subject', '').replace('\n', ' ')
    for email, objs in objs_per_email.items():
        sources_str = ', '.join(set([obj.parsed_data['source'] for obj in objs]))
        subject = subject_template.format(sources_str=sources_str, object_count=len(objs))
        body = header_template.format(sources_str=sources_str, object_count=len(objs))
        body += '\nThe following objects are affected:\n'
        body += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n'
        for rpsl_obj in objs:
            body += rpsl_obj.render_rpsl_text() + '\n'
        body += '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'
        try:
            send_email(email, subject, body)
        except Exception as e:  # pragma: no cover
            logger.warning(f'Unable to send RPKI invalid notification to {email}: {e}')

    return len(objs_per_email.keys())
