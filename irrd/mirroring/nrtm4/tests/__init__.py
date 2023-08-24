import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

MOCK_UNF_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(
    b"\x15\xa9Wr\x1b<\x1c\x856\xd8G\xdc\xde*Ms\x15pc\x00~2\x9d1\xf50\x8c\xf4\x11m\x8a\r"
)
MOCK_UNF_PUBLIC_KEY = base64.b64encode(MOCK_UNF_PRIVATE_KEY.public_key().public_bytes_raw()).decode("ascii")

MOCK_UNF_PRIVATE_KEY_OTHER = Ed25519PrivateKey.from_private_bytes(
    b"\xe1\x80\xe0izQ\x0c\x85<\xbc\x96\xc5a\xe6 =\n\x84k\x86\x00tw\x91\x17[:H\xb7W\n\xc1"
)
MOCK_UNF_PUBLIC_KEY_OTHER = base64.b64encode(
    MOCK_UNF_PRIVATE_KEY_OTHER.public_key().public_bytes_raw()
).decode("ascii")
