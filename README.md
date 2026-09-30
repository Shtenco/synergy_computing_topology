# Synergy Computing Topology

Canonical repository for the SHTENCO / Synergy Computing Topology experimental computing stack.

The repository contains the corrected **V4 Correctness Closure + Fair Benchmark** implementation, historical v1-v3 prototypes, Linux kernel / LLVM experiments, compression and cache prototypes, benchmark harnesses, validation reports, and raw evidence used in the 2026-09-30 audit.

## Current validated milestone: V4

V4 was built around a strict correctness-first gate:

- BUILD_ALL — PASS
- LLVM_VERIFY — PASS
- ASAN / UBSAN — PASS for tested userspace components
- batch QPIPE == sequential QPIPE — PASS
- batch determinism — PASS
- cache delete / restart recovery — PASS
- tail-byte preservation — PASS
- fresh-process compression round-trip — PASS
- SHA-256 validation across 1000 generated corpora — PASS
- corrupted archive rejection — PASS
- query result equality between baseline and optimized paths — PASS
- empty-query guard — PASS
- index build cost included in end-to-end benchmark — PASS

The benchmark result must be interpreted narrowly: the >1000x result is for repeated analytical queries over a **precomputed compact descriptor index** versus recomputing descriptors from raw 256-byte records for every query. It is **not** a claim that an entire operating system or arbitrary workload is 1000x faster.

See `docs/SHTENCO_V4_VALIDATION_REPORT_2026-09-30.md` and `validation/V4_GATE_RESULTS.json` for the exact tested status.

## Repository layout

```text
src/v4/                    Corrected V4 source and benchmark harnesses
src/legacy/                Historical Python implementations (v1-v3)
kernel/v3/                 Historical topological kernel source
legacy/turbo_hpc_v2/       Expanded TURBO_HPC v2 package
benchmarks/legacy/          Original benchmark programs used during audit
validation/                 V4 gate results and raw V4 evidence
audit/evidence/             Earlier audit scripts and raw textual logs
docs/                       Technical audit and V4 validation reports
artifacts/                  Reproducible snapshots and built V4 kernel module
```

## Important experimental status

This repository is research/experimental software. Historical files are preserved because they are part of the evidence trail; some contain bugs or benchmark methodology that V4 was created to correct. Do not interpret comments in legacy sources as validated performance claims.

The V4 audit verified the fixed-point Ring-0 source could be compiled against available Linux headers, but did not claim runtime loading on a mismatched kernel.

## Reproducing V4 userspace checks

```bash
cd src/v4
make
python3 v4_correctness_harness.py
python3 v4_python_perf.py
```

Exact dependencies and host capabilities vary across the Python, LLVM and Linux-kernel components. Use the validation report as the reference for what was actually executed and what remained environment-dependent.

## Provenance

Project lineage includes TURBO HPC, SHTENCO OS, Virtual Qubit HPC, DeepCompress TOPO and the compact-descriptor/index experiments. The repository preserves both the historical sources and the V4 correctness closure so future results can be compared against the exact earlier implementations rather than rewritten history.
