; ModuleID = 'sqasm_turbo_v4.c'
source_filename = "sqasm_turbo_v4.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

@.str = private unnamed_addr constant [43 x i8] c"[QPIPE-V4] meas=%d entropy=%.6f hash=%llu\0A\00", align 1

; Function Attrs: nofree nounwind memory(write, argmem: readwrite) uwtable
define dso_local void @sq_amplitude_encode(ptr nocapture noundef readonly %0, i32 noundef %1, ptr nocapture noundef writeonly %2, ptr nocapture noundef writeonly %3) local_unnamed_addr #0 {
  %5 = icmp slt i32 %1, 1
  br i1 %5, label %9, label %6

6:                                                ; preds = %4
  %7 = tail call i32 @llvm.umin.i32(i32 %1, i32 256)
  %8 = zext nneg i32 %7 to i64
  br label %14

9:                                                ; preds = %14, %4
  %10 = phi float [ 0.000000e+00, %4 ], [ %20, %14 ]
  %11 = fcmp ugt float %10, 0.000000e+00
  %12 = select i1 %11, float %10, float 1.000000e+00
  %13 = sext i32 %1 to i64
  br label %24

14:                                               ; preds = %6, %14
  %15 = phi i64 [ 0, %6 ], [ %21, %14 ]
  %16 = phi float [ 0.000000e+00, %6 ], [ %20, %14 ]
  %17 = getelementptr inbounds i8, ptr %0, i64 %15
  %18 = load i8, ptr %17, align 1, !tbaa !5
  %19 = uitofp i8 %18 to float
  %20 = fadd float %16, %19
  %21 = add nuw nsw i64 %15, 1
  %22 = icmp eq i64 %21, %8
  br i1 %22, label %9, label %14, !llvm.loop !8

23:                                               ; preds = %31
  ret void

24:                                               ; preds = %9, %31
  %25 = phi i64 [ 0, %9 ], [ %45, %31 ]
  %26 = icmp slt i64 %25, %13
  br i1 %26, label %27, label %31

27:                                               ; preds = %24
  %28 = getelementptr inbounds i8, ptr %0, i64 %25
  %29 = load i8, ptr %28, align 1, !tbaa !5
  %30 = uitofp i8 %29 to float
  br label %31

31:                                               ; preds = %24, %27
  %32 = phi float [ %30, %27 ], [ 0.000000e+00, %24 ]
  %33 = fdiv float %32, %12
  %34 = tail call float @sqrtf(float noundef %33) #12
  %35 = trunc nuw nsw i64 %25 to i32
  %36 = uitofp nneg i32 %35 to float
  %37 = fmul float %36, 0x401921FB60000000
  %38 = fmul float %37, 3.906250e-03
  %39 = tail call float @cosf(float noundef %38) #12
  %40 = fmul float %34, %39
  %41 = getelementptr inbounds float, ptr %2, i64 %25
  store float %40, ptr %41, align 4, !tbaa !11
  %42 = tail call float @sinf(float noundef %38) #12
  %43 = fmul float %34, %42
  %44 = getelementptr inbounds float, ptr %3, i64 %25
  store float %43, ptr %44, align 4, !tbaa !11
  %45 = add nuw nsw i64 %25, 1
  %46 = icmp eq i64 %45, 256
  br i1 %46, label %23, label %24, !llvm.loop !13
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(i64 immarg, ptr nocapture) #1

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(i64 immarg, ptr nocapture) #1

; Function Attrs: mustprogress nofree nounwind willreturn memory(write)
declare float @sqrtf(float noundef) local_unnamed_addr #2

; Function Attrs: mustprogress nofree nounwind willreturn memory(write)
declare float @cosf(float noundef) local_unnamed_addr #2

; Function Attrs: mustprogress nofree nounwind willreturn memory(write)
declare float @sinf(float noundef) local_unnamed_addr #2

; Function Attrs: nofree norecurse nosync nounwind memory(argmem: readwrite) uwtable
define dso_local void @sq_fwht(ptr nocapture noundef %0, i32 noundef %1) local_unnamed_addr #3 {
  %3 = icmp sgt i32 %1, 1
  br i1 %3, label %4, label %14

4:                                                ; preds = %2
  %5 = zext nneg i32 %1 to i64
  br label %6

6:                                                ; preds = %4, %18
  %7 = phi i32 [ 1, %4 ], [ %19, %18 ]
  %8 = shl i32 %7, 1
  %9 = sext i32 %8 to i64
  %10 = sext i32 %7 to i64
  %11 = sext i32 %7 to i64
  %12 = icmp sgt i32 %7, 0
  %13 = getelementptr float, ptr %0, i64 %10
  br label %15

14:                                               ; preds = %18, %2
  ret void

15:                                               ; preds = %6, %21
  %16 = phi i64 [ 0, %6 ], [ %22, %21 ]
  %17 = add nsw i64 %16, %11
  br i1 %12, label %24, label %21

18:                                               ; preds = %21
  %19 = shl i32 %7, 1
  %20 = icmp slt i32 %19, %1
  br i1 %20, label %6, label %14, !llvm.loop !14

21:                                               ; preds = %24, %15
  %22 = add nsw i64 %16, %9
  %23 = icmp slt i64 %22, %5
  br i1 %23, label %15, label %18, !llvm.loop !15

24:                                               ; preds = %15, %24
  %25 = phi i64 [ %32, %24 ], [ %16, %15 ]
  %26 = getelementptr inbounds float, ptr %0, i64 %25
  %27 = load float, ptr %26, align 4, !tbaa !11
  %28 = getelementptr float, ptr %13, i64 %25
  %29 = load float, ptr %28, align 4, !tbaa !11
  %30 = fadd float %27, %29
  store float %30, ptr %26, align 4, !tbaa !11
  %31 = fsub float %27, %29
  store float %31, ptr %28, align 4, !tbaa !11
  %32 = add nsw i64 %25, 1
  %33 = icmp slt i64 %32, %17
  br i1 %33, label %24, label %21, !llvm.loop !16
}

