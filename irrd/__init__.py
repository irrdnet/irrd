# Note that version is also in pyproject.toml
__version__ = "4.6-dev"
ENV_MAIN_PROCESS_PID = "IRRD_MAIN_PROCESS_PID"
ENV_MAIN_STARTUP_TIME = "IRRD_MAIN_STARTUP_TIME"
META_KEY_HTTP_CLIENT_IP = "HTTP-Client-IP"
# Metadata keys IRRD fills itself, not accepted from a client
META_KEYS_INTERNAL = [
    META_KEY_HTTP_CLIENT_IP,
    "From",
    "HTTP-User-Agent",
    "HTTP-User-Email",
    "HTTP-User-ID",
    "Message-ID",
    "Date",
    "Subject",
]
