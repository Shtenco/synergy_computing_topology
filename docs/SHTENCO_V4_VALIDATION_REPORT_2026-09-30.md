# SHTENCO V4 — Correctness Closure + Fair Benchmark

Date: 2026-09-30

## Executive result

V4 closes the userspace correctness gates that failed in the previous audit and replaces the old multiplied-estimate methodology with a measured, checksum-verified benchmark.

The strongest measured result is **not an OS-wide 1000× speedup**. It is a workload-specific acceleration for repeated analytical queries over 256-byte records when a compact descriptor index is built once and reused instead of recomputing descriptors from raw bytes for every query.

Across five native benchmark trials with **varied query predicates** and **index-build cost included**, median end-to-end speedup was:

- 1 query: **0.931×**
- 10 queries: **9.451×**
- 100 queries: **97.498×**
- 1000 queries: **899.129×**
- 2000 queries: **1569.058×**
- 3000 queries: **2116.714×**

Thus the measured 1000× threshold is crossed between 1000 and 2000 varied queries in this benchmark configuration. No multiplication of unrelated microbenchmark ratios is used.

## Test environment

- Linux runtime: `6.18.44 x86_64`
- CPU exposed to container: 5 logical CPUs
- GCC: 14.2.0
- Clang: 17.0.0
- Python: 3.13 environment
- NumPy: 2.3.5
- Numba: 0.65.1
- `xxhash` Python package: unavailable in this environment
- `zstandard` Python package: unavailable in this environment
- `lz4`: available
- Kernel headers available for strict module build: `6.12.96+deb13-amd64`

The V4 Python source therefore contains correctness fallbacks: BLAKE2b in place of xxhash and zlib in place of zstandard when those optional packages are absent. Compression performance was **not** presented as native xxhash/zstd performance.

## Gate status

| Gate | Result | Evidence |
|---|---|---|
| BUILD_ALL | **PASS** | Python compile + GCC `-Werror` + Clang `-Werror` + kernel module build |
| LLVM_VERIFY | **PASS** | LLVM IR generated from C reference, compiled back to object and executable by Clang |
| ASAN | **PASS** | Scaled fair benchmark + SQASM C reference |
| UBSAN | **PASS** | Same sanitizer run, halt-on-error |
| BATCH == SEQUENTIAL | **PASS** | 128 random payloads, exact measurement equality; entropy/signal max error 0 |
| BATCH DETERMINISTIC | **PASS** | 5 repeated batch runs identical |
| CACHE DELETE | **PASS** | deleted item no longer revives from L3 |
| CACHE RESTART RECOVERY | **PASS** | mmap index rebuilt from persistent slot headers after reopening |
| NO TAIL LOSS | **PASS** | 1024-byte and 1025-byte inputs produce different accelerator output |
| FRESH PROCESS DECOMPRESS | **PASS** | all 1000 corpora compressed in parent and decompressed in a separate Python process |
| SHA256 | **PASS** | 1000/1000 reconstructed corpora match SHA-256 |
| CORRUPTED ARCHIVE MUST FAIL | **PASS** | corrupted payload rejected by frame/checksum validation |
| Topological archive self-contained | **PASS** | V10 archive reconstructs in fresh process without external dictionary |
| QUERY RESULT SET | **PASS** | 256 varied query templates: raw and indexed `count + checksum` identical |
| EMPTY QUERY GUARD | **PASS** | empty result suppresses speedup instead of reporting infinity |
| INDEX BUILD COST INCLUDED | **PASS** | one-time descriptor/index build is in end-to-end denominator |
| HILBERT vs HASH vs SORTED vs B-TREE vs FLAT | **PASS** | exact lookup benchmark, identical checksum |
| END-TO-END SPEEDUP MEASURED | **PASS** | direct wall-clock timing, varied predicates, no multiplied estimates |
| Kernel runtime on current kernel | **NOT TESTED** | module built for 6.12.96 headers; running kernel is 6.18.44, so vermagic mismatch prevents honest load test |

## Correctness fixes

### 1. QPIPE batch race

The old batch implementation reused one `psi_re/psi_im` scratch pair across `prange` iterations. V4 gives each batch item an independent scratch row and calls the same fused function as the sequential implementation.

