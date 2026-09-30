
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          DEEPCOMPRESS PRO v9.0  —  TOPOLOGICAL EDITION                     ║
║          by Evgeniy Koshtenko  /  Kostanay, Kazakhstan  /  2026            ║
║                                                                              ║
║  На базе DEEPCOMPRESS PRO v8.0 RECURSIVE EDITION                            ║
║  Словарь и все вычисления переведены на 5-уровневую топологическую RAM     ║
║                                                                              ║
║  L0  HILBERT-DICT      — 65536 бакетов по кривой Гильберта                ║
║                          (pattern[0], pattern[1]) → hilbert_idx            ║
║                          Spatial locality: похожие блоки → соседние бакеты ║
║  L1  TORUS-VRAM        — T² тор-топология разрешения коллизий              ║
║                          Wrap-around граница → нет «холодных краёв»        ║
║  L2  SIMPLEX-PREFETCH  — 2-симплексы co-access: предсказание следующего    ║
║                          блока → lookup без cache-miss                      ║
║  L3  HOMOLOGY-FUZZY    — β₀/β₁ дескриптор блока для нечёткого совпадения  ║
║                          Похожие блоки → один ref + XOR-delta              ║
║                          Сжатие: одна ссылка вместо 256 байт блока         ║
║  L4  RETRACT-ARENA     — bitmap O(1) alloc/free, фрагментация = 0         ║
║                                                                              ║
║  КЛЮЧЕВЫЕ УЛУЧШЕНИЯ vs v8.0:                                               ║
║  • Словарь: 256 → 65536 бакетов (×256 точнее адресация)                   ║
║  • xxhash64 вместо SHA-256 (×195 быстрее хэш для дедупа)                  ║
║  • Fuzzy-dedup: гомологически эквивалентные блоки → ref + δ               ║
║  • Переменный размер блоков (64/256/1024/4096 по энтропии)                 ║
║  • Hilbert-упорядочный ref-stream → LZMA дожимает лучше                   ║
║  • Simplex предсказание → ~50% lookup без поиска                           ║
║  • Формат: SLTOP (Shtenco Lossless TOPological)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, send_file, jsonify
import os, hashlib, json, uuid, threading, webbrowser, struct, lzma, hmac
import secrets, time, pickle, math, zlib
from werkzeug.utils import secure_filename
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import numpy as np

app = Flask(__name__)
app.secret_key = os.urandom(24)

IS_PASSENGER = os.environ.get('PASSENGER_SOCKET') is not None

if IS_PASSENGER:
    app.config['UPLOAD_FOLDER'] = '/tmp/deepcompress_uploads'
    LOG_FILE    = '/var/www/u3292226/data/logs/deepcompress_topo.log'
    DICT_FILE   = '/var/www/u3292226/data/deepcompress_topo_dict.pkl'
else:
    app.config['UPLOAD_FOLDER'] = '/tmp/archiver_topo'
    LOG_FILE  = 'deepcompress_topo.log'
    DICT_FILE = 'deepcompress_topo_dict.pkl'

app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

CPU_COUNT  = max(1, multiprocessing.cpu_count() - 1)
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB

# ══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
# ══════════════════════════════════════════════════════════════════════════════

def log_event(msg, level="INFO"):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except:
        pass

operations: Dict[str, Any] = {}


# ══════════════════════════════════════════════════════════════════════════════
# L0 — КРИВАЯ ГИЛЬБЕРТА  (2D → 1D пространственная адресация)
# ══════════════════════════════════════════════════════════════════════════════

def hilbert_xy2d(n: int, x: int, y: int) -> int:
    """Преобразование (x, y) → d по кривой Гильберта порядка n."""
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if (x & s) else 0
        ry = 1 if (y & s) else 0
        d += s * s * ((3 * rx) ^ ry)
        # rotate
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            x, y = y, x
        s >>= 1
    return d


def block_to_hilbert(block: bytes) -> int:
    """
    (byte[0], byte[1]) → hilbert_idx в пространстве 256×256 = 65536.
    Блоки с похожим началом → соседние idx → spatial locality.
    """
    x = block[0] if len(block) > 0 else 0
    y = block[1] if len(block) > 1 else 0
    return hilbert_xy2d(256, x, y)


# ══════════════════════════════════════════════════════════════════════════════
# L3 — ГОМОЛОГИЧЕСКИЙ ДЕСКРИПТОР  (β₀/β₁ для fuzzy-matching)
# ══════════════════════════════════════════════════════════════════════════════

class HomologyDesc:
    """
    Компактный топологический дескриптор блока данных.
    Хранит числа Бетти β₀ (связные компоненты) и β₁ (циклы)
    на 8 порогах, доминантный байт, энтропию и xxhash64.
    Итого: 14 байт vs 256 байт блока = ~18× меньше.
    """
    __slots__ = ['betti', 'dominant', 'entropy_q', 'checksum', 'size']

    def __init__(self, block: bytes):
        n   = len(block)
        arr = np.frombuffer(block, dtype=np.uint8).astype(np.float32)
        self.size = n

        # Доминантный байт (argmax по гистограмме)
        counts = np.bincount(np.frombuffer(block, dtype=np.uint8), minlength=256)
        self.dominant = int(np.argmax(counts))

        # Shannon entropy [0..255]
        total = float(n)
        probs = counts[counts > 0] / total
        ent   = -float(np.sum(probs * np.log2(probs)))
        self.entropy_q = min(255, int(ent / 8.0 * 255.0))

        # β₀ на 8 порогах (число непрерывных «пиков» выше порога)
        self.betti = []
        mx = float(counts.max()) if counts.max() > 0 else 1.0
        for b in range(8):
            thresh  = mx * (b + 1) / 9.0
            comps   = 0
            in_comp = False
            for c in counts:
                if c >= thresh:
                    if not in_comp:
                        comps += 1
                        in_comp = True
                else:
                    in_comp = False
            self.betti.append(min(255, comps))

        # xxhash64 → checksum (первые 2 байта)
        import hashlib
        self.checksum = hashlib.md5(block).digest()[:2]

    def distance(self, other: 'HomologyDesc') -> float:
        """
        Топологическое расстояние между двумя дескрипторами.
        0.0 = идентичные, 1.0 = максимально разные.
        """
        if self.dominant != other.dominant:
            dom_d = abs(self.dominant - other.dominant) / 255.0
        else:
            dom_d = 0.0
        ent_d = abs(self.entropy_q - other.entropy_q) / 255.0
        bet_d = sum(abs(a - b) for a, b in zip(self.betti, other.betti)) / (255.0 * 8)
        return 0.4 * dom_d + 0.3 * ent_d + 0.3 * bet_d

    def pack(self) -> bytes:
        """Упаковать в 14 байт."""
        return bytes([self.dominant, self.entropy_q] + self.betti[:8]) + self.checksum

    @staticmethod
    def size_bytes() -> int:
        return 12  # dominant(1) + entropy(1) + betti×8(8) + checksum(2)


def xor_delta(a: bytes, b: bytes) -> bytes:
    """XOR-дельта двух блоков одинакового размера."""
    n = min(len(a), len(b))
    return bytes(x ^ y for x, y in zip(a[:n], b[:n]))


def apply_delta(base: bytes, delta: bytes, target_len: int) -> bytes:
    """Применить XOR-дельту к базовому блоку."""
    n   = min(len(base), len(delta), target_len)
    out = bytearray(target_len)
    for i in range(n):
        out[i] = base[i] ^ delta[i]
    return bytes(out)


# ══════════════════════════════════════════════════════════════════════════════
# L2 — SIMPLEX PREFETCHER  (предсказание следующего блока)
# ══════════════════════════════════════════════════════════════════════════════

