# 🌸 Bloom Filter Demo

> A space-efficient, probabilistic data structure — built to handle 1 lakh users with just 117 KB of memory.

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Memory](https://img.shields.io/badge/Memory-117%20KiB-orange?style=flat-square)
![Users](https://img.shields.io/badge/Users-100k-purple?style=flat-square)

---

## What is this?

This project implements a **Bloom filter** — the same data structure Instagram uses to check username availability and deduplicate seen content at scale — pre-loaded with **1,00,000 randomly generated usernames**.

A Bloom filter keeps a fixed array of `m` bits (all 0 initially). It never stores strings like `"saurabh"` anywhere — only which bits should be `1`. Membership is probabilistic:

- **"Definitely not in the set"** — guaranteed correct
- **"Maybe in the set"** — correct with probability `1 - FPR`

---

## Memory: the key win

| What | Size |
|------|------|
| `users.csv` (100k names on disk) | **975.7 KiB** |
| Bloom filter bit array (in memory) | **117.1 KiB** |

The filter uses **~8× less memory** than the raw data — and stores zero actual names.

---

## How it works

### MurmurHash3 (mmh3)

- **Fast** — critical when inserting or querying millions of keys
- **Well-distributed** — output bits spread evenly, minimising clumps in the bit array
- **Non-cryptographic** — Bloom filters need good mixing, not collision resistance
- **Stable seeds** — same string always maps to the same bit positions (seeds `0` and `1`)

### Double hashing

Instead of maintaining `k` independent hash functions, all `k` positions are derived from just two base hashes `h₁(x)` and `h₂(x)`:

```
hᵢ(x) = ( h₁(x) + i · h₂(x) ) mod m,   for i = 0, 1, …, k − 1
```

`h₂` is always in `[1, m−1]` so the `k` indices never collapse to a single point.

### Optimal sizing formulas

Given `n` keys and desired false-positive rate `p`:

```
m ≈ −(n · ln p) / (ln 2)²      # optimal bit array length
k ≈ (m / n) · ln 2              # optimal number of hash functions
```

With `n = 100,000` and `p = 0.01` (1%):

| Parameter | Value |
|-----------|-------|
| Bit array size `m` | 958,506 bits |
| Hash functions `k` | 7 |
| Target FPR | 1% |
| Estimated FPR (model) | 1.004% |

### False-positive rate after insertion

```
P(false positive) ≈ ( 1 − e^(−k · n_ins / m) )^k
```

As the bit array fills, this probability rises toward the design target.

---

## Walkthrough: adding `saurabh`

```
1. Compute h₁("saurabh") and h₂("saurabh") using mmh3 with seeds 0 and 1
2. Derive 7 bit indices:  hᵢ = (h₁ + i·h₂) mod 958506,  for i in [0..6]
3. Set each of those 7 bits to 1 in the bit array
4. To CHECK: probe the same 7 bits
      → all 1s   = "possibly present" (true positive here)
      → any 0    = "definitely not present"
5. The string "saurabh" is never stored anywhere
```

The live demo runs the same filter pre-loaded with 100k users. Adding `saurabh` shows real hash indices and bit probes in the visualiser.

---

## Project structure

```
bloom-filter-demo/
├── app.py                 # Flask/FastAPI server
├── bloom.py               # Core Bloom filter implementation
├── generate_users.py      # Script to generate 100k random usernames
├── users.csv              # 100k generated usernames (975.7 KiB)
├── static/
│   └── index.html         # Interactive demo UI
└── README.md
```

---

## Installation

```bash
git clone https://github.com/your-username/bloom-filter-demo.git
cd bloom-filter-demo

pip install -r requirements.txt
```

**Requirements:**

```
mmh3
bitarray
flask        # or fastapi + uvicorn
```

---

## Usage

### Run the demo server

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

### Use the Bloom filter directly

```python
from bloom import BloomFilter

bf = BloomFilter(n=100_000, p=0.01)

# Insert
bf.add("saurabh")
bf.add("anamika")

# Check
bf.check("saurabh")   # → True  (definitely or probably present)
bf.check("unknown")   # → False (definitely not present)

# Stats
print(bf.stats())
# {'m': 958506, 'k': 7, 'fpr_estimate': 0.01004, 'memory_kib': 117.1}
```

### Generate a new user dataset

```bash
python generate_users.py --count 100000 --output users.csv
```

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/add` | Add a username to the filter |
| `POST` | `/check` | Check if a username is probably present |
| `GET` | `/stats` | Get filter statistics |
| `GET` | `/bits?limit=200` | Get the first N bits of the array |

---

## Instagram use cases

Instagram uses Bloom filters for:

- **Username availability checks** — quick lookup before hitting the database
- **Seen-content deduplication** — avoid showing the same Reel twice without storing a full history
- **Spam detection** — fast membership tests on known bad actors

---

## Limitations

- **False positives are possible** (~1% with this config). The filter may say a username is taken when it isn't.
- **False negatives are impossible** — if something was added, it will always be found.
- **Deletion is not supported** — standard Bloom filters cannot remove elements. Use a Counting Bloom Filter variant if deletion is needed.
- **FPR grows** as more elements are inserted beyond the design capacity `n`.

---

## License

MIT — see [LICENSE](LICENSE) for details.
