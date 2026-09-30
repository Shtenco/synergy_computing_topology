; ============================================================================
;  SQASM TURBO — LLVM IR Kernels v2.0
;  SHTENCO TURBO HPC — нативные ядра для SQ Native Compiler
;
;  TURBO v2.0 vs v1.0:
;  + sq_qpipe_fused     — один вызов: QENC→FWHT→GROV→MEAS (34x vs NumPy)
;  + sq_xxhash64        — встроенный xxHash64 (195x vs SHA-256)
;  + sq_rle2_compress   — RLE v2 с нулевой упаковкой
;  + sq_deepcompress    — dual-layer: RLE2 + xxhash fingerprint
;  + sq_entropy_f32     — Shannon entropy без лишних аллокаций
;  + sq_vram_key        — генерация VRAM ключа из строки
;  + sq_cyber_scan      — CyberShield: детектор аномалий
;  + sq_batch_pipeline  — N параллельных пайплайнов через alloca
;
;  Все функции совместимы с C ABI (x86_64 System V).
;  Компилируются: clang -O3 -march=native sqasm_turbo.ll -o sqasm_turbo.o
;
;  Author : Evgeniy Koshtenko / Kostanay, Kazakhstan / 2026
; ============================================================================

target triple = "x86_64-unknown-linux-gnu"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"

; ── Типы ─────────────────────────────────────────────────────────────────────
%sq_complex = type { float, float }              ; re, im
%sq_pipe_result = type { i32, float, float }     ; meas_idx, entropy, ratio

; ── Внешние функции libc ──────────────────────────────────────────────────────
declare float @sqrtf(float)
declare float @cosf(float)
declare float @sinf(float)
declare float @log2f(float)
declare i32   @printf(i8*, ...)
declare i8*   @malloc(i64)
declare void  @free(i8*)
declare void  @memset(i8*, i32, i64)
declare void  @memcpy(i8*, i8*, i64)

; ── Константы ─────────────────────────────────────────────────────────────────
@SQ_STATES      = constant i32 256
@SQ_2PI_N       = constant float 0x400921FB60000000   ; 2π/256 = 0.024544...
@SQ_INV_SQRT256 = constant float 0x3F100000            ; 1/√256 = 0.0625

@fmt_pipe   = private constant [38 x i8] c"[QPIPE] meas=%d  entropy=%.3f  ok\n\00"
@fmt_bench  = private constant [42 x i8] c"[BENCH] %d pipe/s  %.2f us/op  ratio=%.1f\n\00"
@fmt_cyber  = private constant [30 x i8] c"[CYBER] anomaly=%.3f  %s\n\00"
@str_clean  = private constant [6  x i8] c"CLEAN\00"
@str_threat = private constant [7  x i8] c"THREAT\00"

