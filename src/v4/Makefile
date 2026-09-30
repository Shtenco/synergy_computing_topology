SHELL := /bin/bash
PYTHON ?= python3
CC ?= gcc
CLANG ?= clang
CFLAGS ?= -O3 -march=native -Wall -Wextra -Werror
KDIR ?= $(shell if [ -d /lib/modules/$$(uname -r)/build ]; then echo /lib/modules/$$(uname -r)/build; else ls -d /usr/src/linux-headers-*-amd64 2>/dev/null | sort -V | tail -1; fi)

.PHONY: all python c llvm kernel correctness bench clean
all: python c llvm kernel

python:
	$(PYTHON) -m py_compile TURBO_HPC_SHTENCO_OS_v4.py turbo_cache_accelerator_v2.py DEEPCOMPRESS_TOPO_v10_V4.py

c: v4_fair_benchmark sqasm_turbo_v4_ref

v4_fair_benchmark: v4_fair_benchmark.c
	$(CC) $(CFLAGS) $< -o $@

sqasm_turbo_v4_ref: sqasm_turbo_v4.c
	$(CC) $(CFLAGS) $< -o $@ -lm

llvm: sqasm_turbo_v4.ll turbo_test_v4 sqasm_turbo_v4.o

sqasm_turbo_v4.ll: sqasm_turbo_v4.c
	$(CLANG) -O1 -S -emit-llvm $< -o $@

turbo_test_v4: sqasm_turbo_v4.ll
	$(CLANG) $(CFLAGS) $< -o $@ -lm

sqasm_turbo_v4.o: sqasm_turbo_v4.ll
	$(CLANG) $(CFLAGS) -c $< -o $@

kernel:
	@test -n "$(KDIR)" -a -d "$(KDIR)" || (echo "No kernel headers found"; exit 1)
	@rm -rf .kbuild && mkdir .kbuild && cp sqcore_turbo_v4.c .kbuild/ && printf 'obj-m += sqcore_turbo_v4.o
ccflags-y += -Werror
' > .kbuild/Makefile
	TERM=xterm $(MAKE) -C $(KDIR) M=$(CURDIR)/.kbuild modules
	cp .kbuild/sqcore_turbo_v4.ko ./sqcore_turbo_v4.ko

correctness: python
	$(PYTHON) v4_correctness_harness.py
	$(PYTHON) v10_parent_plain_test.py

bench: c
	./v4_fair_benchmark
	$(PYTHON) v4_python_perf.py

clean:
	rm -f v4_fair_benchmark sqasm_turbo_v4_ref turbo_test_v4 sqasm_turbo_v4.o sqcore_turbo_v4.ko
	rm -rf __pycache__ .kbuild
