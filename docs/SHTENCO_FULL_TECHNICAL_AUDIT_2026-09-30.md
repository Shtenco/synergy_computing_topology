# SHTENCO / TURBO HPC — technical audit
Date: 2026-09-30
Environment: Linux x86_64, GCC 14.2, Clang 17, Python 3.13.5

## Scope
Audited uploaded sources and TURBO_HPC_v2.zip for syntax/build, runtime correctness, data integrity, concurrency, benchmark methodology, sanitizer behavior, and reproducibility. No source originals were modified. Temporary test harnesses/shims were used only where external Python packages were missing; performance numbers are never taken from shimmed dependencies.

## Verdict
The project contains several working low-level experiments and one especially strong idea: precomputed compact HomDesc/index structures can make repeated filtered queries dramatically faster than recomputing a 256-byte descriptor for every block. However, the current package is not production-ready and the headline 1000x / multi-thousand-x whole-system speedups are not established by the supplied benchmarks.

Critical correctness blockers found:
- TURBO_HPC_v2 LLVM IR does not compile; `make all` still exits 0 and prints BUILD COMPLETE.
- C userspace QPIPE reports impossible negative Shannon entropy.
- Unified v3 Numba batch QPIPE has a parallel data race: shared psi buffers across `prange` iterations; reproduced 62/64 measurement mismatches and nondeterministic reruns.
- Unified v3 QubitCore cache key ignores `threshold`.
- Unified v3 RLE2+LZ4 zero-data path does not round-trip.
- TurboCache delete short-circuits after L2 and can leave L3 stale; deleted values can reappear.
- TurboAccelerator drops trailing bytes when input length is not evenly covered by core blocks; 1024 bytes and the same 1024 plus one byte produced identical accelerator outputs.
- Turbo mmap cache index is RAM-only and is not rebuilt after restart, so stored values are not recoverable by a fresh instance.
- DeepCompress v1/v2 compressed streams depend on the compressor's in-memory dictionary; fresh engine decompression returns no data.
- DEEPCOMPRESS TOPO v9 archives depend on a global external dictionary not embedded in the archive; same-process decode works, fresh-dictionary decode fails SHA verification.

## Build/runtime
All five standalone Python files pass `py_compile`, but in the pristine audit environment they do not start because required packages such as `xxhash`, `zstandard`, and Flask are not installed and no complete dependency lock/requirements file was included.

All five uploaded C files compile with GCC -O3. ASan+UBSan completed without reported errors for topo_real_bench, topo_real_bench2, and sqcore_topo_v3. `shtenco_vs_linux_full.c` has a compiler-detected sequence-point/argument-evaluation bug around `p++` and simultaneous reads of `p` in one snprintf call.

Kernel-module loading was not possible in this environment because `/lib/modules/6.18.44/build` is absent; therefore actual Ring-0 performance, module insertion, ioctl behavior under the live kernel, and kernel concurrency remain unverified.

## Reproduced benchmark results
### topo_real_bench
- Hilbert locality: 1.1x on this run.
- Torus eviction metric: 0.3x (worse).
- Simplex cold-miss metric: 2.0x.
- Homology storage density: 128x, but this is bytes-per-descriptor vs full PSI, not an end-to-end runtime speedup.
- Arena vs malloc: 0.1x (slower).
- Printed combined product: about 10x, then code adds a hard-coded x10 Ring-0 correction to print ~96x. That correction was not measured.

### topo_real_bench2
- Hilbert random lookup: 0.03x.
- Hilbert grouped lookup: 0.15x.
- Hilbert correlated lookup: 0.04x.
- 'Torus' cache hit rate improved 24.2% -> 29.7%, but direct lookup measured 0.5x.
- Simplex miss reduction: 2.1x, but v9 uses an 8-entry array while baseline uses 4 entries, so capacity and prefetch are confounded.
- HomDesc read: 16.6x faster in this run; storage density 21x. This is a valid useful precomputed-index microbenchmark.
- Arena: 0.2x fresh and 0.1x refill, slower than malloc.
- The printed ~74x 'LZMA gain' is not an LZMA compression run: code estimates bytes from Shannon entropy.

### sqcore_topo_v3 userspace benchmark
- v2 VSET: 8 ns/op; v3 TSET: 255 ns/op (v3 slower).
- v2 VGET: 8 ns/op; v3 TGET: 27 ns/op.
- Homology descriptor ratio: 128x (size ratio), compress ~16.7 us/op.
- Arena: 1.6x in this run.
- QPIPE: 5.85 us/op.
- Final 1381x 'overall potential' is not measured end-to-end. Source hard-codes Simplex=10x and computes Torus speedup from a formula, then multiplies these with storage-density and runtime ratios.

### shtenco_vs_linux_full
This run printed a 3.3x geometric mean, but that aggregate is not reliable. Examples:
- allocation: 6.1x for this synthetic arena workload;
- xxhash vs crc32: 1.5x;
- 4KB RLE2 vs memcpy: dramatically slower;
- dominant-byte lookup: ~536x only because baseline recomputes descriptor from 256 bytes while optimized side reads precomputed HomDesc;
- raw file copy: ~3160 MB/s vs computed LZMA 'effective' ~607 MB/s, yet result insertion treats the ratio in the wrong direction and labels it a win;
- mutex vs rwlock: 0.2x, but workloads differ (100% writes vs 99% reads), so comparison is not equivalent;
- Hilbert 'O(1)' path does not verify key equality after indexing, so it is not a correctness-equivalent lookup benchmark.
The final table also mixes latency and throughput in the same numeric fields and formats values by magnitude rather than by unit type.