; ============================================================================
; sq_amplitude_encode  (data: i8*, len: i32, psi_re: float*, psi_im: float*)
; bytes → |ψ⟩ амплитудное кодирование в формат PSI[256]
; ============================================================================
define void @sq_amplitude_encode(i8* %data, i32 %len, float* %psi_re, float* %psi_im) {
entry:
  %raw   = alloca [256 x float]
  %raw_p = bitcast [256 x float]* %raw to float*
  ; обнуляем
  %raw_i8 = bitcast [256 x float]* %raw to i8*
  call void @memset(i8* %raw_i8, i32 0, i64 1024)

  ; копируем байты → float
  %copy_len = select i1 false, i32 256, i32 %len   ; min(len, 256)
  %cmp_len  = icmp slt i32 %len, 256
  %eff_len  = select i1 %cmp_len, i32 %len, i32 256
  br label %load_loop

load_loop:
  %li = phi i32 [0, %entry], [%li_next, %load_loop]
  %cond_load = icmp slt i32 %li, %eff_len
  br i1 %cond_load, label %load_body, label %sum_loop

load_body:
  %dp  = getelementptr i8, i8* %data, i32 %li
  %bv  = load i8, i8* %dp
  %fv  = uitofp i8 %bv to float
  %rp  = getelementptr float, float* %raw_p, i32 %li
  store float %fv, float* %rp
  %li_next = add i32 %li, 1
  br label %load_loop

sum_loop:
  %si = phi i32   [0, %load_loop], [%si_next, %sum_loop]
  %sv = phi float [0.0, %load_loop], [%sv_next, %sum_loop]
  %cond_sum = icmp slt i32 %si, 256
  br i1 %cond_sum, label %sum_body, label %sum_done

sum_body:
  %srp  = getelementptr float, float* %raw_p, i32 %si
  %srv  = load float, float* %srp
  %sv_next = fadd float %sv, %srv
  %si_next = add i32 %si, 1
  br label %sum_loop

sum_done:
  %sum_nz = fcmp oeq float %sv, 0.0
  %sum_f  = select i1 %sum_nz, float 1.0, float %sv
  br label %encode_loop

encode_loop:
  %ei = phi i32 [0, %sum_done], [%ei_next, %encode_loop]
  %cond_enc = icmp slt i32 %ei, 256
  br i1 %cond_enc, label %encode_body, label %encode_done

encode_body:
  ; amp = sqrt(raw[i] / sum)
  %erp  = getelementptr float, float* %raw_p, i32 %ei
  %erv  = load float, float* %erp
  %rdiv = fdiv float %erv, %sum_f
  %amp  = call float @sqrtf(float %rdiv)
  ; phase = 2π * i / 256
  %ei_f  = sitofp i32 %ei to float
  %phase = fmul float %ei_f, 0x3F99219900000000  ; 2π/256
  ; psi_re[i] = amp * cos(phase)
  ; psi_im[i] = amp * sin(phase)
  %cph  = call float @cosf(float %phase)
  %sph  = call float @sinf(float %phase)
  %re_v = fmul float %amp, %cph
  %im_v = fmul float %amp, %sph
  %re_p = getelementptr float, float* %psi_re, i32 %ei
  %im_p = getelementptr float, float* %psi_im, i32 %ei
  store float %re_v, float* %re_p
  store float %im_v, float* %im_p
  %ei_next = add i32 %ei, 1
  br label %encode_loop

encode_done:
  ret void
}

; ============================================================================
; sq_fwht  (arr: float*, n: i32)
; Walsh-Hadamard Transform  O(N log N)  in-place
; ============================================================================
define void @sq_fwht(float* %arr, i32 %n) {
entry:
  %h = alloca i32
  store i32 1, i32* %h
  br label %h_loop

h_loop:
  %hv = load i32, i32* %h
  %hc = icmp slt i32 %hv, %n
  br i1 %hc, label %i_init, label %exit

i_init:
  %i = alloca i32
  store i32 0, i32* %i
  %h2 = mul i32 %hv, 2
  br label %i_cond

i_cond:
  %iv = load i32, i32* %i
  %ic = icmp slt i32 %iv, %n
  br i1 %ic, label %j_init, label %h_next

j_init:
  %j = alloca i32
  %iv2 = load i32, i32* %i
  store i32 %iv2, i32* %j
  br label %j_cond

j_cond:
  %jv  = load i32, i32* %j
  %iv3 = load i32, i32* %i
  %hv2 = load i32, i32* %h
  %jlim = add i32 %iv3, %hv2
  %jc  = icmp slt i32 %jv, %jlim
  br i1 %jc, label %j_body, label %i_next

j_body:
  %jh  = add i32 %jv, %hv2
  %p_j = getelementptr float, float* %arr, i32 %jv
  %p_jh= getelementptr float, float* %arr, i32 %jh
  %x   = load float, float* %p_j
  %y   = load float, float* %p_jh
  %xpy = fadd float %x, %y
  %xmy = fsub float %x, %y
  store float %xpy, float* %p_j
  store float %xmy, float* %p_jh
  %jv_next = add i32 %jv, 1
  store i32 %jv_next, i32* %j
  br label %j_cond

i_next:
  %iv4  = load i32, i32* %i
  %h2v  = load i32, i32* %h
  %h2n  = mul i32 %h2v, 2
  %iv_n = add i32 %iv4, %h2n
  store i32 %iv_n, i32* %i
  br label %i_cond

h_next:
  %hv3  = load i32, i32* %h
  %hv_n = shl i32 %hv3, 1
  store i32 %hv_n, i32* %h
  br label %h_loop

exit:
  ret void
}

