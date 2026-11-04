import logging
import sys

from IPy import IP

from irrd.conf import get_setting

STARLETTE_TEST_CLIENT_HOST = "testclient"
MAPPED_IPV4_RANGE = IP("::ffff:0:0/96")

logger = logging.getLogger(__name__)


def rate_limit_host_key(host: str) -> str:
    """
    The key to rate limit a client host by. IPv6 clients are limited per /64,
    as a single client commonly has at least a /64 to rotate through. Mapped
    IPv4 addresses are unmapped first, as they would all share one /64.
    """
    try:
        ip = IP(host)
    except (ValueError, TypeError):
        return host
    if ip.version() == 6:
        return str(ip.v46map()) if ip in MAPPED_IPV4_RANGE else str(ip.make_net(64))
    return str(ip)


def is_client_permitted(ip: str, access_list_setting: str, default_deny=True, log=True) -> bool:
    """
    Determine whether a client is permitted to access an interface,
    based on the value of the setting of access_list_setting.
    If default_deny is True, an unset or empty access list will lead to denial.

    IPv6-mapped IPv4 addresses are unmapped to regular IPv4 addresses before processing.
    """
    bypass_auth = ip == STARLETTE_TEST_CLIENT_HOST and getattr(sys, "_called_from_test")  # type: ignore

    client_ip = None
    if not bypass_auth:
        try:
            client_ip = IP(ip)
        except (ValueError, AttributeError) as e:
            if log:
                logger.error(f"Rejecting request as client IP could not be read from {ip}: {e}")
            return False

    if client_ip and client_ip.version() == 6:
        try:
            client_ip = client_ip.v46map()
        except ValueError:
            pass

    access_list_name = get_setting(access_list_setting)
    access_list = get_setting(f"access_lists.{access_list_name}")

    if not access_list_name or not access_list:
        if default_deny:
            if log:
                logger.info(f"Rejecting request, access list empty or undefined: {client_ip}")
            return False
        else:
            return True

    allowed = bypass_auth or any([client_ip in IP(allowed) for allowed in access_list])
    if not allowed and log:
        logger.info(f"Rejecting request, IP not in access list {access_list_name}: {client_ip}")
    return allowed
