"""Flask API and UI for the Bloom filter interactive demo."""

from __future__ import annotations

import logging
import os
import random
import re
import string
import threading
from typing import Any

from flask import Flask, jsonify, render_template, request

from bloom_filter import BloomFilter, estimated_false_positive_rate
from utils import load_or_generate_users, users_csv_size_bytes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_USERS: list[str] = []
INSERTED: set[str] = set()
BF: BloomFilter | None = None
API_ADD_OPERATIONS: int = 0

_BLOOM_INIT_LOCK = threading.Lock()

_USERNAME_PATTERN = re.compile(r"^[a-z]{1,32}$")


def _validate_username(raw: str) -> tuple[bool, str]:
    name = (raw or "").strip().lower()
    if not name:
        return False, "Username is required."
    if not _USERNAME_PATTERN.match(name):
        return False, "Use 1–32 lowercase letters (a–z) only."
    return True, name


def _viz_payload(bf: BloomFilter, hash_indices: list[int], flipped: list[int] | None = None) -> dict[str, Any]:
    """Bit samples for the UI: overview strip + exact positions used."""
    flipped_set = set(flipped or [])
    first = bf.snapshot_first_n(200)
    cells = []
    for idx in sorted(set(hash_indices)):
        cells.append(
            {
                "index": idx,
                "value": bf.bits_at_indices([idx])[0]["value"],
                "flipped": idx in flipped_set,
            }
        )
    return {
        "first_200_bits": first,
        "hash_cells": cells,
        "m": bf.m,
    }


def _parse_username_from_request() -> str | None:
    data = request.get_json(silent=True)
    if isinstance(data, dict) and "username" in data:
        return data.get("username")
    return request.form.get("username")


def bootstrap_bloom_demo(expected_n: int = 100_000) -> None:
    """
    Load or generate users, persist CSV, build Bloom filter, insert all users.

    Idempotent for a running process; call again only via /reset in this app.
    """
    global BASE_USERS, INSERTED, BF, API_ADD_OPERATIONS
    logger.info("Initializing Bloom demo (n=%s)...", expected_n)
    BASE_USERS = load_or_generate_users(expected_n)
    INSERTED = set(BASE_USERS)
    BF = BloomFilter(expected_n=expected_n, false_positive_rate=0.01)
    BF.clear()
    for name in BASE_USERS:
        BF.add(name)
    API_ADD_OPERATIONS = 0
    logger.info("Ready: %d users in filter, m=%d k=%d", len(BASE_USERS), BF.m, BF.k)


def ensure_bloom_ready() -> None:
    """
    Load the Bloom filter on first use (WSGI deployments do not run main.py).

    Skipped when app.config['TESTING'] is True so unit tests stay fast.
    Size n from env BLOOM_EXPECTED_N (default 100_000).
    """
    global BF
    if BF is not None:
        return
    if app.config.get("TESTING"):
        return
    with _BLOOM_INIT_LOCK:
        if BF is not None:
            return
        n = int(os.environ.get("BLOOM_EXPECTED_N", "100000"))
        bootstrap_bloom_demo(n)


@app.before_request
def _init_bloom_before_request() -> None:
    ensure_bloom_ready()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/learn", endpoint="learn")
def learn_theory():
    """Theory page: mmh3, double hashing, formulas, saurabh walkthrough."""
    return render_template("learn.html")


@app.route("/preview_bits", methods=["GET"])
def preview_bits():
    """Return the first 200 bits for initial UI paint (no query side effects)."""
    if BF is None:
        return jsonify({"error": "Server not initialized"}), 500
    return jsonify({"first_200_bits": BF.snapshot_first_n(200)})