; Function Attrs: nofree norecurse nosync nounwind memory(argmem: readwrite) uwtable
define dso_local i32 @sq_grover(ptr nocapture noundef %0, ptr nocapture noundef %1, i32 noundef %2, float noundef %3) local_unnamed_addr #3 {
  %5 = icmp sgt i32 %2, 0
  br i1 %5, label %6, label %8

6:                                                ; preds = %4
  %7 = zext nneg i32 %2 to i64
  br label %15

8:                                                ; preds = %15, %4
  %9 = phi float [ 0.000000e+00, %4 ], [ %25, %15 ]
  %10 = fsub float 1.000000e+00, %3
  %11 = fmul float %10, %9
  %12 = icmp sgt i32 %2, 0
  br i1 %12, label %13, label %28

13:                                               ; preds = %8
  %14 = zext nneg i32 %2 to i64
  br label %30

15:                                               ; preds = %6, %15
  %16 = phi i64 [ 0, %6 ], [ %26, %15 ]
  %17 = phi float [ 0.000000e+00, %6 ], [ %25, %15 ]
  %18 = getelementptr inbounds float, ptr %0, i64 %16
  %19 = load float, ptr %18, align 4, !tbaa !11
  %20 = getelementptr inbounds float, ptr %1, i64 %16
  %21 = load float, ptr %20, align 4, !tbaa !11
  %22 = fmul float %21, %21
  %23 = tail call float @llvm.fmuladd.f32(float %19, float %19, float %22)
  %24 = fcmp ogt float %23, %17
  %25 = select i1 %24, float %23, float %17
  %26 = add nuw nsw i64 %16, 1
  %27 = icmp eq i64 %26, %7
  br i1 %27, label %8, label %15, !llvm.loop !17

28:                                               ; preds = %45, %8
  %29 = phi i32 [ 0, %8 ], [ %46, %45 ]
  ret i32 %29

30:                                               ; preds = %13, %45
  %31 = phi i64 [ 0, %13 ], [ %47, %45 ]
  %32 = phi i32 [ 0, %13 ], [ %46, %45 ]
  %33 = getelementptr inbounds float, ptr %0, i64 %31
  %34 = load float, ptr %33, align 4, !tbaa !11
  %35 = getelementptr inbounds float, ptr %1, i64 %31
  %36 = load float, ptr %35, align 4, !tbaa !11
  %37 = fmul float %36, %36
  %38 = tail call float @llvm.fmuladd.f32(float %34, float %34, float %37)
  %39 = fcmp ult float %38, %11
  br i1 %39, label %45, label %40

40:                                               ; preds = %30
  %41 = fneg float %34
  store float %41, ptr %33, align 4, !tbaa !11
  %42 = load float, ptr %35, align 4, !tbaa !11
  %43 = fneg float %42
  store float %43, ptr %35, align 4, !tbaa !11
  %44 = add nsw i32 %32, 1
  br label %45

45:                                               ; preds = %40, %30
  %46 = phi i32 [ %44, %40 ], [ %32, %30 ]
  %47 = add nuw nsw i64 %31, 1
  %48 = icmp eq i64 %47, %14
  br i1 %48, label %28, label %30, !llvm.loop !18
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare float @llvm.fmuladd.f32(float, float, float) #4

; Function Attrs: nofree norecurse nosync nounwind memory(argmem: read) uwtable
define dso_local i32 @sq_measure(ptr nocapture noundef readonly %0, ptr nocapture noundef readonly %1, i32 noundef %2) local_unnamed_addr #5 {
  %4 = icmp sgt i32 %2, 0
  br i1 %4, label %5, label %7

5:                                                ; preds = %3
  %6 = zext nneg i32 %2 to i64
  br label %9

7:                                                ; preds = %9, %3
  %8 = phi i32 [ 0, %3 ], [ %22, %9 ]
  ret i32 %8

9:                                                ; preds = %5, %9
  %10 = phi i64 [ 0, %5 ], [ %23, %9 ]
  %11 = phi i32 [ 0, %5 ], [ %22, %9 ]
  %12 = phi float [ -1.000000e+00, %5 ], [ %20, %9 ]
  %13 = getelementptr inbounds float, ptr %0, i64 %10
  %14 = load float, ptr %13, align 4, !tbaa !11
  %15 = getelementptr inbounds float, ptr %1, i64 %10
  %16 = load float, ptr %15, align 4, !tbaa !11
  %17 = fmul float %16, %16
  %18 = tail call float @llvm.fmuladd.f32(float %14, float %14, float %17)
  %19 = fcmp ogt float %18, %12
  %20 = select i1 %19, float %18, float %12
  %21 = trunc nuw nsw i64 %10 to i32
  %22 = select i1 %19, i32 %21, i32 %11
  %23 = add nuw nsw i64 %10, 1
  %24 = icmp eq i64 %23, %6
  br i1 %24, label %7, label %9, !llvm.loop !19
}

; Function Attrs: nofree nounwind memory(write, argmem: readwrite) uwtable
define dso_local float @sq_entropy(ptr nocapture noundef readonly %0, ptr nocapture noundef readonly %1, i32 noundef %2) local_unnamed_addr #0 {
  %4 = icmp sgt i32 %2, 0
  br i1 %4, label %5, label %7

5:                                                ; preds = %3
  %6 = zext nneg i32 %2 to i64
  br label %14

7:                                                ; preds = %14, %3
  %8 = phi double [ 0.000000e+00, %3 ], [ %25, %14 ]
  %9 = fcmp ugt double %8, 0.000000e+00
  %10 = icmp sgt i32 %2, 0
  %11 = and i1 %9, %10
  br i1 %11, label %12, label %51

12:                                               ; preds = %7
  %13 = zext nneg i32 %2 to i64
  br label %30