Result:

```text
BATCH_EQ_SEQ PASS entropy_max_abs 0.0 signal_max_abs 0.0
BATCH_DETERMINISTIC PASS
```

### 2. Complex Hadamard path

V4 applies FWHT to both real and imaginary components. The previous path transformed only the real component and silently discarded part of the complex-state semantics.

### 3. Qubit cache key

The threshold is now part of the cache key. A result computed with one threshold cannot be reused for another threshold.

Measured check:

```text
CACHE_THRESHOLD_KEY PASS 1 12
```

The same data with thresholds 0.01 and 0.99 produced different hit counts as expected.

### 4. DeepCompress RLE path

V4 adds an actual RLE2 decoder and explicit stream-kind headers. All archive forms now carry a SHA-256 digest inside the compressed envelope.

### 5. Archive-local dictionary

The normal dictionary path no longer depends on process-global state. Each compressed stream contains the blocks required by its reference stream.

### 6. 1000-corpus fresh-process test

The parent process produced 1000 corpora covering zero-filled, repetitive text, random, structured binary and sparse data. A separate fresh Python process decompressed every archive.

```text
FRESH_PROCESS_1000_PASS 1000
SHA256_1000_CORPORA PASS
CORRUPTED_ARCHIVE_REJECT PASS
```

### 7. mmap cache persistence

Each mmap record now stores the key hash in persistent slot metadata. On startup the in-memory index is rebuilt from the mmap slots.

```text
CACHE_RESTART_RECOVERY PASS
CACHE_DELETE PASS
```

### 8. Accelerator tail loss

The fixed four-core input transform now folds every byte of each partition into a 256-byte feature block and mixes a BLAKE2s digest plus input length. A trailing byte can no longer disappear silently.

```text
NO_TAIL_LOSS PASS
max_abs_delta = 0.034541793...
```

### 9. Topological archive V10

The new archive format embeds only the dictionary entries actually referenced by the archive, with an archive-dictionary SHA-256. Missing dictionary references are hard failures, not zero-filled recovery.

Fresh-process tests:

```text
repeat     archive=933 B   fresh process PASS
structured archive=1157 B fresh process PASS
TOPO_V10_SELF_CONTAINED=PASS
```

### 10. LLVM closure

Instead of continuing to patch invalid hand-written LLVM constants one by one, V4 defines the reference implementation in C and uses Clang to emit valid LLVM IR. The emitted IR is then independently compiled back to an executable and object file.

Runtime check:

```text
[QPIPE-V4] meas=128 entropy=2.293130 hash=18212234690957388007
LLVM_VERIFY=PASS
```

Entropy is non-negative and below the 8-bit-state maximum of 8 bits.

### 11. Ring-0 FPU removal

The old kernel source used ordinary floating-point functions and arithmetic inside a Linux kernel module. V4 replaces the Ring-0 computational path with fixed-point arithmetic so the module builds without enabling unsafe kernel FPU/SSE usage.

Strict build:

```text
ccflags-y += -Werror
sqcore_turbo_v4.ko built successfully
version: 4.0
vermagic: 6.12.96+deb13-amd64 ...
```

This is a **build result only**. It is not a runtime result on the current 6.18.44 kernel.

## Fair exact-lookup benchmark

All five methods answer the same exact-key workload. Every method must produce the same checksum before timing is accepted.

Five-trial median latency:

| Method | Median ns/query | Relative to flat |
|---|---:|---:|
| Flat linear scan | 9556.56 | 1.00× |
| Hash table | **29.07** | **328.74×** |
| B-tree | 127.19 | 75.14× |
| Sorted array + binary search | 127.39 | 75.02× |
| Hilbert-sorted + binary search | 178.01 | 53.69× |

Important negative result: **Hilbert is not the fastest exact-lookup structure here. Hash wins clearly, and B-tree/sorted array also beat Hilbert.** This prevents claiming a generic Hilbert lookup advantage.

Build-time medians from the earlier fixed-query trial set were approximately:

- hash: 1.153 ms
- B-tree: 2.870 ms
- sorted array: 3.605 ms
- Hilbert-sorted array: 6.748 ms

## Fair analytical-query benchmark