### bench_real_1000x
Original full run is intentionally enormous and did not complete within the bounded audit run. A coverage-preserving reduced-scale probe showed that the core idea can indeed give >1000x warm-query speedup for a narrow indexed query when compared with recomputing the full descriptor for every raw 256-byte block. Earlier reduced scaling that did not include target_dom=128 produced window=0 and millions-x speedups with zero results, demonstrating the benchmark lacks an empty-query guard.

The key caveat is structural: the code labels the optimized path 'Hilbert-sorted', but the targeted index is actually counting-sorted by dominant byte and `hilbert_d()` is unused by this benchmark. Index construction/sorting cost is excluded from query timing. Thus this is evidence for precomputation + indexing, not for Hilbert topology or whole-OS 1000x speedup.

## Python correctness tests
### TURBO_HPC_SHTENCO_OS_v3.py
Logic-only harness result with real Numba and dependency shims only for missing compression/hash packages:
- batch vs sequential QPIPE: 62/64 measurements mismatched;
- max entropy difference about 20.7;
- repeated batch outputs nondeterministic;
- same data at threshold 0.01 and 0.99 returned the same cached result, while fresh QPIPE calls produced hits 1 vs 8;
- zero-data RLE2+LZ4 compressed to 35 bytes but decompressed to 34 bytes instead of 4096.
Source confirms the race: `_qpipe_batch` allocates one `psi_re` and one `psi_im` before `for b in prange(N)`, so all iterations write the same buffers. Source also confirms cache key is only xxhash(data), not `(data, threshold)`.

### turbo_cache_accelerator.py
Reproduced:
- put/get succeeds;
- delete returns True, but immediate get returns the supposedly deleted value because successful L2 deletion prevents L3 deletion via `or` short-circuit;
- accelerator outputs for 1024-byte input and identical 1025-byte input are exactly equal, confirming last byte is ignored;
- after closing and reopening the same mmap files, a fresh cache instance cannot retrieve previously stored key because the hash->slot index is not persisted/rebuilt.

### virtual_qubit_hpc_v1.py / v2.py
Both normalize encode/Hadamard/QFT outputs to norm 1 in tested paths. However, Hadamard leaves max imaginary magnitude at exactly 0 after operating on a phase-bearing state: implementation transforms only the real component, so this is not a general unitary Hadamard on an arbitrary complex state.

DeepCompressV6 same-engine round-trip works. Fresh-engine round-trip fails in both v1 and v2 (0 output bytes in test), because the compressed stream contains `(cid,pos,len)` references but not the referenced block dictionary.

### DEEPCOMPRESS_TOPO_v9.py
80 KB repetitive test:
- archive: 712 bytes;
- same-process decompression: PASS and exact bytes;
- dictionary entries after compression: 2;
- no dictionary file was saved;
- resetting global dictionary to simulate a fresh process: decompression FAIL, no valid output.
The archive writes magic+metadata+compressed reference stream; referenced dictionary blocks are external. The source also explicitly sets `FUZZY_THRESHOLD = 0.0` because fuzzy mode causes dictionary corruption, so fuzzy functionality advertised in documentation is currently disabled.

## TURBO_HPC_v2 ZIP
Archive structure is valid. C userspace demo builds and runs. LLVM component does not build:
`sqasm_turbo.ll:42:34: error: floating point constant invalid for type`.
`make all` still returns success and prints that LLVM compiled and BUILD COMPLETE, creating a false-green build. `make test_ll` correctly fails. `make validate_ll` exits 0 silently when `llc` is unavailable, so it is not a robust validation gate.

The userspace demo also reports entropy values such as -691.1893 and -482.827. Shannon entropy should not be negative for a normalized probability distribution. The C fallback FWHT changes the real amplitudes without the correct normalization while the entropy routine then uses squared magnitudes as probabilities, causing the invalid metric.

## TurboDaemon snippet
The exact daemon/client implementation is not present in the uploaded files, so network end-to-end testing of `send()`, framing, timeouts, concurrency, authentication, and stop behavior is impossible from the provided materials. Static issues in the pasted snippet:
- `--status` and `--stop` call `TurboDaemon.is_running()` without the parsed host/port, while remote stop uses them;
- `except: pass` in status hides protocol/connectivity failures;
- `if key:` in `accel` omits valid falsy keys; use `if key is not None`;
- `get()` trusts `data_hex` and has no response-schema validation;
- put/accel assume bytes-like input and no visible request-size guard.

## Recommended next gate
Do not optimize further until correctness is closed. The next credible milestone should be:
1. Fix build false-green and LLVM IR.
2. Fix batch QPIPE race and add deterministic batch==sequential property tests.
3. Make all compressed formats self-contained and verify fresh-process round-trip + checksum corruption handling.
4. Fix cache delete, tail handling, persistent index/recovery, and threshold-aware keys.
5. Replace hard-coded/compound speedups with equivalent-work end-to-end benchmarks including build/index cost and non-empty-query assertions.
6. Only after that run a pinned Linux host benchmark with CPU pinning, warm/cold cache separation, perf counters, confidence intervals, and real kernel module loaded.

## Evidence
Raw compiler output, benchmark stdout, sanitizer logs and logic-test harnesses are included in `SHTENCO_AUDIT_EVIDENCE_2026-09-30.zip`.
