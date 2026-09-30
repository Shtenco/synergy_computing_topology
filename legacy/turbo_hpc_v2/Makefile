# ============================================================================
#  TURBO HPC SYSTEM v2.0 — Makefile
#  Evgeniy Koshtenko / Kostanay, Kazakhstan / 2026
#
#  Targets:
#    make all          — всё: kernel module + client + LLVM + demo
#    make kernel       — только sqcore_turbo.ko (требует kernel-headers)
#    make client       — только userspace C client + standalone demo
#    make llvm         — компиляция sqasm_turbo.ll → нативный .o
#    make demo         — запуск standalone демо (без .ko)
#    make bench        — полный бенчмарк
#    make test_ll      — тест LLVM IR ядер
#    make install      — insmod + udev rule
#    make uninstall    — rmmod
#    make clean        — удалить собранные файлы
#
#  Требования:
#    kernel: linux-headers-$(uname -r) gcc make
#    llvm:   clang llvm (apt install clang llvm)
#    client: gcc -lm
# ============================================================================

# ── Конфигурация ──────────────────────────────────────────────────────────────
CC        := gcc
CLANG     := clang
LLC       := llc
CFLAGS    := -O3 -march=native -ffast-math -Wall -Wextra
LDFLAGS   := -lm

KDIR      := /lib/modules/$(shell uname -r)/build
PWD       := $(shell pwd)

DEVICE    := /dev/sqcore_turbo
UDEV_RULE := /etc/udev/rules.d/99-sqcore-turbo.rules

