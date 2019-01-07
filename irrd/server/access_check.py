import logging
from IPy import IP

from irrd.conf import get_setting

logger = logging.getLogger(__name__)


def is_client_permitted(peer, access_list_setting, default_deny=True) -> bool:
    """
    Determine whether a client is permitted to access an interface,
    based on the value of the setting of access_list_setting.
    If default_deny is True, an unset or empty access list will lead to denial.
    """
    try:
        client_ip = IP(peer.host)
    except (ValueError, AttributeError) as e:
        logger.error(f'Rejecting request as client IP could not be read from '
                     f'{peer}: {e}')
        return False

    access_list_name = get_setting(access_list_setting)
    access_list = get_setting(f'access_lists.{access_list_name}')

    if not access_list_name or not access_list:
        if default_deny:
            logger.info(f'Rejecting request, access list empty or undefined: {client_ip}')
            return False
        else:
            return True

    allowed = any([client_ip in IP(allowed) for allowed in access_list])
    if not allowed:
        logger.info(f'Rejecting request, IP not in access list {access_list_name}: {client_ip}')
    return allowed