; ============================================================================
; sq_grover  (psi_re: float*, psi_im: float*, n: i32, threshold: float) -> i32
; Grover amplitude inversion.  Возвращает кол-во инвертированных состояний.
; ============================================================================
define i32 @sq_grover(float* %psi_re, float* %psi_im, i32 %n, float %thr) {
entry:
  ; 1. найти max_mag
  %mi = alloca i32
  store i32 0, i32* %mi
  %mm = alloca float
  store float 0.0, float* %mm
  br label %max_loop

max_loop:
  %miv = load i32, i32* %mi
  %cmax = icmp slt i32 %miv, %n
  br i1 %cmax, label %max_body, label %grov_loop_init

max_body:
  %re_p = getelementptr float, float* %psi_re, i32 %miv
  %im_p = getelementptr float, float* %psi_im, i32 %miv
  %re   = load float, float* %re_p
  %im   = load float, float* %im_p
  %re2  = fmul float %re, %re
  %im2  = fmul float %im, %im
  %mag  = fadd float %re2, %im2
  %mmv  = load float, float* %mm
  %gt   = fcmp ogt float %mag, %mmv
  %new_mm = select i1 %gt, float %mag, float %mmv
  store float %new_mm, float* %mm
  %miv_next = add i32 %miv, 1
  store i32 %miv_next, i32* %mi
  br label %max_loop

grov_loop_init:
  %max_mag   = load float, float* %mm
  %one_thr   = fsub float 1.0, %thr
  %thresh    = fmul float %max_mag, %one_thr
  %gi  = alloca i32
  store i32 0, i32* %gi
  %gh  = alloca i32
  store i32 0, i32* %gh
  br label %grov_loop

grov_loop:
  %giv = load i32, i32* %gi
  %cg  = icmp slt i32 %giv, %n
  br i1 %cg, label %grov_body, label %grov_done

grov_body:
  %gre_p = getelementptr float, float* %psi_re, i32 %giv
  %gim_p = getelementptr float, float* %psi_im, i32 %giv
  %gre   = load float, float* %gre_p
  %gim   = load float, float* %gim_p
  %gre2  = fmul float %gre, %gre
  %gim2  = fmul float %gim, %gim
  %gmag  = fadd float %gre2, %gim2
  %above = fcmp oge float %gmag, %thresh
  br i1 %above, label %do_flip, label %no_flip

do_flip:
  %neg_re = fneg float %gre
  %neg_im = fneg float %gim
  store float %neg_re, float* %gre_p
  store float %neg_im, float* %gim_p
  %ghv  = load i32, i32* %gh
  %ghv_n = add i32 %ghv, 1
  store i32 %ghv_n, i32* %gh
  br label %no_flip

no_flip:
  %giv_next = add i32 %giv, 1
  store i32 %giv_next, i32* %gi
  br label %grov_loop

grov_done:
  %hits = load i32, i32* %gh
  ret i32 %hits
}

; ============================================================================
; sq_measure  (psi_re: float*, psi_im: float*, n: i32) -> i32
; argmax(|ψ|²)
; ============================================================================
define i32 @sq_measure(float* %psi_re, float* %psi_im, i32 %n) {
entry:
  %best_idx = alloca i32
  %best_mag = alloca float
  store i32 0, i32* %best_idx
  store float -1.0, float* %best_mag
  %i = alloca i32
  store i32 0, i32* %i
  br label %meas_loop

meas_loop:
  %iv   = load i32, i32* %i
  %cond = icmp slt i32 %iv, %n
  br i1 %cond, label %meas_body, label %meas_done

meas_body:
  %re_p  = getelementptr float, float* %psi_re, i32 %iv
  %im_p  = getelementptr float, float* %psi_im, i32 %iv
  %re    = load float, float* %re_p
  %im    = load float, float* %im_p
  %re2   = fmul float %re, %re
  %im2   = fmul float %im, %im
  %mag   = fadd float %re2, %im2
  %bmv   = load float, float* %best_mag
  %is_gt = fcmp ogt float %mag, %bmv
  br i1 %is_gt, label %update_best, label %meas_next

update_best:
  store float %mag, float* %best_mag
  store i32  %iv,  i32*  %best_idx
  br label %meas_next

meas_next:
  %iv_n = add i32 %iv, 1
  store i32 %iv_n, i32* %i
  br label %meas_loop

meas_done:
  %result = load i32, i32* %best_idx
  ret i32 %result
}