@app.route("/stats", methods=["GET"])
def stats():
    if BF is None:
        return jsonify({"error": "Server not initialized"}), 500
    n_ins = len(INSERTED)
    est = estimated_false_positive_rate(BF.m, BF.k, n_ins)
    mem = BF.approximate_memory_bytes()
    csv_bytes = users_csv_size_bytes()
    return jsonify(
        {
            "total_users_inserted": n_ins,
            "total_keys_in_set": n_ins,
            "api_add_operations": API_ADD_OPERATIONS,
            "bit_array_size_m": BF.m,
            "hash_functions_k": BF.k,
            "target_false_positive_rate": BF.target_fpr,
            "estimated_false_positive_rate": round(est, 6),
            "users_csv_bytes": csv_bytes,
            "bloom_filter_memory_bytes_approx": mem["bit_storage_bytes"],
            "bloom_filter_storage_backend": mem["storage_backend"],
        }
    )


@app.route("/add", methods=["POST"])
def add_username():
    global API_ADD_OPERATIONS
    if BF is None:
        return jsonify({"error": "Server not initialized"}), 500
    raw = _parse_username_from_request()
    ok, msg_or_name = _validate_username(str(raw) if raw is not None else "")
    if not ok:
        return jsonify({"ok": False, "error": msg_or_name}), 400
    name = msg_or_name
    logger.info("Bloom filter ADD: username=%r", name)
    breakdown = BF.get_hash_breakdown(name)
    result = BF.add(name)
    INSERTED.add(name)
    API_ADD_OPERATIONS += 1
    viz = _viz_payload(BF, result["hash_indices"], result["flipped"])
    return jsonify(
        {
            "ok": True,
            "username": name,
            "hash_indices": result["hash_indices"],
            "hash_breakdown": breakdown,
            "flipped_indices": result["flipped"],
            "updated_bit_positions": viz,
        }
    )


@app.route("/check", methods=["POST"])
def check_username():
    if BF is None:
        return jsonify({"error": "Server not initialized"}), 500
    raw = _parse_username_from_request()
    ok, msg_or_name = _validate_username(str(raw) if raw is not None else "")
    if not ok:
        return jsonify({"ok": False, "error": msg_or_name}), 400
    name = msg_or_name
    breakdown = BF.get_hash_breakdown(name)
    probe = BF.check(name)
    verdict = "possibly_present" if probe["possibly_present"] else "definitely_not_present"
    logger.info("Bloom filter CHECK: username=%r verdict=%s", name, verdict)
    label = "Possibly Present" if probe["possibly_present"] else "Definitely Not Present"
    viz = _viz_payload(BF, probe["hash_indices"])
    return jsonify(
        {
            "ok": True,
            "username": name,
            "verdict": verdict,
            "label": label,
            "hash_indices": probe["hash_indices"],
            "hash_breakdown": breakdown,
            "per_bit": probe["per_bit"],
            "check_bits": viz,
        }
    )


@app.route("/simulate", methods=["POST"])
def simulate():
    """Probe random strings that were never inserted; estimate empirical FPR."""
    if BF is None:
        return jsonify({"error": "Server not initialized"}), 500
    trials = 1000
    alphabet = string.ascii_lowercase
    tested = 0
    false_positives = 0
    attempts = 0
    max_attempts = trials * 200
    while tested < trials and attempts < max_attempts:
        attempts += 1
        length = random.randint(6, 10)
        candidate = "".join(random.choices(alphabet, k=length))
        if candidate in INSERTED:
            continue
        tested += 1
        if BF.check(candidate)["possibly_present"]:
            false_positives += 1
    rate = (false_positives / trials) if trials else 0.0
    return jsonify(
        {
            "trials": trials,
            "false_positives": false_positives,
            "empirical_false_positive_rate": round(rate, 4),
            "attempts_drawn": attempts,
        }
    )


@app.route("/reset", methods=["POST"])
def reset():
    bootstrap_bloom_demo(100_000)
    return jsonify({"ok": True, "message": "Rebuilt filter from base user list."})


if __name__ == "__main__":
    bootstrap_bloom_demo()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