Data set: 2048 records × 256 bytes.

The baseline recomputes the descriptor from raw bytes on every query. The indexed version computes descriptors once, sorts/buckets them by dominant value, and then answers queries from descriptors.

V4 validates 256 different query templates before timing:

```text
QUERY_RESULT_SET_256=PASS
EMPTY_QUERY_GUARD=PASS
```

Five-trial end-to-end medians with build cost included:

| Number of varied queries | Median speedup |
|---:|---:|
| 1 | 0.931× |
| 10 | 9.451× |
| 100 | 97.498× |
| 1000 | 899.129× |
| 2000 | **1569.058×** |
| 3000 | **2116.714×** |

Ranges across five trials:

- 1000 queries: 526.954× – 1018.294×
- 2000 queries: 971.653× – 1727.924×
- 3000 queries: 1332.362× – 2541.551×

The 2000-query median is above 1000×, but one 2000-query trial was 971.653×. Therefore the strongest defensible statement is:

> On this machine and this 2048-record analytical workload, the precomputed descriptor index crossed 1000× in median end-to-end speedup once the index was amortized across roughly 2000 varied queries; the result is workload-specific and not an OS-wide speedup.

## QPIPE performance after race fix

Median-style single-run benchmark (Numba enabled):

| Batch N | Batch pipe/s | Sequential pipe/s | Batch / sequential |
|---:|---:|---:|---:|
| 1 | 22,388 | 69,023 | 0.324× |
| 8 | 137,000 | 90,659 | 1.511× |
| 64 | 214,414 | 59,564 | 3.600× |
| 256 | 246,300 | 73,459 | 3.353× |
| 1024 | **247,754** | 73,690 | **3.362×** |

The old `500K pipe/sec` target is **not reached** by the corrected implementation on this environment. Correctness is restored, with roughly 248K pipe/s at N=1024.

## Sanitizers

The final V4 fair benchmark was also run in a smaller but path-equivalent configuration under:

```text
-fsanitize=address,undefined
-fno-omit-frame-pointer
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1
UBSAN_OPTIONS=halt_on_error=1
```

Both the fair benchmark and SQASM C reference exited successfully with no sanitizer finding.

## What is now proven

1. The corrected batch implementation is deterministic and matches the sequential path.
2. Cache deletion and persistence work in the tested mmap configuration.
3. The accelerator no longer silently ignores the trailing byte case tested.
4. The unified compressor is self-contained across processes for 1000 tested corpora.
5. Corruption is rejected.
6. The topological V10 archive can restore without an external dictionary.
7. The LLVM path is valid and executable.
8. The fixed-point Ring-0 V4 source builds as a kernel module against available headers.
9. Exact lookup favors hash, not Hilbert, in this benchmark.
10. Precomputed descriptors can produce a genuine >1000× measured end-to-end advantage after sufficient repeated varied analytical queries, with index-build cost included.

## What is not yet proven

1. No Ring-0 runtime test was performed on the current 6.18.44 kernel because matching headers/module vermagic are unavailable.
2. No native xxhash/zstandard performance result was produced because those Python packages are unavailable in the execution environment.
3. The >1000× result is not a general operating-system acceleration, not a general compression acceleration, and not a universal Hilbert advantage.
4. The current descriptor benchmark is a synthetic analytical workload; the next scientific gate is replay on a real workload/corpus with frozen queries and a held-out dataset.
5. No hardware quantum acceleration is implied by the virtual-QPIPE code.

## Recommended V5 gate

V5 should be a **Real Workload Closure**:

- freeze one real corpus before benchmark design;
- define 500–5000 real analytical queries from an independent workload;
- compare raw recomputation, hash-backed descriptors, sorted descriptors, B-tree, Hilbert ordering, SQLite/LMDB or another mature index;
- include index build, memory footprint, update cost and cache cold-start;
- run at least 10 independent trials and report median/p5/p95;
- run on at least two machines;
- run the fixed-point `.ko` on a matching-kernel VM and compare ioctl output against the userspace reference;
- install native xxhash/zstandard and rerun compression throughput separately from correctness.

Only after that should the project describe a >1000× result as transferable beyond this synthetic descriptor-query workload.