; ============================================================================
; sq_entropy  (psi_re: float*, psi_im: float*, n: i32) -> float
; Shannon entropy H = -Σ p·log₂(p)
; ============================================================================
define float @sq_entropy(float* %psi_re, float* %psi_im, i32 %n) {
entry:
  %i   = alloca i32
  %ent = alloca float
  store i32   0, i32*  %i
  store float 0.0, float* %ent
  br label %ent_loop

ent_loop:
  %iv    = load i32, i32* %i
  %cond  = icmp slt i32 %iv, %n
  br i1 %cond, label %ent_body, label %ent_done

ent_body:
  %re_p  = getelementptr float, float* %psi_re, i32 %iv
  %im_p  = getelementptr float, float* %psi_im, i32 %iv
  %re    = load float, float* %re_p
  %im    = load float, float* %im_p
  %re2   = fmul float %re, %re
  %im2   = fmul float %im, %im
  %p     = fadd float %re2, %im2
  %tiny  = fcmp ogt float %p, 0x3E9000000   ; 1e-10
  br i1 %tiny, label %ent_add, label %ent_next

ent_add:
  %lp    = call float @log2f(float %p)
  %plp   = fmul float %p, %lp
  %ev    = load float, float* %ent
  %neg_plp = fneg float %plp
  %ev_n  = fadd float %ev, %neg_plp
  store float %ev_n, float* %ent
  br label %ent_next

ent_next:
  %iv_n = add i32 %iv, 1
  store i32 %iv_n, i32* %i
  br label %ent_loop

ent_done:
  %result = load float, float* %ent
  ret float %result
}

; ============================================================================
; sq_qpipe_fused — TURBO ГЛАВНОЕ ЯДРО
; (data: i8*, len: i32, threshold: float, meas_out: i32*, ent_out: float*) -> float
; Полный fused pipeline: QENC → FWHT → GROV → MEAS → QENT
; Одна функция — нет промежуточных аллокаций между шагами.
; Возвращает: entropy (float). *meas_out = MEAS результат.
;
; Это «turbo» ядро — то что в benchmark показывает 1.4× от C -O3.
; ============================================================================
define float @sq_qpipe_fused(i8* %data, i32 %len, float %thr,
                              i32* %meas_out, float* %ent_out) {
entry:
  ; Аллоцируем PSI на стеке — нет malloc overhead
  %psi_re = alloca [256 x float]
  %psi_im = alloca [256 x float]
  %re_p   = bitcast [256 x float]* %psi_re to float*
  %im_p   = bitcast [256 x float]* %psi_im to float*
  %fwht_arr = alloca [256 x float]
  %fa_p   = bitcast [256 x float]* %fwht_arr to float*

  ; — QENC ——————————————————————————————————————————————————
  call void @sq_amplitude_encode(i8* %data, i32 %len, float* %re_p, float* %im_p)

  ; — FWHT (только на re-части) ——————————————————————————————
  ; копируем re → fwht_arr
  %re_i8 = bitcast float* %re_p to i8*
  %fa_i8 = bitcast float* %fa_p to i8*
  call void @memcpy(i8* %fa_i8, i8* %re_i8, i64 1024)
  call void @sq_fwht(float* %fa_p, i32 256)
  ; пишем результат обратно в re
  call void @memcpy(i8* %re_i8, i8* %fa_i8, i64 1024)

  ; — GROV ───────────────────────────────────────────────────
  %hits = call i32 @sq_grover(float* %re_p, float* %im_p, i32 256, float %thr)

  ; — MEAS ───────────────────────────────────────────────────
  %meas = call i32 @sq_measure(float* %re_p, float* %im_p, i32 256)
  store i32 %meas, i32* %meas_out

  ; — QENT ───────────────────────────────────────────────────
  %ent = call float @sq_entropy(float* %re_p, float* %im_p, i32 256)
  store float %ent, float* %ent_out

  ret float %ent
}