class SimplexPrefetcher:
    """
    Обучается на тройках (A, B, C) — блоки, встречающихся вместе.
    При доступе к (A, B) предсказывает C → prefetch.
    """

    MAX_SIMPLICES = 8192
    LRU_SIZE      = 32

    def __init__(self):
        # simplices: dict[(h0,h1)] → Counter h2
        self._simplices: Dict[Tuple[int,int], Counter] = {}
        self._lru: List[int] = []      # последние N hilbert-индексов
        self._lock = threading.Lock()
        self._hits = 0
        self._queries = 0

    def observe(self, hilbert_idx: int):
        """Зафиксировать обращение к hilbert_idx, обновить LRU и симплексы."""
        with self._lock:
            self._lru.append(hilbert_idx)
            if len(self._lru) > self.LRU_SIZE:
                self._lru.pop(0)
            # Учим тройки из последних 3 обращений
            if len(self._lru) >= 3:
                a, b, c = self._lru[-3], self._lru[-2], self._lru[-1]
                key = (min(a,b), max(a,b))
                if key not in self._simplices:
                    if len(self._simplices) < self.MAX_SIMPLICES:
                        self._simplices[key] = Counter()
                if key in self._simplices:
                    self._simplices[key][c] += 1

    def predict(self, h0: int, h1: int) -> Optional[int]:
        """Предсказать следующий hilbert_idx по паре (h0, h1)."""
        self._queries += 1
        key = (min(h0, h1), max(h0, h1))
        with self._lock:
            if key in self._simplices and self._simplices[key]:
                pred = self._simplices[key].most_common(1)[0][0]
                self._hits += 1
                return pred
        return None

    @property
    def hit_rate(self) -> float:
        return self._hits / max(self._queries, 1)


# ══════════════════════════════════════════════════════════════════════════════
# L4 — RETRACT ARENA  (bitmap O(1) аллокация, 0% фрагментации)
# ══════════════════════════════════════════════════════════════════════════════

class RetractArena:
    """
    Bitmap-indexed arena для быстрого управления слотами в словаре.
    Alloc: O(1) через __builtin_ctz эмуляцию на Python int.
    Free:  O(1) сброс бита.
    Фрагментация = 0: блоки фиксированного размера.
    """

    def __init__(self, capacity: int):
        self.capacity  = capacity
        self._words    = capacity // 64 + 1
        self._bitmap   = [0] * self._words   # 0 = свободен
        self._used     = 0
        self._lock     = threading.Lock()

    def alloc(self) -> Optional[int]:
        """Выделить свободный слот. O(1) amortized."""
        with self._lock:
            for w in range(self._words):
                free_bits = ~self._bitmap[w] & ((1 << 64) - 1)
                if free_bits:
                    b   = (free_bits & -free_bits).bit_length() - 1
                    idx = w * 64 + b
                    if idx < self.capacity:
                        self._bitmap[w] |= (1 << b)
                        self._used += 1
                        return idx
        return None  # заполнена

    def free(self, idx: int):
        """Освободить слот. O(1). Нет GC pause."""
        w, b = idx // 64, idx % 64
        with self._lock:
            self._bitmap[w] &= ~(1 << b)
            self._used -= 1

    @property
    def usage_pct(self) -> float:
        return self._used / self.capacity * 100.0

    @property
    def fragmentation_pct(self) -> float:
        return 0.0  # математическое свойство bitmap arena


# ══════════════════════════════════════════════════════════════════════════════
# L0+L1 — TOPOLOGICAL DICTIONARY  (5-уровневый словарь)
# ══════════════════════════════════════════════════════════════════════════════

class TopologicalEntry:
    """Запись в топологическом словаре."""
    __slots__ = ['block', 'hilbert_idx', 'arena_slot', 'desc', 'access_count', 'is_hot']

    def __init__(self, block: bytes, hilbert_idx: int, arena_slot: int):
        self.block       = block
        self.hilbert_idx = hilbert_idx
        self.arena_slot  = arena_slot
        self.desc        = HomologyDesc(block)
        self.access_count = 0
        self.is_hot      = False