14:                                               ; preds = %5, %14
  %15 = phi i64 [ 0, %5 ], [ %26, %14 ]
  %16 = phi double [ 0.000000e+00, %5 ], [ %25, %14 ]
  %17 = getelementptr inbounds float, ptr %0, i64 %15
  %18 = load float, ptr %17, align 4, !tbaa !11
  %19 = fpext float %18 to double
  %20 = getelementptr inbounds float, ptr %1, i64 %15
  %21 = load float, ptr %20, align 4, !tbaa !11
  %22 = fpext float %21 to double
  %23 = fmul double %22, %22
  %24 = tail call double @llvm.fmuladd.f64(double %19, double %19, double %23)
  %25 = fadd double %16, %24
  %26 = add nuw nsw i64 %15, 1
  %27 = icmp eq i64 %26, %6
  br i1 %27, label %7, label %14, !llvm.loop !20

28:                                               ; preds = %47
  %29 = fptrunc double %48 to float
  br label %51

30:                                               ; preds = %12, %47
  %31 = phi i64 [ 0, %12 ], [ %49, %47 ]
  %32 = phi double [ 0.000000e+00, %12 ], [ %48, %47 ]
  %33 = getelementptr inbounds float, ptr %0, i64 %31
  %34 = load float, ptr %33, align 4, !tbaa !11
  %35 = fpext float %34 to double
  %36 = getelementptr inbounds float, ptr %1, i64 %31
  %37 = load float, ptr %36, align 4, !tbaa !11
  %38 = fpext float %37 to double
  %39 = fmul double %38, %38
  %40 = tail call double @llvm.fmuladd.f64(double %35, double %35, double %39)
  %41 = fdiv double %40, %8
  %42 = fcmp ogt double %41, 0.000000e+00
  br i1 %42, label %43, label %47

43:                                               ; preds = %30
  %44 = tail call double @log2(double noundef %41) #12
  %45 = fneg double %41
  %46 = tail call double @llvm.fmuladd.f64(double %45, double %44, double %32)
  br label %47

47:                                               ; preds = %43, %30
  %48 = phi double [ %46, %43 ], [ %32, %30 ]
  %49 = add nuw nsw i64 %31, 1
  %50 = icmp eq i64 %49, %13
  br i1 %50, label %28, label %30, !llvm.loop !21

51:                                               ; preds = %28, %7
  %52 = phi float [ 0.000000e+00, %7 ], [ %29, %28 ]
  ret float %52
}

; Function Attrs: mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare double @llvm.fmuladd.f64(double, double, double) #4

; Function Attrs: mustprogress nofree nounwind willreturn memory(write)
declare double @log2(double noundef) local_unnamed_addr #2

; Function Attrs: nofree nounwind memory(write, argmem: readwrite) uwtable
define dso_local float @sq_qpipe_fused(ptr nocapture noundef readonly %0, i32 noundef %1, float noundef %2, ptr noundef writeonly %3, ptr noundef writeonly %4) local_unnamed_addr #0 {
  %6 = alloca [256 x float], align 16
  %7 = alloca [256 x float], align 16
  call void @llvm.lifetime.start.p0(i64 1024, ptr nonnull %6) #12
  call void @llvm.lifetime.start.p0(i64 1024, ptr nonnull %7) #12
  %8 = icmp slt i32 %1, 1
  br i1 %8, label %12, label %9

9:                                                ; preds = %5
  %10 = tail call i32 @llvm.umin.i32(i32 %1, i32 256)
  %11 = zext nneg i32 %10 to i64
  br label %17

12:                                               ; preds = %17, %5
  %13 = phi float [ 0.000000e+00, %5 ], [ %23, %17 ]
  %14 = fcmp ugt float %13, 0.000000e+00
  %15 = select i1 %14, float %13, float 1.000000e+00
  %16 = sext i32 %1 to i64
  br label %26

17:                                               ; preds = %17, %9
  %18 = phi i64 [ 0, %9 ], [ %24, %17 ]
  %19 = phi float [ 0.000000e+00, %9 ], [ %23, %17 ]
  %20 = getelementptr inbounds i8, ptr %0, i64 %18
  %21 = load i8, ptr %20, align 1, !tbaa !5
  %22 = uitofp i8 %21 to float
  %23 = fadd float %19, %22
  %24 = add nuw nsw i64 %18, 1
  %25 = icmp eq i64 %24, %11
  br i1 %25, label %12, label %17, !llvm.loop !8

26:                                               ; preds = %33, %12
  %27 = phi i64 [ 0, %12 ], [ %47, %33 ]
  %28 = icmp slt i64 %27, %16
  br i1 %28, label %29, label %33

29:                                               ; preds = %26
  %30 = getelementptr inbounds i8, ptr %0, i64 %27
  %31 = load i8, ptr %30, align 1, !tbaa !5
  %32 = uitofp i8 %31 to float
  br label %33

33:                                               ; preds = %29, %26
  %34 = phi float [ %32, %29 ], [ 0.000000e+00, %26 ]
  %35 = fdiv float %34, %15
  %36 = tail call float @sqrtf(float noundef %35) #12
  %37 = trunc nuw nsw i64 %27 to i32
  %38 = uitofp nneg i32 %37 to float
  %39 = fmul float %38, 0x401921FB60000000
  %40 = fmul float %39, 3.906250e-03
  %41 = tail call float @cosf(float noundef %40) #12
  %42 = fmul float %36, %41
  %43 = getelementptr inbounds float, ptr %6, i64 %27
  store float %42, ptr %43, align 4, !tbaa !11
  %44 = tail call float @sinf(float noundef %40) #12
  %45 = fmul float %36, %44
  %46 = getelementptr inbounds float, ptr %7, i64 %27
  store float %45, ptr %46, align 4, !tbaa !11
  %47 = add nuw nsw i64 %27, 1
  %48 = icmp eq i64 %47, 256
  br i1 %48, label %49, label %26, !llvm.loop !13