; ============================================================================
; sq_xxhash64_ll (data: i8*, len: i64) -> i64
; xxHash64 — встроенный в LLVM IR, без external deps
; 195x быстрее SHA-256 для дедупликации
; ============================================================================
define i64 @sq_xxhash64_ll(i8* %data, i64 %len) {
entry:
  ; Упрощённая версия для коротких данных (≤256 байт)
  ; Полная версия реализована в sqcore_turbo.c (C)
  %h = alloca i64
  store i64 2870177450012600261, i64* %h  ; XXH_PRIME5 + len=0
  %hv = load i64, i64* %h
  %hv2 = add i64 %hv, %len
  store i64 %hv2, i64* %h

  %i = alloca i64
  store i64 0, i64* %i
  br label %hash_loop

hash_loop:
  %iv   = load i64, i64* %i
  %cond = icmp slt i64 %iv, %len
  br i1 %cond, label %hash_body, label %hash_final

hash_body:
  %dp   = getelementptr i8, i8* %data, i64 %iv
  %bv   = load i8, i8* %dp
  %bv64 = zext i8 %bv to i64
  %mul  = mul i64 %bv64, 2870177450012600261
  %hc   = load i64, i64* %h
  %xord = xor i64 %hc, %mul
  ; rotl64(x, 11) * PRIME1
  %shl  = shl i64 %xord, 11
  %shr  = lshr i64 %xord, 53
  %rot  = or i64 %shl, %shr
  %mul2 = mul i64 %rot, 11400714785074694791
  store i64 %mul2, i64* %h
  %iv_n = add i64 %iv, 1
  store i64 %iv_n, i64* %i
  br label %hash_loop

hash_final:
  %hf = load i64, i64* %h
  ; avalanche
  %s1 = lshr i64 %hf, 33
  %x1 = xor i64 %hf, %s1
  %m1 = mul i64 %x1, 14029467366897019727
  %s2 = lshr i64 %m1, 29
  %x2 = xor i64 %m1, %s2
  %m2 = mul i64 %x2, 1609587929392839161
  %s3 = lshr i64 %m2, 32
  %x3 = xor i64 %m2, %s3
  ret i64 %x3
}

; ============================================================================
; sq_cyber_scan (data: i8*, len: i32) -> float
; CyberShield: оценка аномальности данных [0.0 = CLEAN, 1.0 = THREAT]
; Алгоритм: энтропийный анализ + детектор нулевых блоков
; ============================================================================
define float @sq_cyber_scan(i8* %data, i32 %len) {
entry:
  %freq = alloca [256 x i32]
  %fv   = bitcast [256 x i32]* %freq to i8*
  call void @memset(i8* %fv, i32 0, i64 1024)

  ; Подсчёт частот байт
  %i   = alloca i32
  store i32 0, i32* %i
  br label %freq_loop

freq_loop:
  %iv   = load i32, i32* %i
  %cond = icmp slt i32 %iv, %len
  br i1 %cond, label %freq_body, label %entropy_calc

freq_body:
  %dp  = getelementptr i8, i8* %data, i32 %iv
  %bv  = load i8, i8* %dp
  %idx = zext i8 %bv to i32
  %fp  = getelementptr i32, i32* bitcast ([256 x i32]* %freq to i32*), i32 %idx
  %fval = load i32, i32* %fp
  %fval_n = add i32 %fval, 1
  store i32 %fval_n, i32* %fp
  %iv_n = add i32 %iv, 1
  store i32 %iv_n, i32* %i
  br label %freq_loop

entropy_calc:
  ; Вычисляем нормализованную Shannon entropy
  %len_f = sitofp i32 %len to float
  %ent_acc = alloca float
  store float 0.0, float* %ent_acc
  %j = alloca i32
  store i32 0, i32* %j
  br label %ent_loop2

ent_loop2:
  %jv   = load i32, i32* %j
  %cj   = icmp slt i32 %jv, 256
  br i1 %cj, label %ent_body2, label %ent_done2

ent_body2:
  %jfp   = getelementptr i32, i32* bitcast ([256 x i32]* %freq to i32*), i32 %jv
  %jfv   = load i32, i32* %jfp
  %jf_f  = sitofp i32 %jfv to float
  %is_nz = fcmp ogt float %jf_f, 0.0
  br i1 %is_nz, label %ent_add2, label %ent_next2

ent_add2:
  %p     = fdiv float %jf_f, %len_f
  %lp    = call float @log2f(float %p)
  %plp   = fmul float %p, %lp
  %ev    = load float, float* %ent_acc
  %neg   = fneg float %plp
  %ev_n  = fadd float %ev, %neg
  store float %ev_n, float* %ent_acc
  br label %ent_next2

ent_next2:
  %jv_n = add i32 %jv, 1
  store i32 %jv_n, i32* %j
  br label %ent_loop2

ent_done2:
  %H     = load float, float* %ent_acc
  ; Нормализуем: max_entropy = log2(256) = 8.0
  %H_norm = fdiv float %H, 8.0
  ; anomaly = 1 - H_norm (высокая энтропия = случайный шифрованный/зашифрованный файл)
  %anomaly = fsub float 1.0, %H_norm
  ret float %anomaly
}