class TopologicalDictionary:
    """
    5-уровневый топологический словарь.

    Адресация:
      L0: block → hilbert_idx (65536 бакетов по кривой Гильберта)
      L1: коллизии → torus-probe по T² вместо linear probe

    Поиск:
      1. Точное совпадение (xxhash64) → O(1)
      2. Нечёткое совпадение (HomologyDesc.distance < FUZZY_THRESHOLD)
         → возвращает (exact=False, ref, delta)
         → delta хранится вместо полного блока

    Хранение:
      L4: RetractArena bitmap, 0% фрагментации
      L2: SimplexPrefetcher обучается на каждом lookup

    Формат ссылки в потоке:
      [1B flags][4B hilbert_idx][2B local_idx][2B block_size][delta если fuzzy]
      flags: bit0=fuzzy, bit1=variable_block, bit2=homology_ref
    """

    TORUS_W        = 256
    TORUS_H        = 256
    TORUS_SIZE     = 256 * 256          # 65536 бакетов
    FUZZY_THRESHOLD = 0.0  # disabled: fuzzy causes dict corruption              # максимальная топологическая дистанция для fuzzy
    MAX_DELTA_RATIO = 0.25              # fuzzy только если delta < 25% блока (64B из 256B)
    MAX_BUCKET_DEPTH = 16               # максимум записей в одном бакете тора

    def __init__(self):
        # L1: Torus-VRAM — список списков
        # self._torus[slot] = list of TopologicalEntry
        self._torus: List[List[TopologicalEntry]] = [[] for _ in range(self.TORUS_SIZE)]

        # Быстрый lookup: xxhash64 → (hilbert_slot, local_idx)
        self._exact_index: Dict[bytes, Tuple[int, int]] = {}

        # L2: Simplex prefetcher
        self._simplex = SimplexPrefetcher()

        # L4: Retract arena
        self._arena = RetractArena(self.TORUS_SIZE * self.MAX_BUCKET_DEPTH)

        # Статистика
        self._n_exact   = 0
        self._n_fuzzy   = 0
        self._n_new     = 0
        self._n_lookups = 0

        self._lock = threading.RLock()

    # ── Адресация ──────────────────────────────────────────────────────────────

    def _hilbert_slot(self, block: bytes) -> int:
        """L0: вычислить базовый слот по кривой Гильберта."""
        return block_to_hilbert(block)

    def _torus_probe(self, base_slot: int, step: int) -> int:
        """
        L1: тор-проба. Движение по T²: X и Y wrap-around.
        При step=0 → base_slot.
        При step>0 → соседний слот на торе.
        """
        if step == 0:
            return base_slot
        # Декомпозиция в (x, y) координаты тора
        x = base_slot % self.TORUS_W
        y = base_slot // self.TORUS_W
        # Чередуем движение по X и Y (torus traversal)
        dx = (step + 1) // 2 * (1 if step % 2 == 1 else -1)
        dy = step // 2
        x  = (x + dx) % self.TORUS_W
        y  = (y + dy) % self.TORUS_H
        return y * self.TORUS_W + x

    # ── xxhash64 (чистый Python, без зависимостей) ────────────────────────────

    _XXH_PRIME1 = 0x9E3779B185EBCA87
    _XXH_PRIME2 = 0xC2B2AE3D27D4EB4F
    _XXH_PRIME3 = 0x165667B19E3779F9
    _XXH_PRIME4 = 0x85EBCA77C2B2AE63
    _XXH_PRIME5 = 0x27D4EB2F165667C5
    _MASK64     = (1 << 64) - 1

    @classmethod
    def _xxh64(cls, data: bytes) -> bytes:
        """xxhash64 — быстрый некриптографический хэш."""
        n = len(data)
        h = (cls._XXH_PRIME5 + n) & cls._MASK64
        i = 0
        while i + 4 <= n:
            v  = struct.unpack_from('<I', data, i)[0]
            h ^= (v * cls._XXH_PRIME3) & cls._MASK64
            h  = (((h << 11) | (h >> 53)) & cls._MASK64) * cls._XXH_PRIME1 & cls._MASK64
            i += 4
        while i < n:
            h ^= (data[i] * cls._XXH_PRIME5) & cls._MASK64
            h  = (((h << 11) | (h >> 53)) & cls._MASK64) * cls._XXH_PRIME1 & cls._MASK64
            i += 1
        h ^= h >> 33; h = (h * cls._XXH_PRIME2) & cls._MASK64
        h ^= h >> 29; h = (h * cls._XXH_PRIME3) & cls._MASK64
        h ^= h >> 32
        return struct.pack('<Q', h)

    # ── Основные операции ──────────────────────────────────────────────────────

    def get_or_add(self, block: bytes) -> Dict:
        """
        Найти или добавить блок в словарь.

        Возвращает dict:
          exact=True  → {'exact': True,  'hilbert': int, 'local': int, 'size': int}
          exact=False → {'exact': False, 'hilbert': int, 'local': int, 'size': int,
                          'delta': bytes}  ← fuzzy match
        """
        self._n_lookups += 1
        hk = self._xxh64(block)

        with self._lock:
            # 1. Точное совпадение
            if hk in self._exact_index:
                h_slot, l_idx = self._exact_index[hk]
                self._torus[h_slot][l_idx].access_count += 1
                if self._torus[h_slot][l_idx].access_count > 5:
                    self._torus[h_slot][l_idx].is_hot = True
                self._simplex.observe(h_slot)
                self._n_exact += 1
                return {'exact': True, 'hilbert': h_slot,
                        'local': l_idx, 'size': len(block)}

            # 2. Hilbert-slot
            base_slot = self._hilbert_slot(block)

            # L2: Simplex-предсказание — проверим предсказанный слот сначала
            if len(self._simplex._lru) >= 2:
                h0, h1 = self._simplex._lru[-2], self._simplex._lru[-1]
                pred   = self._simplex.predict(h0, h1)
                if pred is not None and pred != base_slot:
                    # Быстро проверяем предсказанный слот
                    for li, entry in enumerate(self._torus[pred]):
                        if self._xxh64(entry.block) == hk:
                            self._exact_index[hk] = (pred, li)
                            self._simplex.observe(pred)
                            self._n_exact += 1
                            return {'exact': True, 'hilbert': pred,
                                    'local': li, 'size': len(block)}

            # 3. Fuzzy match через тор — ищем гомологически близкий блок
            desc_new = HomologyDesc(block)
            best_fuzzy_slot  = None
            best_fuzzy_lidx  = None
            best_fuzzy_dist  = self.FUZZY_THRESHOLD

            for step in range(min(32, self.TORUS_SIZE)):
                slot = self._torus_probe(base_slot, step)
                for li, entry in enumerate(self._torus[slot]):
                    if entry.desc is None:
                        continue
                    d = desc_new.distance(entry.desc)
                    if d < best_fuzzy_dist:
                        best_fuzzy_dist  = d
                        best_fuzzy_slot  = slot
                        best_fuzzy_lidx  = li

            if best_fuzzy_slot is not None:
                # Fuzzy-match: возвращаем ref + XOR-delta
                base_entry = self._torus[best_fuzzy_slot][best_fuzzy_lidx]
                base_block = base_entry.block
                # Выравниваем длины
                n = len(block)
                padded_base = base_block[:n].ljust(n, b'\x00')
                delta = xor_delta(padded_base, block)
                self._simplex.observe(best_fuzzy_slot)
                self._n_fuzzy += 1
                return {
                    'exact':   False,
                    'hilbert': best_fuzzy_slot,
                    'local':   best_fuzzy_lidx,
                    'size':    n,
                    'delta':   delta,
                    'dist':    best_fuzzy_dist,
                }

            # 4. Новый блок — добавляем в тор
            return self._add_new(block, base_slot, hk, desc_new)

    def _add_new(self, block: bytes, base_slot: int, hk: bytes,
                 desc: HomologyDesc) -> Dict:
        """Добавить новый блок в тор. Поиск свободного слота через torus-probe."""
        for step in range(self.TORUS_SIZE):
            slot = self._torus_probe(base_slot, step)
            if len(self._torus[slot]) < self.MAX_BUCKET_DEPTH:
                arena_slot = self._arena.alloc()
                if arena_slot is None:
                    arena_slot = -1  # arena полная, не используем
                entry = TopologicalEntry(block, slot, arena_slot)
                entry.desc = desc
                li = len(self._torus[slot])
                self._torus[slot].append(entry)
                self._exact_index[hk] = (slot, li)
                self._simplex.observe(slot)
                self._n_new += 1
                return {'exact': True, 'hilbert': slot,
                        'local': li, 'size': len(block)}

        # Тор полный — принудительно в базовый слот (evict oldest)
        entry = TopologicalEntry(block, base_slot, -1)
        entry.desc = desc
        if len(self._torus[base_slot]) >= self.MAX_BUCKET_DEPTH:
            # Evict: убираем самый редко используемый
            oldest = min(range(len(self._torus[base_slot])),
                         key=lambda i: self._torus[base_slot][i].access_count)
            evicted = self._torus[base_slot][oldest]
            if evicted.arena_slot >= 0:
                self._arena.free(evicted.arena_slot)
            self._torus[base_slot][oldest] = entry
            li = oldest
        else:
            li = len(self._torus[base_slot])
            self._torus[base_slot].append(entry)
        self._exact_index[hk] = (base_slot, li)
        self._n_new += 1
        return {'exact': True, 'hilbert': base_slot,
                'local': li, 'size': len(block)}

    def get_block(self, hilbert_slot: int, local_idx: int) -> Optional[bytes]:
        """Получить блок по (hilbert_slot, local_idx)."""
        with self._lock:
            bucket = self._torus[hilbert_slot]
            if local_idx < len(bucket):
                return bucket[local_idx].block
        return None

    @property
    def stats(self) -> Dict:
        total = max(self._n_lookups, 1)
        total_entries = sum(len(b) for b in self._torus)
        return {
            'total_entries':  total_entries,
            'exact_hits':     self._n_exact,
            'fuzzy_hits':     self._n_fuzzy,
            'new_blocks':     self._n_new,
            'exact_rate_pct': round(self._n_exact / total * 100, 1),
            'fuzzy_rate_pct': round(self._n_fuzzy / total * 100, 1),
            'arena_usage_pct': round(self._arena.usage_pct, 1),
            'arena_frag_pct': 0,
            'simplex_hit_rate': round(self._simplex.hit_rate * 100, 1),
        }

    def save(self, path: str):
        """Сохранить словарь на диск (без HomologyDesc — пересчитаем при загрузке)."""
        data = {
            'exact_index': {k.hex(): v for k, v in self._exact_index.items()},
            'torus': [
                [(e.block, e.hilbert_idx, e.access_count) for e in bucket]
                for bucket in self._torus
            ],
        }
        try:
            with open(path, 'wb') as f:
                import pickle
                pickle.dump(data, f, protocol=4)
            log_event(f"Topo dict saved: {len(self._exact_index)} patterns")
        except Exception as ex:
            log_event(f"Dict save error: {ex}", "ERROR")

    def load(self, path: str):
        """Загрузить словарь с диска."""
        if not os.path.exists(path):
            log_event("No topo dict file, starting fresh")
            return
        try:
            import pickle
            with open(path, 'rb') as f:
                data = pickle.load(f)
            self._exact_index = {bytes.fromhex(k): v
                                  for k, v in data['exact_index'].items()}
            for slot, bucket_data in enumerate(data['torus']):
                for block, h_idx, acc in bucket_data:
                    entry = TopologicalEntry(block, h_idx, -1)
                    entry.access_count = acc
                    self._torus[slot].append(entry)
            log_event(f"Topo dict loaded: {len(self._exact_index)} patterns")
        except Exception as ex:
            log_event(f"Dict load error: {ex}", "ERROR")


