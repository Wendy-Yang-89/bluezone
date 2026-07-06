# Case: MotionBlurMode.CameraOnly Does Not Generate Motion Vectors

## Problem

Setting Motion Blur mode to `CameraOnly` in VolumeManager had no visual effect — motion blur appeared disabled even when the effect was active.

## Error Log

No error. Motion blur simply had no visual result.

## Diagnosis Process

1. Enabled Motion Blur with `MotionBlurMode.CameraOnly`
2. Observed no blur effect
3. Examined URP source code `UniversalRenderer.cs`
4. Found that motion vector generation is gated by `requiresMotionVectors`

## Root Cause

In URP source code (`UniversalRenderer.cs` around line 1863), the `requiresMotionVectors` flag is only set to `true` when `MotionBlurMode == CameraAndObjects`:

```csharp
// Simplified URP source:
if (motionBlur.mode == MotionBlurMode.CameraAndObjects)
{
    requiresMotionVectors = true;
}
```

When `MotionBlurMode.CameraOnly` is used, URP assumes motion vectors are not needed and skips the motion vector rendering pass. Without the motion vector texture, the CameraMotionBlur post-processing effect has no data to work with, resulting in no visible blur.

This is somewhat counter-intuitive — `CameraOnly` sounds like it should work with camera-based motion, but URP's implementation requires the full motion vector pass regardless.

## Fix

Changed default `MotionBlurMode` from `CameraOnly` to `CameraAndObjects`:

```csharp
public MotionBlurMode motionBlurMode = MotionBlurMode.CameraAndObjects;
```

## Lesson

**Read the engine source code when an effect "should work but doesn't."** URP's Motion Blur requires `CameraAndObjects` mode to trigger motion vector generation. `CameraOnly` mode exists as an enum value but doesn't actually produce motion vectors in URP 14.x.