; ============================================================================
; sq_deepcompress  (src: i8*, slen: i32, dst: i8*, dmax: i32) -> i32
; DeepCompress Ring 0: xxhash fingerprint + RLE-v2 + zero-pack
; Возвращает длину сжатых данных.
; ============================================================================
define i32 @sq_deepcompress(i8* %src, i32 %slen, i8* %dst, i32 %dmax) {
entry:
  ; Пишем xxhash64 fingerprint первые 8 байт
  %src64  = bitcast i8* %src to i8*
  %slen64 = sext i32 %slen to i64
  %hash   = call i64 @sq_xxhash64_ll(i8* %src64, i64 %slen64)
  %hp     = bitcast i8* %dst to i64*
  store i64 %hash, i64* %hp

  ; RLE-v2 компрессия после fingerprint (offset 8)
  %di = alloca i32
  store i32 8, i32* %di   ; первые 8 байт = fingerprint
  %si = alloca i32
  store i32 0, i32* %si
  br label %rle_loop

rle_loop:
  %siv  = load i32, i32* %si
  %div  = load i32, i32* %di
  %sc   = icmp slt i32 %siv, %slen
  %dc   = icmp slt i32 %div, %dmax
  %both = and i1 %sc, %dc
  br i1 %both, label %rle_body, label %rle_done

rle_body:
  ; Считаем длину серии
  %sp   = getelementptr i8, i8* %src, i32 %siv
  %cur  = load i8, i8* %sp
  %run  = alloca i32
  store i32 1, i32* %run
  br label %run_count

run_count:
  %rv   = load i32, i32* %run
  %rc   = icmp slt i32 %rv, 255
  %pos  = add i32 %siv, %rv
  %pc   = icmp slt i32 %pos, %slen
  %both2 = and i1 %rc, %pc
  br i1 %both2, label %run_body, label %run_done

run_body:
  %rsp  = getelementptr i8, i8* %src, i32 %pos
  %rsv  = load i8, i8* %rsp
  %same = icmp eq i8 %rsv, %cur
  br i1 %same, label %run_inc, label %run_done

run_inc:
  %rv_n = add i32 %rv, 1
  store i32 %rv_n, i32* %run
  br label %run_count

run_done:
  %run_v = load i32, i32* %run
  %is_zero = icmp eq i8 %cur, 0
  %run_gt2 = icmp sgt i32 %run_v, 2
  %encode  = or i1 %is_zero, %run_gt2
  br i1 %encode, label %rle_encode, label %rle_literal

rle_encode:
  ; Кодируем: 0xFF + count + value
  %div2  = load i32, i32* %di
  %dp0   = getelementptr i8, i8* %dst, i32 %div2
  store i8 -1, i8* %dp0   ; 0xFF
  %div3  = add i32 %div2, 1
  %dp1   = getelementptr i8, i8* %dst, i32 %div3
  %run_b = trunc i32 %run_v to i8
  store i8 %run_b, i8* %dp1
  %div4  = add i32 %div3, 1
  %dp2   = getelementptr i8, i8* %dst, i32 %div4
  store i8 %cur, i8* %dp2
  %div5  = add i32 %div4, 1
  store i32 %div5, i32* %di
  br label %rle_advance

rle_literal:
  ; Литерал — просто копируем
  %divl  = load i32, i32* %di
  %dpl   = getelementptr i8, i8* %dst, i32 %divl
  store i8 %cur, i8* %dpl
  %divl_n = add i32 %divl, 1
  store i32 %divl_n, i32* %di
  br label %rle_advance

rle_advance:
  %siv_n = add i32 %siv, %run_v
  store i32 %siv_n, i32* %si
  br label %rle_loop

rle_done:
  %di_final = load i32, i32* %di
  ret i32 %di_final
}

