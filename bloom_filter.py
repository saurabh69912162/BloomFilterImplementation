"""Bloom filter with double hashing (mmh3) and compact bit storage."""

from __future__ import annotations

import logging
import math
import sys
from typing import Any

import mmh3

logger = logging.getLogger(__name__)

try:
    from bitarray import bitarray as _BitArray

    _HAS_BITARRAY = True
except ImportError:
    _HAS_BITARRAY = False
    _BitArray = None  # type: ignore[misc, assignment]
    logger.warning("bitarray not installed; using Python list fallback (more memory)")


def optimal_bit_size_and_k(expected_n: int, false_positive_rate: float) -> tuple[int, int]:
    """
    Compute bit array length m and hash count k for target false positive rate.

    m ≈ -n ln(p) / (ln 2)^2, k ≈ (m/n) ln 2.
    """
    p = false_positive_rate
    n = expected_n
    m = max(1, int(round(-(n * math.log(p)) / (math.log(2) ** 2))))
    k = max(1, int(round((m / n) * math.log(2))))
    return m, k


def estimated_false_positive_rate(m: int, k: int, num_inserted: int) -> float:
    """Approximate FPR after num_inserted items: (1 - e^(-kn/m))^k."""
    if m <= 0 or num_inserted <= 0:
        return 0.0
    fill = math.exp(-k * num_inserted / m)
    return (1.0 - fill) ** k


class BloomFilter:
    """
    Bloom filter using double hashing: h_i(x) = (h1(x) + i * h2(x)) % m.

    h2 is kept in [1, m-1] so steps walk the ring without degenerating.
    """

    def __init__(self, expected_n: int = 100_000, false_positive_rate: float = 0.01) -> None:
        self.expected_n = expected_n
        self.target_fpr = false_positive_rate
        self.m, self.k = optimal_bit_size_and_k(expected_n, false_positive_rate)
        self._bits: Any
        if _HAS_BITARRAY:
            self._bits = _BitArray(self.m)
        else:
            self._bits = [0] * self.m
        logger.debug("BloomFilter m=%d k=%d", self.m, self.k)

    def _get_bit(self, index: int) -> int:
        if _HAS_BITARRAY:
            return int(self._bits[index])
        return int(self._bits[index])

    def _set_bit(self, index: int) -> None:
        if _HAS_BITARRAY:
            self._bits[index] = 1
        else:
            self._bits[index] = 1

    def _h1_h2(self, item: str) -> tuple[int, int]:
        """Primary and secondary hashes in range for double hashing."""
        m = self.m
        # Unsigned 32-bit mix (mmh3 supports signed=False; mask is a safe fallback).
        try:
            u1 = mmh3.hash(item, seed=0, signed=False)
            u2 = mmh3.hash(item, seed=1, signed=False)
        except TypeError:
            u1 = mmh3.hash(item, seed=0) & 0xFFFFFFFF
            u2 = mmh3.hash(item, seed=1) & 0xFFFFFFFF
        h1 = u1 % m
        h2 = (u2 % (m - 1)) + 1 if m > 1 else 1
        return h1, h2

    def get_hash_indices(self, item: str) -> list[int]:
        """Return the k bit positions used for item (for visualization)."""
        h1, h2 = self._h1_h2(item)
        return [(h1 + i * h2) % self.m for i in range(self.k)]

    def get_hash_breakdown(self, item: str) -> dict[str, Any]:
        """Expose h1, h2 and derived indices for the UI."""
        h1, h2 = self._h1_h2(item)
        indices = [(h1 + i * h2) % self.m for i in range(self.k)]
        derived = [{"i": i, "index": indices[i]} for i in range(self.k)]
        return {"h1": h1, "h2": h2, "m": self.m, "k": self.k, "indices": indices, "derived": derived}

    def add(self, item: str) -> dict[str, Any]:
        """
        Insert item. Returns hash indices and positions that flipped 0 → 1.
        """
        indices = self.get_hash_indices(item)
        flipped: list[int] = []
        for idx in indices:
            if self._get_bit(idx) == 0:
                self._set_bit(idx)
                flipped.append(idx)
        return {"hash_indices": indices, "flipped": flipped}

    def check(self, item: str) -> dict[str, Any]:
        """
        Membership probe. Returns possibly present vs definitely not, per-bit state.
        """
        indices = self.get_hash_indices(item)
        bits: list[dict[str, int]] = []
        all_set = True
        for idx in indices:
            val = self._get_bit(idx)
            bits.append({"index": idx, "value": val})
            if val == 0:
                all_set = False
        present = all_set
        return {
            "possibly_present": present,
            "hash_indices": indices,
            "per_bit": bits,
        }

    def snapshot_first_n(self, n: int = 200) -> list[int]:
        """First n bit values (or fewer if m < n) for grid overview."""
        limit = min(n, self.m)
        return [self._get_bit(i) for i in range(limit)]

    def approximate_memory_bytes(self) -> dict[str, Any]:
        """
        Rough in-process size of the bit backing store (sys.getsizeof).

        Excludes other Python objects (e.g. Flask globals); list fallback uses
        far more memory than bitarray for the same m.
        """
        backend = "bitarray" if _HAS_BITARRAY else "python_list"
        return {
            "bit_storage_bytes": int(sys.getsizeof(self._bits)),
            "storage_backend": backend,
        }

    def bits_at_indices(self, indices: list[int]) -> list[dict[str, int]]:
        """Bit values at specific positions (for highlighting)."""
        return [{"index": i, "value": self._get_bit(i)} for i in indices]

    def clear(self) -> None:
        """Reset all bits to zero."""
        if _HAS_BITARRAY:
            self._bits.setall(0)
        else:
            for i in range(self.m):
                self._bits[i] = 0