# Цвета вывода
RED   := \033[91m
GREEN := \033[92m
CYAN  := \033[96m
GOLD  := \033[33m
RESET := \033[0m

# ── Главные цели ──────────────────────────────────────────────────────────────
.PHONY: all kernel client llvm demo bench test_ll install uninstall clean help

all: client llvm
	@echo ""
	@printf "$(GREEN)══════════════════════════════════════════════════════$(RESET)\n"
	@printf "$(GREEN)  TURBO HPC v2.0 — BUILD COMPLETE$(RESET)\n"
	@printf "  sqcore_client_turbo  (C client + demo)\n"
	@printf "  sqasm_turbo.o        (LLVM IR compiled)\n"
	@printf "  turbo_test           (LLVM standalone)\n"
	@printf "$(GREEN)══════════════════════════════════════════════════════$(RESET)\n"
	@echo ""
	@echo "  Run demo:   ./sqcore_demo"
	@echo "  Run bench:  ./sqcore_demo --bench 50000"
	@echo "  LLVM test:  ./turbo_test"
	@echo ""
	@printf "  Kernel module: $(GOLD)make kernel$(RESET)  (requires kernel-headers)\n"

# ── Kernel Module ─────────────────────────────────────────────────────────────
obj-m += sqcore_turbo.o

kernel: sqcore_turbo.c
	@printf "$(CYAN)[KO]$(RESET) Building sqcore_turbo.ko...\n"
	@if [ ! -d "$(KDIR)" ]; then \
		printf "$(RED)ERROR: kernel headers not found at $(KDIR)$(RESET)\n"; \
		printf "  Install: sudo apt install linux-headers-$$(uname -r)\n"; \
		exit 1; \
	fi
	$(MAKE) -C $(KDIR) M=$(PWD) modules
	@printf "$(GREEN)[KO] sqcore_turbo.ko built successfully$(RESET)\n"
	@modinfo sqcore_turbo.ko 2>/dev/null | head -5 || true

# ── Userspace C Client ────────────────────────────────────────────────────────
client: sqcore_client_turbo.c
	@printf "$(CYAN)[CC]$(RESET) Building C client + demo...\n"
	$(CC) $(CFLAGS) -DSQCORE_MAIN -o sqcore_demo sqcore_client_turbo.c $(LDFLAGS)
	@printf "$(GREEN)[CC] sqcore_demo built$(RESET)\n"

# Библиотека .so
libsqcore.so: sqcore_client_turbo.c
	@printf "$(CYAN)[SO]$(RESET) Building shared library...\n"
	$(CC) $(CFLAGS) -shared -fPIC -o libsqcore.so sqcore_client_turbo.c $(LDFLAGS)
	@printf "$(GREEN)[SO] libsqcore.so built$(RESET)\n"

# ── LLVM IR Kernels ───────────────────────────────────────────────────────────
llvm: sqasm_turbo.ll
	@printf "$(CYAN)[LL]$(RESET) Compiling LLVM IR → native...\n"
	@if command -v $(CLANG) >/dev/null 2>&1; then \
		$(CLANG) -O3 -march=native sqasm_turbo.ll -c -o sqasm_turbo.o -lm 2>&1 || \
		printf "$(RED)[LL] Compile failed — check LLVM install$(RESET)\n"; \
		printf "$(GREEN)[LL] sqasm_turbo.o compiled$(RESET)\n"; \
	else \
		printf "$(RED)[LL] clang not found — skipping LLVM$(RESET)\n"; \
		printf "  Install: sudo apt install clang\n"; \
	fi

# Standalone test binary из LLVM IR
turbo_test: sqasm_turbo.ll
	@if command -v $(CLANG) >/dev/null 2>&1; then \
		printf "$(CYAN)[LL]$(RESET) Building LLVM test binary...\n"; \
		$(CLANG) -O3 -march=native sqasm_turbo.ll -o turbo_test -lm && \
		printf "$(GREEN)[LL] turbo_test built$(RESET)\n"; \
	fi

test_ll: turbo_test
	@printf "$(CYAN)[TEST]$(RESET) Running LLVM kernel test...\n"
	@./turbo_test

# ── Demo & Bench ──────────────────────────────────────────────────────────────
demo: client
	@printf "$(CYAN)[RUN]$(RESET) TURBO HPC Demo\n"
	./sqcore_demo

bench: client
	@printf "$(CYAN)[BENCH]$(RESET) TURBO HPC Full Benchmark N=50000\n"
	./sqcore_demo --bench 50000

# ── Install / Uninstall ───────────────────────────────────────────────────────
install: kernel
	@printf "$(CYAN)[INSTALL]$(RESET) Loading sqcore_turbo.ko...\n"
	@if [ "$$(id -u)" != "0" ]; then \
		printf "$(RED)ERROR: need root (sudo make install)$(RESET)\n"; exit 1; \
	fi
	sudo insmod sqcore_turbo.ko || true
	@printf "$(CYAN)[UDEV]$(RESET) Creating udev rule...\n"
	echo 'KERNEL=="sqcore_turbo", GROUP="sqcore", MODE="0660"' > $(UDEV_RULE)
	groupadd -f sqcore
	udevadm control --reload-rules && udevadm trigger
	@if [ -c "$(DEVICE)" ]; then \
		printf "$(GREEN)[OK]$(RESET) $(DEVICE) created\n"; \
	else \
		printf "$(RED)[WARN]$(RESET) device not found — check dmesg\n"; \
	fi
	@dmesg | grep sqcore_turbo | tail -3 || true

uninstall:
	@printf "$(CYAN)[UNINSTALL]$(RESET) Removing sqcore_turbo.ko...\n"
	sudo rmmod sqcore_turbo 2>/dev/null || true
	sudo rm -f $(UDEV_RULE)
	@printf "$(GREEN)[OK]$(RESET) sqcore_turbo unloaded\n"

# ── Validate LLVM IR syntax ───────────────────────────────────────────────────
validate_ll:
	@if command -v llc >/dev/null 2>&1; then \
		printf "$(CYAN)[VALID]$(RESET) Validating LLVM IR...\n"; \
		$(LLC) -march=x86-64 sqasm_turbo.ll -o /dev/null && \
		printf "$(GREEN)[VALID] sqasm_turbo.ll OK$(RESET)\n" || \
		printf "$(RED)[VALID] sqasm_turbo.ll has errors$(RESET)\n"; \
	fi

# ── Status ────────────────────────────────────────────────────────────────────
status:
	@printf "$(CYAN)TURBO HPC STATUS$(RESET)\n"
	@echo "  Kernel module:"
	@lsmod | grep sqcore_turbo && echo "    LOADED" || echo "    not loaded"
	@ls -la $(DEVICE) 2>/dev/null && echo "    device OK" || echo "    device not present"
	@echo ""
	@echo "  /proc stats:"
	@cat /proc/sqcore_turbo/stats 2>/dev/null || echo "    (module not loaded)"
	@echo ""
	@echo "  Build artifacts:"
	@ls -la sqcore_turbo.ko sqcore_demo sqasm_turbo.o turbo_test 2>/dev/null || echo "    (not built)"

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	@printf "$(CYAN)[CLEAN]$(RESET) Removing build artifacts...\n"
	rm -f sqcore_demo turbo_test sqasm_turbo.o libsqcore.so
	rm -f *.ko *.o *.mod *.mod.c *.order *.symvers .*.cmd
	rm -rf .tmp_versions __pycache__
	@printf "$(GREEN)[CLEAN] Done$(RESET)\n"

# ── Help ─────────────────────────────────────────────────────────────────────
help:
	@printf "$(GOLD)TURBO HPC SYSTEM v2.0$(RESET)  —  Evgeniy Koshtenko / 2026\n\n"
	@echo "  make all          → client + LLVM (no kernel required)"
	@echo "  make kernel       → sqcore_turbo.ko (requires kernel-headers)"
	@echo "  make client       → sqcore_demo (standalone C demo)"
	@echo "  make llvm         → sqasm_turbo.o (LLVM IR → native)"
	@echo "  make demo         → run demo (userspace fallback if no .ko)"
	@echo "  make bench        → full benchmark N=50000"
	@echo "  make test_ll      → LLVM kernel test binary"
	@echo "  make install      → insmod + udev (sudo required)"
	@echo "  make uninstall    → rmmod + cleanup"
	@echo "  make status       → show module/device/proc status"
	@echo "  make clean        → remove build artifacts"
	@echo ""
	@echo "  Files:"
	@echo "    sqcore_turbo.c        — Linux kernel module Ring 0 v2.0"
	@echo "    sqasm_turbo.ll        — LLVM IR kernels (QPIPE/GROV/FWHT/...)"
	@echo "    sqcore_client_turbo.c — Userspace C client (Ring 0 + fallback)"
	@echo "    turbo_hpc.sq          — Main program in SQ v2.0 language"
	@echo "    Makefile              — This file"