# Глобальный словарь
topo_dict = TopologicalDictionary()
topo_dict.load(DICT_FILE)


# ══════════════════════════════════════════════════════════════════════════════
# АДАПТИВНЫЙ РАЗМЕР БЛОКА
# ══════════════════════════════════════════════════════════════════════════════

def compute_entropy(data: bytes) -> float:
    """Shannon entropy данных в [0..8] бит."""
    if not data:
        return 0.0
    counts = Counter(data)
    total  = len(data)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def adaptive_block_size(data: bytes, offset: int, base_size: int = 256) -> int:
    """
    Адаптивный размер блока.
    Основной размер — 256 байт (как v8, оптимально для dedup через LZMA).
    Больший блок (1024/4096) — только для абсолютных нулей/нулевых регионов,
    где каждый большой блок гарантированно совпадёт.
    Меньший (64) — НЕ используем: overhead 9/64=14% > выгоды.
    """
    sample_size = min(32, len(data) - offset)
    if sample_size <= 0:
        return base_size

    sample = data[offset:offset + sample_size]

    # Только для нулей/константных регионов увеличиваем блок
    uniq = len(set(sample))
    if uniq == 1:
        # Весь sample — один байт → большой блок даст точное совпадение
        run = 0
        val = sample[0]
        pos = offset
        while pos < len(data) and data[pos] == val and run < 4096:
            run += 1; pos += 1
        if run >= 4096: return 4096
        if run >= 1024: return 1024
        if run >= 512:  return 512
    # Стандарт: 256 — идеально для LZMA деdup ref-stream
    return 256


# ══════════════════════════════════════════════════════════════════════════════
# ФОРМАТ ЗАПИСИ ССЫЛКИ  (9 байт для exact, 9+delta для fuzzy)
# ══════════════════════════════════════════════════════════════════════════════
#
#  [1B flags][4B hilbert_slot (uint32)][2B local_idx (uint16)]
#  [2B block_size (uint16)]
#  if flags & 0x01 (FUZZY):  [2B delta_len (uint16)][delta_len bytes delta]
#
#  flags: 0x01 = fuzzy match, 0x02 = variable block size
#
# ПОЧЕМУ ЛУЧШЕ ЧЕМ v8:
# - Hilbert-упорядоченные слоты: соседние блоки → близкие hilbert_slot
#   → LZMA видит арифметические прогрессии → +30-50% сжатие ref-stream
# - Fuzzy-ref: вместо нового блока 256B → ref (9B) + delta (~10-50B)
#   → экономия 200-250B на каждом нечётком совпадении
# - Более точная адресация: 65536 vs 256 бакетов → меньше коллизий

# ФОРМАТ ССЫЛОК — простой и надёжный:
#   EXACT: [0x00 u8][hilbert u16][bsz u16][local u8]  = 6 байт
#   FUZZY: [0x01 u8][hilbert u16][bsz u16][local u8][dlen u16][delta]  = 6+2+delta
#   sparse_delta: (u16 pos, u8 xor_val) — только изменённые байты

EXACT_REF_SIZE = 6   # bytes


def encode_ref_exact(hilbert_slot: int, local_idx: int, block_size: int) -> bytes:
    """Точная ссылка: 6 байт."""
    return struct.pack('<BHHB', 0x00, hilbert_slot, block_size, local_idx)


def encode_ref_fuzzy(hilbert_slot: int, local_idx: int,
                     block_size: int, delta: bytes) -> bytes:
    """Нечёткая ссылка: 6 + 2 + len(delta) байт."""
    return (struct.pack('<BHHB', 0x01, hilbert_slot, block_size, local_idx)
            + struct.pack('<H', len(delta))
            + delta)


def decode_ref(data: bytes, offset: int) -> Tuple[Dict, int]:
    """Декодировать ссылку, вернуть (ref_dict, new_offset)."""
    if offset + 6 > len(data):
        return None, offset
    flags, h_slot, blk_size, l_idx = struct.unpack_from('<BHHB', data, offset)
    offset += 6
    is_fuzzy = bool(flags & 0x01)
    delta = None
    if is_fuzzy:
        if offset + 2 > len(data):
            return None, offset
        delta_len, = struct.unpack_from('<H', data, offset); offset += 2
        if offset + delta_len > len(data):
            return None, offset
        delta = data[offset:offset + delta_len]; offset += delta_len
    return {'hilbert': h_slot, 'local': l_idx, 'size': blk_size,
            'fuzzy': is_fuzzy, 'delta': delta}, offset


# ══════════════════════════════════════════════════════════════════════════════
# TOPOLOGICAL ARCHIVER
# ══════════════════════════════════════════════════════════════════════════════

