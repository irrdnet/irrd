import logging
from IPy import IP

from irrd.conf import get_setting

logger = logging.getLogger(__name__)


def is_client_permitted(ip: str, access_list_setting: str, default_deny=True, log=True) -> bool:
    """
    Determine whether a client is permitted to access an interface,
    based on the value of the setting of access_list_setting.
    If default_deny is True, an unset or empty access list will lead to denial.

    IPv6-mapped IPv4 addresses are unmapped to regular IPv4 addresses before processing.
    """
    try:
        client_ip = IP(ip)
    except (ValueError, AttributeError) as e:
        if log:
            logger.error(f'Rejecting request as client IP could not be read from '
                         f'{ip}: {e}')
        return False

    if client_ip.version() == 6:
        try:
            client_ip = client_ip.v46map()
        except ValueError:
            pass

    access_list_name = get_setting(access_list_setting)
    access_list = get_setting(f'access_lists.{access_list_name}')

    if not access_list_name or not access_list:
        if default_deny:
            if log:
                logger.info(f'Rejecting request, access list empty or undefined: {client_ip}')
            return False
        else:
            return True

    allowed = any([client_ip in IP(allowed) for allowed in access_list])
    if not allowed and log:
        logger.info(f'Rejecting request, IP not in access list {access_list_name}: {client_ip}')
    return allowed