49:                                               ; preds = %33, %57
  %50 = phi i32 [ %51, %57 ], [ 1, %33 ]
  %51 = shl i32 %50, 1
  %52 = sext i32 %51 to i64
  %53 = sext i32 %50 to i64
  br label %54

54:                                               ; preds = %59, %49
  %55 = phi i64 [ 0, %49 ], [ %60, %59 ]
  %56 = add nsw i64 %55, %53
  br label %62

57:                                               ; preds = %59
  %58 = icmp slt i32 %51, 256
  br i1 %58, label %49, label %72, !llvm.loop !14

59:                                               ; preds = %62
  %60 = add nsw i64 %55, %52
  %61 = icmp slt i64 %60, 256
  br i1 %61, label %54, label %57, !llvm.loop !15

62:                                               ; preds = %54, %62
  %63 = phi i64 [ %70, %62 ], [ %55, %54 ]
  %64 = getelementptr inbounds float, ptr %6, i64 %63
  %65 = load float, ptr %64, align 4, !tbaa !11
  %66 = getelementptr float, ptr %64, i64 %53
  %67 = load float, ptr %66, align 4, !tbaa !11
  %68 = fadd float %65, %67
  store float %68, ptr %64, align 4, !tbaa !11
  %69 = fsub float %65, %67
  store float %69, ptr %66, align 4, !tbaa !11
  %70 = add nsw i64 %63, 1
  %71 = icmp slt i64 %70, %56
  br i1 %71, label %62, label %59, !llvm.loop !16

72:                                               ; preds = %57, %80
  %73 = phi i32 [ %74, %80 ], [ 1, %57 ]
  %74 = shl i32 %73, 1
  %75 = sext i32 %74 to i64
  %76 = sext i32 %73 to i64
  br label %77

77:                                               ; preds = %82, %72
  %78 = phi i64 [ 0, %72 ], [ %83, %82 ]
  %79 = add nsw i64 %78, %76
  br label %85

80:                                               ; preds = %82
  %81 = icmp slt i32 %74, 256
  br i1 %81, label %72, label %98, !llvm.loop !14

82:                                               ; preds = %85
  %83 = add nsw i64 %78, %75
  %84 = icmp slt i64 %83, 256
  br i1 %84, label %77, label %80, !llvm.loop !15

85:                                               ; preds = %77, %85
  %86 = phi i64 [ %93, %85 ], [ %78, %77 ]
  %87 = getelementptr inbounds float, ptr %7, i64 %86
  %88 = load float, ptr %87, align 4, !tbaa !11
  %89 = getelementptr float, ptr %87, i64 %76
  %90 = load float, ptr %89, align 4, !tbaa !11
  %91 = fadd float %88, %90
  store float %91, ptr %87, align 4, !tbaa !11
  %92 = fsub float %88, %90
  store float %92, ptr %89, align 4, !tbaa !11
  %93 = add nsw i64 %86, 1
  %94 = icmp slt i64 %93, %79
  br i1 %94, label %85, label %82, !llvm.loop !16

95:                                               ; preds = %98
  %96 = fsub float 1.000000e+00, %2
  %97 = fmul float %96, %108
  br label %111

98:                                               ; preds = %80, %98
  %99 = phi i64 [ %109, %98 ], [ 0, %80 ]
  %100 = phi float [ %108, %98 ], [ 0.000000e+00, %80 ]
  %101 = getelementptr inbounds float, ptr %6, i64 %99
  %102 = load float, ptr %101, align 4, !tbaa !11
  %103 = getelementptr inbounds float, ptr %7, i64 %99
  %104 = load float, ptr %103, align 4, !tbaa !11
  %105 = fmul float %104, %104
  %106 = tail call float @llvm.fmuladd.f32(float %102, float %102, float %105)
  %107 = fcmp ogt float %106, %100
  %108 = select i1 %107, float %106, float %100
  %109 = add nuw nsw i64 %99, 1
  %110 = icmp eq i64 %109, 256
  br i1 %110, label %95, label %98, !llvm.loop !17

111:                                              ; preds = %123, %95
  %112 = phi i64 [ 0, %95 ], [ %124, %123 ]
  %113 = getelementptr inbounds float, ptr %6, i64 %112
  %114 = load float, ptr %113, align 4, !tbaa !11
  %115 = getelementptr inbounds float, ptr %7, i64 %112
  %116 = load float, ptr %115, align 4, !tbaa !11
  %117 = fmul float %116, %116
  %118 = tail call float @llvm.fmuladd.f32(float %114, float %114, float %117)
  %119 = fcmp ult float %118, %97
  br i1 %119, label %123, label %120

120:                                              ; preds = %111
  %121 = fneg float %114
  store float %121, ptr %113, align 4, !tbaa !11
  %122 = fneg float %116
  store float %122, ptr %115, align 4, !tbaa !11
  br label %123

123:                                              ; preds = %120, %111
  %124 = add nuw nsw i64 %112, 1
  %125 = icmp eq i64 %124, 256
  br i1 %125, label %126, label %111, !llvm.loop !18

126:                                              ; preds = %123, %126
  %127 = phi i64 [ %140, %126 ], [ 0, %123 ]
  %128 = phi i32 [ %139, %126 ], [ 0, %123 ]
  %129 = phi float [ %137, %126 ], [ -1.000000e+00, %123 ]
  %130 = getelementptr inbounds float, ptr %6, i64 %127
  %131 = load float, ptr %130, align 4, !tbaa !11
  %132 = getelementptr inbounds float, ptr %7, i64 %127
  %133 = load float, ptr %132, align 4, !tbaa !11
  %134 = fmul float %133, %133
  %135 = tail call float @llvm.fmuladd.f32(float %131, float %131, float %134)
  %136 = fcmp ogt float %135, %129
  %137 = select i1 %136, float %135, float %129
  %138 = trunc nuw nsw i64 %127 to i32
  %139 = select i1 %136, i32 %138, i32 %128
  %140 = add nuw nsw i64 %127, 1
  %141 = icmp eq i64 %140, 256
  br i1 %141, label %144, label %126, !llvm.loop !19

