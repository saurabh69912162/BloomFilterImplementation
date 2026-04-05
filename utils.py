"""User generation and persistence for the Bloom filter demo."""

from __future__ import annotations

import csv
import logging
import random
import string
from pathlib import Path

logger = logging.getLogger(__name__)

USERS_CSV = Path(__file__).resolve().parent / "users.csv"
print(USERS_CSV)


def users_csv_size_bytes(path: Path | None = None) -> int | None:
    """Return on-disk byte size of the users CSV if it exists, else None."""
    target = path or USERS_CSV
    if not target.is_file():
        return None
    return int(target.stat().st_size)


def generate_users(n: int = 100_000) -> list[str]:
    """
    Generate n random lowercase usernames (length 6–10) with high uniqueness.

    Uses a set to avoid duplicates; collision rate is negligible at this scale.
    """
    alphabet = string.ascii_lowercase
    seen: set[str] = set()
    while len(seen) < n:
        length = random.randint(6, 10)
        name = "".join(random.choices(alphabet, k=length))
        seen.add(name)
    result = list(seen)
    random.shuffle(result)
    logger.info("Generated %d unique usernames", n)
    return result


def save_users_csv(usernames: list[str], path: Path | None = None) -> None:
    """Write usernames to CSV with a single column: username."""
    target = path or USERS_CSV
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["username"])
        for name in usernames:
            writer.writerow([name])
    logger.info("Wrote %d rows to %s", len(usernames), target)


def load_users_csv(path: Path | None = None) -> list[str]:
    """Load usernames from CSV; returns empty list if file missing or invalid."""
    target = path or USERS_CSV
    if not target.is_file():
        return []
    names: list[str] = []
    with target.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "username" not in reader.fieldnames:
            logger.warning("CSV missing username column: %s", target)
            return []
        for row in reader:
            u = (row.get("username") or "").strip()
            if u:
                names.append(u)
    return names


def load_or_generate_users(
    n: int = 100_000,
    path: Path | None = None,
) -> list[str]:
    """
    Load users from CSV if it has exactly n rows; otherwise generate and save.

    This speeds restarts while keeping the demo reproducible once CSV exists.
    """
    path = path or USERS_CSV
    existing = load_users_csv(path)
    if len(existing) == n:
        logger.info("Loaded %d usernames from %s", n, path)
        return existing
    users = generate_users(n)
    save_users_csv(users, path)
    return users