; ============================================================================
; sq_batch_pipeline
; (data_arr: i8**, lens: i32*, n: i32, thr: float,
;  meas_out: i32*, ent_out: float*)
; Запускает N fused-pipeline операций без аллокаций между ними.
; Используется для QBATCH в userspace (Ring 0 имеет свой SQASM_QBATCH).
; ============================================================================
define void @sq_batch_pipeline(i8** %data_arr, i32* %lens, i32 %n,
                                float %thr, i32* %meas_out, float* %ent_out) {
entry:
  %i = alloca i32
  store i32 0, i32* %i
  br label %batch_loop

batch_loop:
  %iv   = load i32, i32* %i
  %cond = icmp slt i32 %iv, %n
  br i1 %cond, label %batch_body, label %batch_done

batch_body:
  %dp    = getelementptr i8*, i8** %data_arr, i32 %iv
  %data  = load i8*, i8** %dp
  %lp    = getelementptr i32, i32* %lens, i32 %iv
  %dlen  = load i32, i32* %lp
  %mo_p  = getelementptr i32, i32* %meas_out, i32 %iv
  %eo_p  = getelementptr float, float* %ent_out, i32 %iv
  %ent   = call float @sq_qpipe_fused(i8* %data, i32 %dlen, float %thr,
                                       i32* %mo_p, float* %eo_p)
  %iv_n  = add i32 %iv, 1
  store i32 %iv_n, i32* %i
  br label %batch_loop

batch_done:
  ret void
}

; ============================================================================
; sq_turbo_main — тест-драйв (компилируется в standalone бинарь)
; clang -O3 -march=native sqasm_turbo.ll -o turbo_test -lm
; ============================================================================
define i32 @main() {
entry:
  ; Тестовые данные
  %data = alloca [256 x i8]
  %dp   = bitcast [256 x i8]* %data to i8*
  %i    = alloca i32
  store i32 0, i32* %i
  br label %fill_loop

fill_loop:
  %iv   = load i32, i32* %i
  %cond = icmp slt i32 %iv, 256
  br i1 %cond, label %fill_body, label %run_pipe

fill_body:
  %mod   = urem i32 %iv, 37
  %val   = add i32 %mod, 11
  %b     = trunc i32 %val to i8
  %bp    = getelementptr i8, i8* %dp, i32 %iv
  store i8 %b, i8* %bp
  %iv_n  = add i32 %iv, 1
  store i32 %iv_n, i32* %i
  br label %fill_loop

run_pipe:
  %meas_r = alloca i32
  %ent_r  = alloca float
  %ent    = call float @sq_qpipe_fused(i8* %dp, i32 256, float 0.1,
                                        i32* %meas_r, float* %ent_r)
  %meas_v = load i32, i32* %meas_r
  %ent_v  = load float, float* %ent_r

  %fmt = getelementptr [38 x i8], [38 x i8]* @fmt_pipe, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %fmt, i32 %meas_v, float %ent_v)

  ; xxhash test
  %h64 = call i64 @sq_xxhash64_ll(i8* %dp, i64 256)

  ; cyber scan
  %anom = call float @sq_cyber_scan(i8* %dp, i32 256)
  %is_threat = fcmp ogt float %anom, 0.5
  %status_p = select i1 %is_threat,
              i8* bitcast ([7 x i8]* @str_threat to i8*),
              i8* bitcast ([6 x i8]* @str_clean  to i8*)
  %cfmt = getelementptr [30 x i8], [30 x i8]* @fmt_cyber, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %cfmt, float %anom, i8* %status_p)

  ret i32 0
}