142:                                              ; preds = %144
  %143 = fcmp ugt double %155, 0.000000e+00
  br i1 %143, label %160, label %181

144:                                              ; preds = %126, %144
  %145 = phi i64 [ %156, %144 ], [ 0, %126 ]
  %146 = phi double [ %155, %144 ], [ 0.000000e+00, %126 ]
  %147 = getelementptr inbounds float, ptr %6, i64 %145
  %148 = load float, ptr %147, align 4, !tbaa !11
  %149 = fpext float %148 to double
  %150 = getelementptr inbounds float, ptr %7, i64 %145
  %151 = load float, ptr %150, align 4, !tbaa !11
  %152 = fpext float %151 to double
  %153 = fmul double %152, %152
  %154 = tail call double @llvm.fmuladd.f64(double %149, double %149, double %153)
  %155 = fadd double %146, %154
  %156 = add nuw nsw i64 %145, 1
  %157 = icmp eq i64 %156, 256
  br i1 %157, label %142, label %144, !llvm.loop !20

158:                                              ; preds = %177
  %159 = fptrunc double %178 to float
  br label %181

160:                                              ; preds = %142, %177
  %161 = phi i64 [ %179, %177 ], [ 0, %142 ]
  %162 = phi double [ %178, %177 ], [ 0.000000e+00, %142 ]
  %163 = getelementptr inbounds float, ptr %6, i64 %161
  %164 = load float, ptr %163, align 4, !tbaa !11
  %165 = fpext float %164 to double
  %166 = getelementptr inbounds float, ptr %7, i64 %161
  %167 = load float, ptr %166, align 4, !tbaa !11
  %168 = fpext float %167 to double
  %169 = fmul double %168, %168
  %170 = tail call double @llvm.fmuladd.f64(double %165, double %165, double %169)
  %171 = fdiv double %170, %155
  %172 = fcmp ogt double %171, 0.000000e+00
  br i1 %172, label %173, label %177

173:                                              ; preds = %160
  %174 = tail call double @log2(double noundef %171) #12
  %175 = fneg double %171
  %176 = tail call double @llvm.fmuladd.f64(double %175, double %174, double %162)
  br label %177

177:                                              ; preds = %173, %160
  %178 = phi double [ %176, %173 ], [ %162, %160 ]
  %179 = add nuw nsw i64 %161, 1
  %180 = icmp eq i64 %179, 256
  br i1 %180, label %158, label %160, !llvm.loop !21

181:                                              ; preds = %142, %158
  %182 = phi float [ 0.000000e+00, %142 ], [ %159, %158 ]
  %183 = icmp eq ptr %3, null
  br i1 %183, label %185, label %184

184:                                              ; preds = %181
  store i32 %139, ptr %3, align 4, !tbaa !22
  br label %185

185:                                              ; preds = %184, %181
  %186 = icmp eq ptr %4, null
  br i1 %186, label %188, label %187

187:                                              ; preds = %185
  store float %182, ptr %4, align 4, !tbaa !11
  br label %188

188:                                              ; preds = %187, %185
  call void @llvm.lifetime.end.p0(i64 1024, ptr nonnull %7) #12
  call void @llvm.lifetime.end.p0(i64 1024, ptr nonnull %6) #12
  ret float %182
}

; Function Attrs: nofree norecurse nosync nounwind memory(argmem: read) uwtable
define dso_local i64 @sq_xxhash64_ll(ptr nocapture noundef readonly %0, i64 noundef %1) local_unnamed_addr #5 {
  %3 = add i64 %1, 2870177450012600261
  %4 = icmp ult i64 %1, 4
  br i1 %4, label %5, label %9

5:                                                ; preds = %9, %2
  %6 = phi i64 [ 0, %2 ], [ %10, %9 ]
  %7 = phi i64 [ %3, %2 ], [ %20, %9 ]
  %8 = icmp ult i64 %6, %1
  br i1 %8, label %23, label %35

9:                                                ; preds = %2, %9
  %10 = phi i64 [ %21, %9 ], [ 4, %2 ]
  %11 = phi i64 [ %20, %9 ], [ %3, %2 ]
  %12 = phi i64 [ %10, %9 ], [ 0, %2 ]
  %13 = getelementptr inbounds i8, ptr %0, i64 %12
  %14 = load i32, ptr %13, align 1
  %15 = zext i32 %14 to i64
  %16 = mul i64 %15, -4417276706812531889
  %17 = xor i64 %16, %11
  %18 = tail call i64 @llvm.fshl.i64(i64 %17, i64 %17, i64 27)
  %19 = mul i64 %18, -7046029288634856825
  %20 = add i64 %19, -8796714831421723037
  %21 = add nuw i64 %10, 4
  %22 = icmp ugt i64 %21, %1
  br i1 %22, label %5, label %9, !llvm.loop !24

23:                                               ; preds = %5, %23
  %24 = phi i64 [ %32, %23 ], [ %7, %5 ]
  %25 = phi i64 [ %33, %23 ], [ %6, %5 ]
  %26 = getelementptr inbounds i8, ptr %0, i64 %25
  %27 = load i8, ptr %26, align 1, !tbaa !5
  %28 = zext i8 %27 to i64
  %29 = mul i64 %28, 2870177450012600261
  %30 = xor i64 %29, %24
  %31 = tail call i64 @llvm.fshl.i64(i64 %30, i64 %30, i64 11)
  %32 = mul i64 %31, -7046029288634856825
  %33 = add nuw i64 %25, 1
  %34 = icmp eq i64 %33, %1
  br i1 %34, label %35, label %23, !llvm.loop !25

