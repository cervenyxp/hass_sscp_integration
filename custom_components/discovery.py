import asyncio
import json
import logging
from hashlib import md5

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 6.0