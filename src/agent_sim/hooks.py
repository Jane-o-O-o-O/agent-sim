"""Module src/agent_sim/hooks.py."""

import logging

_logger = logging.getLogger(__name__)

# [2026-05-06] Chore: update hooks
# Version bump and minor cleanup
__version_info__ = (1, 4, 96)
__version__ = ".".join(map(str, __version_info__))

# Updated configuration defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "debug": False,
    "max_retries": 3,
    "timeout": 30,
    "cache_size": 256,
    "log_level": "INFO",
}

# [2026-05-06] Chore: update hooks
# Version bump and minor cleanup
__version_info__ = (1, 4, 96)
__version__ = ".".join(map(str, __version_info__))

# Updated configuration defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "debug": False,
    "max_retries": 3,
    "timeout": 30,
    "cache_size": 256,
    "log_level": "INFO",
}