35:                                               ; preds = %23, %5
  %36 = phi i64 [ %7, %5 ], [ %32, %23 ]
  %37 = lshr i64 %36, 33
  %38 = xor i64 %37, %36
  %39 = mul i64 %38, -4417276706812531889
  %40 = lshr i64 %39, 29
  %41 = xor i64 %40, %39
  %42 = mul i64 %41, 1609587929392839161
  %43 = lshr i64 %42, 32
  %44 = xor i64 %43, %42
  ret i64 %44
}

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #6

; Function Attrs: nofree nounwind memory(write, argmem: readwrite) uwtable
define dso_local float @sq_cyber_scan(ptr nocapture noundef readonly %0, i32 noundef %1) local_unnamed_addr #0 {
  %3 = alloca [256 x i32], align 16
  %4 = icmp slt i32 %1, 1
  br i1 %4, label %38, label %5

5:                                                ; preds = %2
  call void @llvm.lifetime.start.p0(i64 1024, ptr nonnull %3) #12
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 16 dereferenceable(1024) %3, i8 0, i64 1024, i1 false)
  %6 = zext nneg i32 %1 to i64
  br label %9

7:                                                ; preds = %9
  %8 = uitofp nneg i32 %1 to double
  br label %22

9:                                                ; preds = %5, %9
  %10 = phi i64 [ 0, %5 ], [ %17, %9 ]
  %11 = getelementptr inbounds i8, ptr %0, i64 %10
  %12 = load i8, ptr %11, align 1, !tbaa !5
  %13 = zext i8 %12 to i64
  %14 = getelementptr inbounds [256 x i32], ptr %3, i64 0, i64 %13
  %15 = load i32, ptr %14, align 4, !tbaa !22
  %16 = add i32 %15, 1
  store i32 %16, ptr %14, align 4, !tbaa !22
  %17 = add nuw nsw i64 %10, 1
  %18 = icmp eq i64 %17, %6
  br i1 %18, label %7, label %9, !llvm.loop !26

19:                                               ; preds = %34
  %20 = fmul double %35, 1.250000e-01
  %21 = fptrunc double %20 to float
  call void @llvm.lifetime.end.p0(i64 1024, ptr nonnull %3) #12
  br label %38

22:                                               ; preds = %7, %34
  %23 = phi i64 [ 0, %7 ], [ %36, %34 ]
  %24 = phi double [ 0.000000e+00, %7 ], [ %35, %34 ]
  %25 = getelementptr inbounds [256 x i32], ptr %3, i64 0, i64 %23
  %26 = load i32, ptr %25, align 4, !tbaa !22
  %27 = icmp eq i32 %26, 0
  br i1 %27, label %34, label %28

28:                                               ; preds = %22
  %29 = uitofp i32 %26 to double
  %30 = fdiv double %29, %8
  %31 = tail call double @log2(double noundef %30) #12
  %32 = fneg double %30
  %33 = tail call double @llvm.fmuladd.f64(double %32, double %31, double %24)
  br label %34

34:                                               ; preds = %22, %28
  %35 = phi double [ %33, %28 ], [ %24, %22 ]
  %36 = add nuw nsw i64 %23, 1
  %37 = icmp eq i64 %36, 256
  br i1 %37, label %19, label %22, !llvm.loop !27

38:                                               ; preds = %2, %19
  %39 = phi float [ %21, %19 ], [ 0.000000e+00, %2 ]
  ret float %39
}

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: write)
declare void @llvm.memset.p0.i64(ptr nocapture writeonly, i8, i64, i1 immarg) #7

; Function Attrs: nofree norecurse nosync nounwind memory(argmem: readwrite) uwtable
define dso_local i32 @sq_deepcompress(ptr nocapture noundef readonly %0, i32 noundef %1, ptr nocapture noundef writeonly %2, i32 noundef %3) local_unnamed_addr #3 {
  %5 = icmp sgt i32 %1, 0
  br i1 %5, label %6, label %88

6:                                                ; preds = %4
  %7 = zext nneg i32 %1 to i64
  br label %8

8:                                                ; preds = %6, %84
  %9 = phi i32 [ %86, %84 ], [ 0, %6 ]
  %10 = phi i32 [ %85, %84 ], [ 0, %6 ]
  %11 = sext i32 %10 to i64
  %12 = getelementptr inbounds i8, ptr %0, i64 %11
  %13 = load i8, ptr %12, align 1, !tbaa !5
  %14 = icmp eq i8 %13, 0
  %15 = icmp slt i32 %10, %1
  br i1 %14, label %20, label %16

16:                                               ; preds = %8
  br i1 %15, label %17, label %67

17:                                               ; preds = %16
  %18 = sext i32 %10 to i64
  %19 = sub i32 %1, %10
  br label %53

20:                                               ; preds = %8
  br i1 %15, label %21, label %42

21:                                               ; preds = %20
  %22 = sext i32 %10 to i64
  %23 = sub i32 %1, %10
  br label %24

24:                                               ; preds = %21, %32
  %25 = phi i64 [ %22, %21 ], [ %33, %32 ]
  %26 = phi i32 [ 0, %21 ], [ %34, %32 ]
  %27 = getelementptr inbounds i8, ptr %0, i64 %25
  %28 = load i8, ptr %27, align 1, !tbaa !5
  %29 = icmp eq i8 %28, 0
  %30 = icmp ult i32 %26, 255
  %31 = select i1 %29, i1 %30, i1 false
  br i1 %31, label %32, label %36

32:                                               ; preds = %24
  %33 = add nsw i64 %25, 1
  %34 = add nuw nsw i32 %26, 1
  %35 = icmp eq i64 %33, %7
  br i1 %35, label %38, label %24, !llvm.loop !28

36:                                               ; preds = %24
  %37 = trunc nsw i64 %25 to i32
  br label %38