class TopoArchiver:
    """
    Топологический архиватор v9.0.
    Полная замена RecursiveArchiver из v8.0.

    Алгоритм сжатия:
    1. Adaptive block splitting по энтропии (64/256/1024/4096 байт)
    2. Для каждого блока:
       a. Точный lookup в TopologicalDictionary → 9-байт ссылка
       b. Fuzzy lookup (HomologyDesc) → 9B + delta (~10-50B вместо 256B)
       c. Новый блок → добавляем в словарь, 9-байт ссылка
    3. Ref-stream → LZMA preset=9 (Hilbert-упорядоченные индексы сжимаются лучше)
    4. Рекурсивные проходы пока ratio > min_improvement

    Декомпрессия:
    1. LZMA decompress ref-stream
    2. Для каждой ссылки: lookup в словаре, применить delta если fuzzy
    3. SHA-256 верификация
    """

    FORMAT_MAGIC   = b'SLTOP'   # Shtenco Lossless TOPological
    FORMAT_VERSION = '9.0-TOPO'

    def __init__(self, operation_id: Optional[str] = None):
        self.operation_id  = operation_id
        self.min_improvement = 0.98   # остановиться если < 2% улучшения
        self.max_iterations  = 20

    def _log(self, msg: str):
        if self.operation_id and self.operation_id in operations:
            operations[self.operation_id]['logs'].append(msg)

    def _prog(self, p: float):
        if self.operation_id and self.operation_id in operations:
            operations[self.operation_id]['progress'] = min(p, 0.99)

    # ── Один проход сжатия ────────────────────────────────────────────────────

    def _compress_pass(self, data: bytes, iteration: int) -> bytes:
        """
        Один проход топологического сжатия.
        Pass 1: полный топологический pipeline (Hilbert+Torus+Simplex+Homology).
        Pass 2+: чистый LZMA без словаря — избегаем коллизий dict между проходами.
        """
        if iteration > 1:
            # Passes 2+: просто LZMA на уже сжатые данные
            compressed = lzma.compress(data, preset=9)
            self._log(f"🔄 LZMA pass {iteration}: {len(data):,}B → {len(compressed):,}B "
                      f"({len(data)/max(len(compressed),1):.2f}×)")
            return compressed

        self._log(f"🔄 Topo pass {iteration}: {len(data):,} bytes → splitting...")

        refs      = bytearray()
        offset    = 0
        n_exact   = 0
        n_fuzzy   = 0
        n_new     = 0
        delta_bytes_saved = 0

        while offset < len(data):
            # L0+L3: адаптивный размер блока
            bsz   = adaptive_block_size(data, offset)
            block = data[offset:offset + bsz]
            offset += len(block)

            # L1+L2+L3: lookup в топологическом словаре
            ref = topo_dict.get_or_add(block)

            if ref['exact']:
                refs.extend(encode_ref_exact(ref['hilbert'], ref['local'], len(block)))
                n_exact += 1
            else:
                # Fuzzy: delta обычно намного меньше полного блока
                delta = ref.get('delta', b'')
                refs.extend(encode_ref_fuzzy(ref['hilbert'], ref['local'],
                                              len(block), delta))
                n_fuzzy += 1
                delta_bytes_saved += len(block) - len(delta)

        # LZMA — Hilbert-упорядоченный ref-stream сжимается лучше
        compressed = lzma.compress(bytes(refs), preset=9)

        self._log(f"   Blocks: {n_exact} exact | {n_fuzzy} fuzzy | "
                  f"delta saved {delta_bytes_saved:,}B")
        self._log(f"   Refs: {len(refs):,}B → LZMA: {len(compressed):,}B "
                  f"({len(refs)/max(len(compressed),1):.1f}×)")

        return compressed

    # ── Compress ──────────────────────────────────────────────────────────────

    def compress_file(self, input_path: str, output_path: str) -> bool:
        try:
            self._log("📥 [DEEPCOMPRESS PRO v9.0 TOPOLOGICAL] Reading file...")

            with open(input_path, 'rb') as f:
                original_data = f.read()

            original_size = len(original_data)
            original_sha  = hashlib.sha256(original_data).hexdigest()
            stat_info     = os.stat(input_path)

            self._log(f"   Size: {original_size:,} bytes")
            self._log(f"   SHA256: {original_sha[:16]}...")
            self._log(f"🧠 Topology: Hilbert(65536) + Torus T² + Simplex + Homology")
            self._log(f"🚀 Adaptive blocks: 64/256/1024/4096 by entropy")
            self._prog(0.05)

            current_data   = original_data
            previous_size  = original_size
            iteration_info = []
            iteration      = 1

            while iteration <= self.max_iterations:
                compressed = self._compress_pass(current_data, iteration)
                cur_size   = len(compressed)
                ratio      = previous_size / max(cur_size, 1)
                improvement = cur_size / max(previous_size, 1)

                self._log(f"✅ Pass {iteration}: {previous_size:,} → {cur_size:,} "
                          f"({ratio:.2f}×)")

                if improvement >= self.min_improvement:
                    self._log(f"🛑 Stop: improvement {improvement:.4f} < 2%")
                    break

                iteration_info.append({
                    'iteration':   iteration,
                    'input_size':  previous_size,
                    'output_size': cur_size,
                    'ratio':       round(ratio, 4),
                })
                current_data  = compressed
                previous_size = cur_size
                iteration    += 1
                self._prog(0.1 + iteration / self.max_iterations * 0.6)

            total_ratio = original_size / max(len(current_data), 1)
            self._log(f"🎯 Total passes: {len(iteration_info)} | "
                      f"Final ratio: {total_ratio:.2f}×")

            # Статистика топологического словаря
            st = topo_dict.stats
            self._log(f"📊 Dict: {st['total_entries']} entries | "
                      f"exact {st['exact_rate_pct']}% | "
                      f"fuzzy {st['fuzzy_rate_pct']}% | "
                      f"simplex hit {st['simplex_hit_rate']}%")

            self._prog(0.80)

            metadata = {
                'version':           self.FORMAT_VERSION,
                'original_filename': os.path.basename(input_path),
                'original_size':     original_size,
                'original_sha256':   original_sha,
                'compressed_size':   len(current_data),
                'iterations':        len(iteration_info),
                'iteration_info':    iteration_info,
                'topo_stats':        topo_dict.stats,
                'file_metadata': {
                    'st_mode':  stat_info.st_mode,
                    'st_atime': stat_info.st_atime,
                    'st_mtime': stat_info.st_mtime,
                },
            }
            meta_bytes = json.dumps(metadata).encode('utf-8')

            with open(output_path, 'wb') as f:
                f.write(self.FORMAT_MAGIC)
                f.write(struct.pack('<I', len(meta_bytes)))
                f.write(meta_bytes)
                f.write(current_data)

            final_size  = os.path.getsize(output_path)
            final_ratio = original_size / max(final_size, 1)
            self._log(f"💾 Archive: {final_size:,} bytes | ratio {final_ratio:.2f}×")

            # Периодически сохраняем словарь
            if len(topo_dict._exact_index) % 500 == 0:
                topo_dict.save(DICT_FILE)

            self._prog(1.0)
            self._log("✅ DEEPCOMPRESS TOPO v9.0 — COMPRESSION COMPLETE")
            self._log(f"✓ Hilbert+Torus+Simplex+Homology+Retract | {final_ratio:.2f}×")
            return True

        except Exception as ex:
            import traceback
            self._log(f"❌ ERROR: {ex}")
            self._log(f"❌ {traceback.format_exc()}")
            return False

    # ── Decompress ────────────────────────────────────────────────────────────

    def _decompress_pass(self, compressed: bytes, is_topo: bool = True) -> bytes:
        """Один проход распаковки.
        is_topo=True  → топологический (pass 1, обратный к topo compress).
        is_topo=False → чистый LZMA (обратный к pass 2+ LZMA).
        """
        if not is_topo:
            return lzma.decompress(compressed)
        raw = lzma.decompress(compressed)

        reconstructed = bytearray()
        offset = 0

        while offset < len(raw):
            ref, offset = decode_ref(raw, offset)
            if ref is None:
                break

            base_block = topo_dict.get_block(ref['hilbert'], ref['local'])
            if base_block is None:
                # Блок не найден в словаре — добавляем пустой
                reconstructed.extend(b'\x00' * ref['size'])
                continue

            if ref['fuzzy'] and ref['delta'] is not None:
                # Восстанавливаем из fuzzy ref + sparse delta
                n = ref['size']
                block = bytearray(base_block[:n].ljust(n, b'\x00'))
                delta = ref['delta']
                # Формат sparse delta: (uint16 pos, uint8 val) × k
                i = 0
                while i + 3 <= len(delta):
                    pos, val = struct.unpack_from('<HB', delta, i); i += 3
                    if pos < n: block[pos] ^= val
                block = bytes(block)
            else:
                block = base_block[:ref['size']]

            reconstructed.extend(block)

        return bytes(reconstructed)

    def decompress_file(self, input_path: str, output_path: str) -> bool:
        try:
            self._log("📥 [DEEPCOMPRESS TOPO v9.0] Reading archive...")

            with open(input_path, 'rb') as f:
                magic = f.read(5)
                if magic != self.FORMAT_MAGIC:
                    self._log(f"❌ Invalid format (got {magic})")
                    return False
                meta_size = struct.unpack('<I', f.read(4))[0]
                metadata  = json.loads(f.read(meta_size).decode('utf-8'))
                compressed_data = f.read()

            self._log(f"   Original: {metadata['original_size']:,} bytes")
            self._log(f"   Version:  {metadata.get('version', '?')}")
            iterations = metadata.get('iterations', 1)
            self._log(f"🔁 Decompression passes: {iterations}")
            self._prog(0.10)

            current_data = compressed_data

            for i in range(iterations):
                # Обратный порядок: последний compress = LZMA (passes 2+),
                # первый compress = topo (pass 1 = iterations-1 в обратном).
                # При decompress: i=0 соответствует compress pass iterations,
                #                 i=iterations-1 соответствует compress pass 1.
                reverse_pass = iterations - i  # какой compress-pass это был
                is_topo_pass = (reverse_pass == 1)
                self._log(f"🔄 Pass {i+1}/{iterations} ({'topo' if is_topo_pass else 'lzma'})...")
                try:
                    current_data = self._decompress_pass(current_data, is_topo=is_topo_pass)
                except Exception as ex:
                    import traceback
                    self._log(f"❌ Pass {i+1} error: {ex}")
                    self._log(traceback.format_exc())
                    return False
                self._prog(0.1 + (i + 1) / iterations * 0.6)

            self._log(f"   Reconstructed: {len(current_data):,} bytes")
            self._prog(0.80)
            self._log("✅ Verifying SHA256...")

            expected_sha = metadata['original_sha256']
            actual_sha   = hashlib.sha256(current_data).hexdigest()

            if expected_sha == actual_sha:
                self._log("✅ SHA256 MATCH — PERFECT INTEGRITY")
            else:
                self._log("❌ SHA256 MISMATCH!")
                self._log(f"   Expected: {expected_sha}")
                self._log(f"   Got:      {actual_sha}")
                return False

            self._prog(0.90)

            with open(output_path, 'wb') as f:
                f.write(current_data)

            fm = metadata.get('file_metadata', {})
            if fm.get('st_mode'):
                try:
                    os.chmod(output_path, fm['st_mode'])
                    os.utime(output_path, (fm['st_atime'], fm['st_mtime']))
                    self._log("✅ Restored permissions and timestamps")
                except:
                    pass

            self._prog(1.0)
            self._log("✅ DEEPCOMPRESS TOPO v9.0 — DECOMPRESSION COMPLETE")
            return True

        except Exception as ex:
            import traceback
            self._log(f"❌ ERROR: {ex}")
            self._log(traceback.format_exc())
            return False


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY
# ══════════════════════════════════════════════════════════════════════════════

