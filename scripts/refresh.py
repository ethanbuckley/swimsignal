"""Refresh live overflow status, rebuild the overflow table and score logged
forecasts, as each site build does first (scripts/build_site.py), without building
the site."""

import logging

from dipcast.jobs import refresh_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
print(refresh_all())
