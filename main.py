"""
Entry point for the Bloom Filter demo.

Loads or generates 100k users, builds the in-memory filter, and runs Flask.
"""

from __future__ import annotations

import logging

from app import app, bootstrap_bloom_demo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting Bloom Filter demo server…")
    bootstrap_bloom_demo(100_000)
    # use_reloader=False avoids building the 100k-entry filter twice on startup.
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)