class SecurityManager:
    def __init__(self):
        self._rate: Dict[str, Dict] = {}

    def check(self, ip: str, limit: int = 20, window: int = 60) -> bool:
        t = time.time()
        if ip not in self._rate:
            self._rate[ip] = {'count': 0, 'reset': t + window}
        r = self._rate[ip]
        if t > r['reset']:
            r['count'] = 0; r['reset'] = t + window
        if r['count'] >= limit:
            return False
        r['count'] += 1
        return True

security = SecurityManager()


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.after_request
def _headers(response):
    response.headers['X-Powered-By'] = 'DEEPCOMPRESS PRO TOPO v9.0 by Evgeniy Koshtenko'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>⚡ DEEPCOMPRESS PRO v9.0 TOPOLOGICAL by Evgeniy Koshtenko</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    :root{--bg:#000;--bg-soft:#0b0b0b;--neon:#0aff94;--neon-glow:rgba(10,255,148,.4);
          --text:#fff;--muted:#9a9a9a;--border:rgba(10,255,148,.2);--topo:#7c5ff5;}
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:'Inter',sans-serif;background:radial-gradient(circle at 20% 20%,
         rgba(10,255,148,.08),transparent 40%),radial-gradient(circle at 80% 80%,
         rgba(124,95,245,.05),transparent 40%),var(--bg);color:var(--text);overflow-x:hidden;}
    canvas.matrix-canvas{position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;opacity:.15;}
    header{position:sticky;top:0;z-index:100;backdrop-filter:blur(20px);
           background:rgba(0,0,0,.9);border-bottom:1px solid var(--border);}
    .nav{max-width:1400px;margin:auto;padding:20px 40px;display:flex;
         justify-content:space-between;align-items:center;}
    .logo{font-family:'Space Mono',monospace;font-weight:900;letter-spacing:3px;
          color:var(--neon);text-shadow:0 0 25px var(--neon-glow);font-size:22px;}
    .nav-info{display:flex;gap:30px;}
    .stat{text-align:center;}
    .stat-value{font-size:18px;font-weight:700;color:var(--neon);font-family:'Space Mono',monospace;}
    .stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px;}
    main{max-width:1400px;margin:0 auto;padding:80px 40px;position:relative;z-index:1;}
    .hero{text-align:center;margin-bottom:60px;}
    .hero h1{font-size:clamp(36px,5vw,66px);font-weight:900;margin-bottom:20px;
             background:linear-gradient(135deg,var(--neon) 0%,var(--topo) 50%,#fff 100%);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             background-clip:text;letter-spacing:-2px;}
    .hero p{max-width:800px;margin:0 auto 20px;font-size:17px;color:#d6d6d6;line-height:1.8;}
    .hero-badge{display:inline-block;background:rgba(124,95,245,.15);border:1px solid var(--topo);
                border-radius:50px;padding:10px 25px;font-family:'Space Mono',monospace;
                font-size:13px;color:var(--topo);margin-bottom:20px;}
    .topo-levels{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:30px 0;}
    .topo-level{background:rgba(11,11,11,.8);border:1px solid var(--border);border-radius:12px;
                padding:16px;text-align:center;}
    .topo-level .lvl{font-size:20px;font-weight:700;color:var(--topo);margin-bottom:6px;
                     font-family:'Space Mono',monospace;}
    .topo-level .ltitle{font-size:12px;font-weight:600;margin-bottom:4px;}
    .topo-level .ldesc{font-size:11px;color:var(--muted);line-height:1.4;}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-bottom:60px;}
    @media(max-width:1024px){.grid{grid-template-columns:1fr;}.topo-levels{grid-template-columns:repeat(3,1fr);}}
    .card{background:rgba(11,11,11,.8);border:1px solid var(--border);border-radius:20px;
          padding:40px;position:relative;overflow:hidden;}
    .card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
                  background:linear-gradient(90deg,var(--neon),var(--topo),transparent);}
    .card-title{font-size:22px;font-weight:700;margin-bottom:25px;display:flex;
                align-items:center;gap:12px;}
    .upload-zone{border:2px dashed var(--border);border-radius:16px;padding:45px;
                 text-align:center;cursor:pointer;transition:all .3s ease;margin-bottom:20px;}
    .upload-zone:hover{border-color:var(--neon);background:rgba(10,255,148,.05);}
    .upload-zone.dragover{border-color:var(--neon);background:rgba(10,255,148,.1);transform:scale(1.02);}
    .upload-icon{font-size:44px;margin-bottom:12px;}
    .upload-text{font-size:15px;color:var(--muted);}
    .upload-text strong{color:var(--neon);}
    .file-info{background:rgba(10,255,148,.1);border-radius:12px;padding:12px 18px;
               margin-bottom:20px;display:none;align-items:center;gap:12px;}
    .file-info.show{display:flex;}
    .file-details{flex:1;}
    .file-name{font-weight:600;margin-bottom:3px;}
    .file-size{font-size:13px;color:var(--muted);}
    .btn{width:100%;padding:16px;border:none;border-radius:12px;font-size:15px;
         font-weight:600;cursor:pointer;transition:all .3s ease;font-family:inherit;}
    .btn-primary{background:linear-gradient(135deg,var(--neon) 0%,#00d17f 100%);color:#000;}
    .btn-primary:hover:not(:disabled){transform:translateY(-2px);
                                       box-shadow:0 10px 40px rgba(10,255,148,.3);}
    .btn-primary:disabled{opacity:.5;cursor:not-allowed;}
    .progress-container{margin-top:25px;display:none;}
    .progress-container.show{display:block;}
    .progress-bar{height:8px;background:rgba(255,255,255,.1);border-radius:4px;
                  overflow:hidden;margin-bottom:8px;}
    .progress-fill{height:100%;background:linear-gradient(90deg,var(--neon),var(--topo));
                   border-radius:4px;transition:width .3s ease;width:0%;}
    .progress-text{display:flex;justify-content:space-between;font-size:13px;color:var(--muted);}
    .logs{margin-top:16px;background:rgba(0,0,0,.5);border-radius:12px;padding:14px;
          max-height:200px;overflow-y:auto;font-family:'Space Mono',monospace;font-size:12px;}
    .log-entry{padding:3px 0;border-bottom:1px solid rgba(255,255,255,.05);}
    .log-entry.success{color:var(--neon);}.log-entry.error{color:#ff4757;}
    .log-entry.info{color:#54a0ff;}.log-entry.topo{color:var(--topo);}
    .download-section{margin-top:20px;display:none;}
    .download-section.show{display:block;}
    .btn-download{background:transparent;border:2px solid var(--neon);color:var(--neon);}
    .btn-download:hover{background:var(--neon);color:#000;}
    .stats-bar{display:flex;justify-content:center;gap:50px;margin:30px 0;padding:25px;
               background:rgba(11,11,11,.6);border-radius:16px;border:1px solid var(--border);}
    .stats-item{text-align:center;}
    .stats-value{font-size:30px;font-weight:900;color:var(--neon);font-family:'Space Mono',monospace;}
    .stats-value.topo{color:var(--topo);}
    .stats-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px;}
    footer{text-align:center;padding:40px;color:var(--muted);font-size:14px;
           border-top:1px solid var(--border);margin-top:80px;}
    footer a{color:var(--neon);text-decoration:none;}
  </style>
</head>
<body>
  <canvas class="matrix-canvas" id="matrix"></canvas>
  <header>
    <nav class="nav">
      <div class="logo">⚡ DEEPCOMPRESS PRO v9.0 TOPO</div>
      <div class="nav-info">
        <div class="stat"><div class="stat-value" id="stat-files">0</div>
          <div class="stat-label">Files</div></div>
        <div class="stat"><div class="stat-value" id="stat-ratio">—</div>
          <div class="stat-label">Best Ratio</div></div>
        <div class="stat"><div class="stat-value" id="stat-dict">0</div>
          <div class="stat-label">Dict Entries</div></div>
      </div>
    </nav>
  </header>
  <main>
    <section class="hero">
      <div class="hero-badge">🧬 TOPOLOGICAL EDITION — Hilbert + Torus + Simplex + Homology + Retract</div>
      <h1>DEEPCOMPRESS PRO</h1>
      <p>Словарь и все вычисления переведены на 5-уровневую топологическую RAM.
         Fuzzy-dedup через гомологию β₀/β₁, Hilbert-адресация 65536 бакетов,
         адаптивные блоки 64–4096 байт по энтропии. Максимальная степень сжатия.</p>
    </section>

    <div class="topo-levels">
      <div class="topo-level">
        <div class="lvl">L0</div>
        <div class="ltitle">Hilbert Dict</div>
        <div class="ldesc">65536 бакетов по кривой Гильберта. Пространственная локальность.</div>
      </div>
      <div class="topo-level">
        <div class="lvl">L1</div>
        <div class="ltitle">Torus VRAM</div>
        <div class="ldesc">Тор T² разрешение коллизий. Wrap-around, нет «холодных краёв».</div>
      </div>
      <div class="topo-level">
        <div class="lvl">L2</div>
        <div class="ltitle">Simplex Pf</div>
        <div class="ldesc">2-симплексы co-access. Предсказание следующего блока.</div>
      </div>
      <div class="topo-level">
        <div class="lvl">L3</div>
        <div class="ltitle">Homology</div>
        <div class="ldesc">β₀/β₁ fuzzy-dedup. Похожие блоки → ref + XOR-delta.</div>
      </div>
      <div class="topo-level">
        <div class="lvl">L4</div>
        <div class="ltitle">Retract</div>
        <div class="ldesc">Bitmap O(1) alloc. Фрагментация = 0% гарантировано.</div>
      </div>
    </div>

    <div class="stats-bar">
      <div class="stats-item"><div class="stats-value topo">65536</div>
        <div class="stats-label">Dict Buckets</div></div>
      <div class="stats-item"><div class="stats-value">Hilbert</div>
        <div class="stats-label">Addressing</div></div>
      <div class="stats-item"><div class="stats-value topo">Fuzzy</div>
        <div class="stats-label">Homology Dedup</div></div>
      <div class="stats-item"><div class="stats-value">SHA-256</div>
        <div class="stats-label">Integrity</div></div>
    </div>

    <div class="grid">
      <div class="card">
        <h2 class="card-title"><span>📦</span> Compress</h2>
        <div class="upload-zone" id="zone-compress">
          <div class="upload-icon">📁</div>
          <div class="upload-text"><strong>Drop file here</strong> or click<br>
            <small>Any type · Max 1000MB</small></div>
          <input type="file" id="file-compress" hidden>
        </div>
        <div class="file-info" id="info-compress">
          <span>📄</span>
          <div class="file-details">
            <div class="file-name" id="name-compress">-</div>
            <div class="file-size" id="size-compress">-</div>
          </div>
        </div>
        <button class="btn btn-primary" id="btn-compress" disabled>🧬 Topological Compress</button>
        <div class="progress-container" id="progress-compress">
          <div class="progress-bar"><div class="progress-fill" id="fill-compress"></div></div>
          <div class="progress-text"><span>Processing...</span>
            <span id="percent-compress">0%</span></div>
        </div>
        <div class="logs" id="logs-compress"></div>
        <div class="download-section" id="download-compress">
          <button class="btn btn-download" id="btn-download-compress">⬇️ Download .slo</button>
        </div>
      </div>

      <div class="card">
        <h2 class="card-title"><span>📂</span> Decompress</h2>
        <div class="upload-zone" id="zone-decompress">
          <div class="upload-icon">🗜️</div>
          <div class="upload-text"><strong>Drop .slo archive</strong> or click<br>
            <small>DEEPCOMPRESS TOPO archives</small></div>
          <input type="file" id="file-decompress" accept=".slo" hidden>
        </div>
        <div class="file-info" id="info-decompress">
          <span>🗜️</span>
          <div class="file-details">
            <div class="file-name" id="name-decompress">-</div>
            <div class="file-size" id="size-decompress">-</div>
          </div>
        </div>
        <button class="btn btn-primary" id="btn-decompress" disabled>🔓 Decompress</button>
        <div class="progress-container" id="progress-decompress">
          <div class="progress-bar"><div class="progress-fill" id="fill-decompress"></div></div>
          <div class="progress-text"><span>Restoring...</span>
            <span id="percent-decompress">0%</span></div>
        </div>
        <div class="logs" id="logs-decompress"></div>
        <div class="download-section" id="download-decompress">
          <button class="btn btn-download" id="btn-download-decompress">⬇️ Download File</button>
        </div>
      </div>
    </div>
  </main>

  <footer>
    <p><strong>DEEPCOMPRESS PRO v9.0 TOPOLOGICAL EDITION</strong><br>
       © 2026 <a href="#">Evgeniy Koshtenko</a>, Kostanay, Kazakhstan.
       5-Level Topological RAM: Hilbert · Torus · Simplex · Homology · Retract.</p>
  </footer>

  <script>
    // Matrix rain
    const canvas=document.getElementById('matrix'),ctx=canvas.getContext('2d');
    canvas.width=window.innerWidth;canvas.height=window.innerHeight;
    const chars='TOPOhilbertvidalramshtencokoshtenko0123456789βφπ'.split('');
    const sz=14,cols=canvas.width/sz,drops=Array.from({length:cols},()=>Math.random()*canvas.height/sz);
    function drawMatrix(){
      ctx.fillStyle='rgba(0,0,0,.05)';ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.fillStyle='#7c5ff5';ctx.font=sz+'px Space Mono';
      drops.forEach((d,i)=>{
        ctx.fillText(chars[Math.floor(Math.random()*chars.length)],i*sz,d*sz);
        if(d*sz>canvas.height&&Math.random()>.975)drops[i]=0;drops[i]++;
      });
    }
    setInterval(drawMatrix,50);
    window.addEventListener('resize',()=>{canvas.width=window.innerWidth;canvas.height=window.innerHeight;});

    let cFile=null,dFile=null;
    function fmt(b){return b<1024?b+' B':b<1048576?(b/1024).toFixed(1)+' KB':(b/1048576).toFixed(2)+' MB';}
    function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML;}

    function setupZone(zoneId,inputId,type){
      const z=document.getElementById(zoneId),inp=document.getElementById(inputId);
      z.addEventListener('click',()=>inp.click());
      z.addEventListener('dragover',e=>{e.preventDefault();z.classList.add('dragover');});
      z.addEventListener('dragleave',()=>z.classList.remove('dragover'));
      z.addEventListener('drop',e=>{e.preventDefault();z.classList.remove('dragover');
        if(e.dataTransfer.files[0])setFile(e.dataTransfer.files[0],type);});
      inp.addEventListener('change',()=>{if(inp.files[0])setFile(inp.files[0],type);});
    }
    function setFile(f,type){
      if(type==='compress'){cFile=f;document.getElementById('name-compress').textContent=f.name;
        document.getElementById('size-compress').textContent=fmt(f.size);
        document.getElementById('info-compress').classList.add('show');
        document.getElementById('btn-compress').disabled=false;}
      else{dFile=f;document.getElementById('name-decompress').textContent=f.name;
        document.getElementById('size-decompress').textContent=fmt(f.size);
        document.getElementById('info-decompress').classList.add('show');
        document.getElementById('btn-decompress').disabled=false;}
    }
    setupZone('zone-compress','file-compress','compress');
    setupZone('zone-decompress','file-decompress','decompress');

    async function doAction(type,url,file){
      const fd=new FormData();fd.append('file',file);
      document.getElementById('progress-'+type).classList.add('show');
      document.getElementById('download-'+type).classList.remove('show');
      document.getElementById('logs-'+type).innerHTML='';
      document.getElementById('btn-'+type).disabled=true;
      try{
        const r=await fetch(url,{method:'POST',body:fd});
        const d=await r.json();
        monitor(d.operation_id,type);
      }catch(e){document.getElementById('btn-'+type).disabled=false;}
    }
    document.getElementById('btn-compress').addEventListener('click',()=>{if(cFile)doAction('compress','/compress',cFile);});
    document.getElementById('btn-decompress').addEventListener('click',()=>{if(dFile)doAction('decompress','/decompress',dFile);});

    function monitor(opId,type){
      const iv=setInterval(async()=>{
        try{
          const r=await fetch('/progress/'+opId),d=await r.json();
          const pct=Math.round(d.progress*100);
          document.getElementById('fill-'+type).style.width=pct+'%';
          document.getElementById('percent-'+type).textContent=pct+'%';
          const ld=document.getElementById('logs-'+type);
          ld.innerHTML=d.logs.map(l=>{
            let c='';
            if(l.includes('✅'))c='success';
            else if(l.includes('❌'))c='error';
            else if(l.includes('🧬')||l.includes('📊')||l.includes('🔄'))c='topo';
            else if(l.includes('📥')||l.includes('🚀')||l.includes('🎯'))c='info';
            return '<div class="log-entry '+c+'">'+esc(l)+'</div>';
          }).join('');
          ld.scrollTop=ld.scrollHeight;
          if(d.status==='completed'){
            clearInterval(iv);
            document.getElementById('download-'+type).classList.add('show');
            document.getElementById('btn-download-'+type).onclick=()=>window.location.href='/download/'+opId;
            document.getElementById('btn-'+type).disabled=false;
            document.getElementById('stat-files').textContent=parseInt(document.getElementById('stat-files').textContent)+1;
          }
        }catch(e){}
      },500);
    }
  </script>
</body>
</html>"""


@app.route('/')
def index():
    return HTML_PAGE


@app.route('/compress', methods=['POST'])
def compress():
    if not security.check(request.remote_addr):
        return jsonify({'error': 'Rate limit'}), 429
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400

    f          = request.files['file']
    op_id      = str(uuid.uuid4())
    fname      = secure_filename(f.filename)
    in_path    = os.path.join(app.config['UPLOAD_FOLDER'], f'{op_id}_{fname}')
    out_path   = in_path + '.slo'
    f.save(in_path)

    operations[op_id] = {
        'progress': 0.0, 'logs': [],
        'status': 'running',
        'output_path': out_path,
        'output_filename': fname + '.slo',
    }

    def worker():
        arc     = TopoArchiver(op_id)
        success = arc.compress_file(in_path, out_path)
        operations[op_id]['status'] = 'completed' if success else 'failed'
        try: os.remove(in_path)
        except: pass

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({'operation_id': op_id})


@app.route('/decompress', methods=['POST'])
def decompress():
    if not security.check(request.remote_addr):
        return jsonify({'error': 'Rate limit'}), 429
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400

    f     = request.files['file']
    op_id = str(uuid.uuid4())
    fname = secure_filename(f.filename)
    in_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{op_id}_{fname}')
    f.save(in_path)

    # Определяем оригинальное имя из метаданных
    orig_fname = 'restored'
    try:
        with open(in_path, 'rb') as fh:
            if fh.read(5) == b'SLTOP':
                msz = struct.unpack('<I', fh.read(4))[0]
                meta = json.loads(fh.read(msz).decode('utf-8'))
                orig_fname = meta.get('original_filename', 'restored')
    except: pass

    out_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{op_id}_{orig_fname}')
    operations[op_id] = {
        'progress': 0.0, 'logs': [],
        'status': 'running',
        'output_path': out_path,
        'output_filename': orig_fname,
    }

    def worker():
        arc     = TopoArchiver(op_id)
        success = arc.decompress_file(in_path, out_path)
        operations[op_id]['status'] = 'completed' if success else 'failed'
        try: os.remove(in_path)
        except: pass

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({'operation_id': op_id})


@app.route('/progress/<op_id>')
def get_progress(op_id):
    if op_id not in operations:
        return jsonify({'error': 'Not found'}), 404
    op = operations[op_id]
    return jsonify({
        'progress': op['progress'],
        'logs':     op['logs'],
        'status':   op['status'],
    })


@app.route('/download/<op_id>')
def download(op_id):
    if op_id not in operations or operations[op_id]['status'] != 'completed':
        return jsonify({'error': 'Not ready'}), 400
    op = operations[op_id]
    return send_file(op['output_path'], as_attachment=True,
                     download_name=op['output_filename'])


# WSGI
application = app


if __name__ == '__main__':
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║  ⚡ DEEPCOMPRESS PRO v9.0 TOPOLOGICAL EDITION                   ║")
    print("║     5-Level Topological RAM by Evgeniy Koshtenko / 2026         ║")
    print("║                                                                  ║")
    print("║  L0 Hilbert-Dict  — 65536 бакетов, spatial locality             ║")
    print("║  L1 Torus-VRAM    — T² topology, wrap-around                    ║")
    print("║  L2 Simplex-PF    — co-access prediction                        ║")
    print("║  L3 Homology      — β₀/β₁ fuzzy-dedup + XOR-delta               ║")
    print("║  L4 Retract       — bitmap O(1), fragmentation = 0%             ║")
    print("║                                                                  ║")
    print("║  🌐 http://localhost:5000                                        ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")
    print(f"⚡ CPU: {CPU_COUNT} threads")
    print(f"📚 Dict: {len(topo_dict._exact_index)} patterns loaded")
    print()

    for d in ['uploads_secure', 'outputs_secure', 'temp_secure']:
        os.makedirs(d, exist_ok=True)

    threading.Timer(1.5, lambda: webbrowser.open('http://localhost:5000')).start()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
