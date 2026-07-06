# Case: UNITY_OHOS vs UNITY_OPENHARMONY Macro

## Problem

Code that used `#if UNITY_OHOS` conditional compilation was not executing on OpenHarmony devices.

## Error Log

No compile error. The conditional code was simply excluded, causing runtime behavior differences.

## Diagnosis Process

1. QualityManager used `#if UNITY_OHOS` to conditionally set quality level
2. On OHOS devices, the quality level was not being set, falling back to default ("Performant")
3. "Performant" quality level has `AdditionalLightsRenderingMode = Disabled`, breaking additional lights
4. Checked Tuanjie URP source code — it uses `UNITY_OPENHARMONY`, not `UNITY_OHOS`
5. Confirmed: Tuanjie's scripting define is `UNITY_OPENHARMONY`

## Root Cause

The correct scripting define symbol for OpenHarmony in Tuanjie is **`UNITY_OPENHARMONY`**, not `UNITY_OHOS`. Using the wrong symbol means the conditional code is silently excluded.

This is a Tuanjie-specific naming convention. Stock Unity doesn't have OpenHarmony support, so there's no reference in Unity documentation.

## Fix

```csharp
// Before:
#if UNITY_OHOS || UNITY_ANDROID || UNITY_IOS

// After:
#if UNITY_OPENHARMONY || UNITY_ANDROID || UNITY_IOS || UNITY_EDITOR
```

## Lesson

**Always verify the exact scripting define symbols for engine forks.** Tuanjie uses `UNITY_OPENHARMONY` while the shorter `UNITY_OHOS` might seem intuitive but is not defined. Check the engine's source code or documentation for the correct symbols.
