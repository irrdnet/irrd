from typing import Any
import os

DEFAULT_SETTINGS = {
    'database_url': 'postgresql:///irrd',
}


def get_setting(setting_name: str) -> Any:
    default = DEFAULT_SETTINGS.get(setting_name)
    env_key = 'IRRD_' + setting_name.upper()
    if env_key in os.environ:
        return os.environ[env_key]
    return default
