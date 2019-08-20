import logging
import os
import re
from tempfile import NamedTemporaryFile
from typing import Optional, Tuple

import gnupg

from irrd.conf import get_setting

logger = logging.getLogger(__name__)
pgp_inline_re = re.compile(r'-----BEGIN PGP SIGNED MESSAGE-----(\n.+)?\n\n((?s:.+))\n-----BEGIN PGP SIGNATURE-----\n',
                           flags=re.MULTILINE)


def get_gpg_instance() -> gnupg.GPG:
    keyring = get_setting('auth.gnupg_keyring')
    if not os.path.exists(keyring):
        os.mkdir(keyring)
    return gnupg.GPG(gnupghome=keyring)


def validate_pgp_signature(message: str, detached_signature: Optional[str]=None) -> Tuple[Optional[str], Optional[str]]:
    """
    Verify a PGP signature in a message.

    If there is a valid signature, returns a tuple of an optional signed message
    part, and the PGP fingerprint, or None,None if there was no (valid) signature.
    The signed message part is relevant for inline signing, where only part of
    the message may be signed. If it is None, the entire message was signed.

    If detached_signature is set, it is expected to contain a PGP signature block
    that was used to sign message (for PGP/MIME signatures).
    For PGP/MIME, note that message should include the entire text/plain part
    of the signed message, including content-type headers.

    If there is a single PGP inline signed message in message, this message
    will be validated, and the signed part of the message is returned.
    If there are multiple inline PGP signed messages, this function returns
    None,None.

    Note that PGP validation is dependent on the PGP key already being in the
    keychain contained in the auth.gnupg_keyring setting. This is usually done by
    importing a key-cert, which will add the certificate to the keychain during
    validation, in RPSLKeyCert.clean().
    """
    gpg = get_gpg_instance()

    new_message = None
    if detached_signature:
        with NamedTemporaryFile() as data_file:
            data_file.write(message.encode(gpg.encoding))
            data_file.flush()
            result = gpg.verify(detached_signature, data_filename=data_file.name)

    elif message.count('BEGIN PGP SIGNED MESSAGE') == 1:
        result = gpg.verify(message)
        match = pgp_inline_re.search(message.replace('\r\n', '\n').replace('\r', '\n'))
        if not match:  # pragma: no cover
            msg = f'message contained an inline PGP signature, but regular expression failed to extract body: {message}'
            logger.info(msg)
            return None, None
        new_message = match.group(2) + '\n'

    else:
        return None, None

    log_message = result.stderr.replace('\n', ' -- ').replace('gpg:                ', '')
    logger.info(f'checked PGP signature, response: {log_message}')
    if result.valid and result.key_status is None:
        logger.info(f'Found valid PGP signature, fingerprint {result.fingerprint}')
        return new_message, result.fingerprint
    return None, None