38:                                               ; preds = %32, %36
  %39 = phi i32 [ %37, %36 ], [ %1, %32 ]
  %40 = phi i32 [ %26, %36 ], [ %23, %32 ]
  %41 = trunc i32 %40 to i8
  br label %42

42:                                               ; preds = %38, %20
  %43 = phi i32 [ %10, %20 ], [ %39, %38 ]
  %44 = phi i8 [ 0, %20 ], [ %41, %38 ]
  %45 = add nsw i32 %9, 2
  %46 = icmp sgt i32 %45, %3
  br i1 %46, label %51, label %47

47:                                               ; preds = %42
  %48 = sext i32 %9 to i64
  %49 = getelementptr inbounds i8, ptr %2, i64 %48
  store i8 0, ptr %49, align 1, !tbaa !5
  %50 = getelementptr i8, ptr %49, i64 1
  store i8 %44, ptr %50, align 1, !tbaa !5
  br label %51

51:                                               ; preds = %42, %47
  %52 = phi i32 [ %45, %47 ], [ %9, %42 ]
  br i1 %46, label %88, label %84

53:                                               ; preds = %17, %61
  %54 = phi i64 [ %18, %17 ], [ %62, %61 ]
  %55 = phi i32 [ 0, %17 ], [ %63, %61 ]
  %56 = getelementptr inbounds i8, ptr %0, i64 %54
  %57 = load i8, ptr %56, align 1, !tbaa !5
  %58 = icmp ne i8 %57, 0
  %59 = icmp ult i32 %55, 127
  %60 = select i1 %58, i1 %59, i1 false
  br i1 %60, label %61, label %65

61:                                               ; preds = %53
  %62 = add nsw i64 %54, 1
  %63 = add nuw nsw i32 %55, 1
  %64 = icmp eq i64 %62, %7
  br i1 %64, label %67, label %53, !llvm.loop !29

65:                                               ; preds = %53
  %66 = trunc nsw i64 %54 to i32
  br label %67

67:                                               ; preds = %65, %61, %16
  %68 = phi i32 [ %10, %16 ], [ %66, %65 ], [ %1, %61 ]
  %69 = phi i32 [ 0, %16 ], [ %55, %65 ], [ %19, %61 ]
  %70 = add nsw i32 %9, 2
  %71 = add nsw i32 %69, %70
  %72 = icmp sgt i32 %71, %3
  br i1 %72, label %82, label %73

73:                                               ; preds = %67
  %74 = trunc i32 %69 to i8
  %75 = or i8 %74, -128
  %76 = sext i32 %9 to i64
  %77 = getelementptr inbounds i8, ptr %2, i64 %76
  store i8 %75, ptr %77, align 1, !tbaa !5
  %78 = getelementptr i8, ptr %77, i64 1
  store i8 %74, ptr %78, align 1, !tbaa !5
  %79 = sext i32 %70 to i64
  %80 = getelementptr inbounds i8, ptr %2, i64 %79
  %81 = zext nneg i32 %69 to i64
  tail call void @llvm.memcpy.p0.p0.i64(ptr align 1 %80, ptr nonnull align 1 %12, i64 %81, i1 false)
  br label %82

82:                                               ; preds = %67, %73
  %83 = phi i32 [ %71, %73 ], [ %9, %67 ]
  br i1 %72, label %88, label %84

84:                                               ; preds = %82, %51
  %85 = phi i32 [ %43, %51 ], [ %68, %82 ]
  %86 = phi i32 [ %52, %51 ], [ %83, %82 ]
  %87 = icmp slt i32 %85, %1
  br i1 %87, label %8, label %88, !llvm.loop !30

88:                                               ; preds = %82, %51, %84, %4
  %89 = phi i32 [ 0, %4 ], [ -1, %82 ], [ -1, %51 ], [ %86, %84 ]
  ret i32 %89
}

; Function Attrs: nofree nounwind memory(readwrite, inaccessiblemem: write) uwtable
define dso_local void @sq_batch_pipeline(ptr nocapture noundef readonly %0, ptr nocapture noundef readonly %1, i32 noundef %2, float noundef %3, ptr noundef %4, ptr noundef %5) local_unnamed_addr #8 {
  %7 = icmp sgt i32 %2, 0
  br i1 %7, label %8, label %10

8:                                                ; preds = %6
  %9 = zext nneg i32 %2 to i64
  br label %11

10:                                               ; preds = %11, %6
  ret void

11:                                               ; preds = %8, %11
  %12 = phi i64 [ 0, %8 ], [ %20, %11 ]
  %13 = getelementptr inbounds ptr, ptr %0, i64 %12
  %14 = load ptr, ptr %13, align 8, !tbaa !31
  %15 = getelementptr inbounds i32, ptr %1, i64 %12
  %16 = load i32, ptr %15, align 4, !tbaa !22
  %17 = getelementptr inbounds i32, ptr %4, i64 %12
  %18 = getelementptr inbounds float, ptr %5, i64 %12
  %19 = tail call float @sq_qpipe_fused(ptr noundef %14, i32 noundef %16, float noundef %3, ptr noundef %17, ptr noundef %18)
  %20 = add nuw nsw i64 %12, 1
  %21 = icmp eq i64 %20, %9
  br i1 %21, label %10, label %11, !llvm.loop !33
}

; Function Attrs: nofree nounwind uwtable
define dso_local range(i32 0, 3) i32 @main() local_unnamed_addr #9 {
  %1 = alloca [256 x i8], align 16
  %2 = alloca i32, align 4
  %3 = alloca float, align 4
  call void @llvm.lifetime.start.p0(i64 256, ptr nonnull %1) #12
  br label %41

