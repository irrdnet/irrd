# In addition to these settings, simple
# defaults are stored in default_config.yaml.
import os

from irrd import __version__

DEFAULT_SOURCE_NRTM_PORT = "43"
DEFAULT_SOURCE_IMPORT_TIMER = 300
DEFAULT_SOURCE_EXPORT_TIMER_NRTM4 = 60 if not os.environ.get("IRRD_TESTING_FAST_SCHEDULER_OVERRIDE") else 0
DEFAULT_SOURCE_IMPORT_TIMER_NRTM4 = 60 if not os.environ.get("IRRD_TESTING_FAST_SCHEDULER_OVERRIDE") else 0
DEFAULT_SOURCE_EXPORT_TIMER = 3600
DEFAULT_SOURCE_NRTM4_SERVER_SNAPSHOT_FREQUENCY = 3600 * 4
HTTP_USER_AGENT = f"irrd/{__version__}"