4:                                                ; preds = %41
  call void @llvm.lifetime.start.p0(i64 4, ptr nonnull %2) #12
  store i32 -1, ptr %2, align 4, !tbaa !22
  call void @llvm.lifetime.start.p0(i64 4, ptr nonnull %3) #12
  store float -1.000000e+00, ptr %3, align 4, !tbaa !11
  %5 = call float @sq_qpipe_fused(ptr noundef nonnull %1, i32 noundef 256, float noundef 0x3FB99999A0000000, ptr noundef nonnull %2, ptr noundef nonnull %3)
  %6 = load i32, ptr %2, align 4, !tbaa !22
  %7 = load float, ptr %3, align 4, !tbaa !11
  br label %8

8:                                                ; preds = %8, %4
  %9 = phi i64 [ %20, %8 ], [ 4, %4 ]
  %10 = phi i64 [ %19, %8 ], [ 2870177450012600517, %4 ]
  %11 = phi i64 [ %9, %8 ], [ 0, %4 ]
  %12 = getelementptr inbounds i8, ptr %1, i64 %11
  %13 = load i32, ptr %12, align 4
  %14 = zext i32 %13 to i64
  %15 = mul i64 %14, -4417276706812531889
  %16 = xor i64 %15, %10
  %17 = call i64 @llvm.fshl.i64(i64 %16, i64 %16, i64 27)
  %18 = mul i64 %17, -7046029288634856825
  %19 = add i64 %18, -8796714831421723037
  %20 = add nuw nsw i64 %9, 4
  %21 = icmp ugt i64 %9, 252
  br i1 %21, label %22, label %8, !llvm.loop !24

22:                                               ; preds = %8
  %23 = fpext float %7 to double
  %24 = lshr i64 %19, 33
  %25 = xor i64 %24, %19
  %26 = mul i64 %25, -4417276706812531889
  %27 = lshr i64 %26, 29
  %28 = xor i64 %27, %26
  %29 = mul i64 %28, 1609587929392839161
  %30 = lshr i64 %29, 32
  %31 = xor i64 %30, %29
  %32 = call i32 (ptr, ...) @printf(ptr noundef nonnull dereferenceable(1) @.str, i32 noundef %6, double noundef %23, i64 noundef %31)
  %33 = load float, ptr %3, align 4, !tbaa !11
  %34 = fcmp ult float %33, 0.000000e+00
  %35 = fcmp ugt float %33, 0x4020000D20000000
  %36 = or i1 %34, %35
  %37 = load i32, ptr %2, align 4
  %38 = icmp ugt i32 %37, 255
  %39 = select i1 %36, i1 true, i1 %38
  %40 = select i1 %39, i32 2, i32 0
  call void @llvm.lifetime.end.p0(i64 4, ptr nonnull %3) #12
  call void @llvm.lifetime.end.p0(i64 4, ptr nonnull %2) #12
  call void @llvm.lifetime.end.p0(i64 256, ptr nonnull %1) #12
  ret i32 %40

41:                                               ; preds = %0, %41
  %42 = phi i64 [ 0, %0 ], [ %48, %41 ]
  %43 = trunc nuw nsw i64 %42 to i32
  %44 = urem i32 %43, 37
  %45 = trunc nuw nsw i32 %44 to i8
  %46 = add nuw nsw i8 %45, 11
  %47 = getelementptr inbounds [256 x i8], ptr %1, i64 0, i64 %42
  store i8 %46, ptr %47, align 1, !tbaa !5
  %48 = add nuw nsw i64 %42, 1
  %49 = icmp eq i64 %48, 256
  br i1 %49, label %4, label %41, !llvm.loop !34
}

; Function Attrs: nofree nounwind
declare noundef i32 @printf(ptr nocapture noundef readonly, ...) local_unnamed_addr #10

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.umin.i32(i32, i32) #11

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i64 @llvm.fshl.i64(i64, i64, i64) #11

attributes #0 = { nofree nounwind memory(write, argmem: readwrite) uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { mustprogress nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }
attributes #2 = { mustprogress nofree nounwind willreturn memory(write) "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { nofree norecurse nosync nounwind memory(argmem: readwrite) uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { mustprogress nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #5 = { nofree norecurse nosync nounwind memory(argmem: read) uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #6 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #7 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: write) }
attributes #8 = { nofree nounwind memory(readwrite, inaccessiblemem: write) uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #9 = { nofree nounwind uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #10 = { nofree nounwind "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #11 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #12 = { nounwind }

!llvm.module.flags = !{!0, !1, !2, !3}
!llvm.ident = !{!4}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"PIE Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 2}
!4 = !{!"clang version 17.0.0 (https://github.com/swiftlang/llvm-project.git 10999b6d034fe318f3d56c83bddb6572593a8bb0)"}
!5 = !{!6, !6, i64 0}
!6 = !{!"omnipotent char", !7, i64 0}
!7 = !{!"Simple C/C++ TBAA"}
!8 = distinct !{!8, !9, !10}
!9 = !{!"llvm.loop.mustprogress"}
!10 = !{!"llvm.loop.unroll.disable"}
!11 = !{!12, !12, i64 0}
!12 = !{!"float", !6, i64 0}
!13 = distinct !{!13, !9, !10}
!14 = distinct !{!14, !9, !10}
!15 = distinct !{!15, !9, !10}
!16 = distinct !{!16, !9, !10}
!17 = distinct !{!17, !9, !10}
!18 = distinct !{!18, !9, !10}
!19 = distinct !{!19, !9, !10}
!20 = distinct !{!20, !9, !10}
!21 = distinct !{!21, !9, !10}
!22 = !{!23, !23, i64 0}
!23 = !{!"int", !6, i64 0}
!24 = distinct !{!24, !9, !10}
!25 = distinct !{!25, !9, !10}
!26 = distinct !{!26, !9, !10}
!27 = distinct !{!27, !9, !10}
!28 = distinct !{!28, !9, !10}
!29 = distinct !{!29, !9, !10}
!30 = distinct !{!30, !9, !10}
!31 = !{!32, !32, i64 0}
!32 = !{!"any pointer", !6, i64 0}
!33 = distinct !{!33, !9, !10}
!34 = distinct !{!34, !9, !10}
