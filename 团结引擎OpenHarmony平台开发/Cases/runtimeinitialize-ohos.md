# Case: RuntimeInitializeOnLoadMethod Not Firing on OHOS

## Problem

`QualityManager` used `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]` to set the quality level before any scene loaded. On OpenHarmony, this method sometimes did not execute.

## Error Log

No error. The quality level was not set, causing the default "Performant" level to be used instead of "High Fidelity".

## Diagnosis Process

1. Added logging to `QualityManager.InitializeQuality()` — confirmed it wasn't being called on some OHOS runs
2. Checked Unity documentation — `RuntimeInitializeOnLoadMethod` should fire for all platforms
3. Discovered this is a known issue in Tuanjie's OHOS runtime
4. The OHOS app lifecycle management may skip certain initialization callbacks

## Root Cause

Tuanjie's OpenHarmony runtime has a known issue where `RuntimeInitializeOnLoadMethod` callbacks may not fire reliably. This is likely due to differences in how the OHOS app lifecycle integrates with Unity's initialization sequence.

## Fix

Dual-trigger mechanism — both `RuntimeInitializeOnLoadMethod` and `Awake()` attempt initialization, gated by a static flag:

```csharp
private static bool initialized = false;

[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
static void InitializeQuality()
{
    SetHighFidelity();
}

void Awake()
{
    if (!initialized)
    {
        SetHighFidelity();
    }
}

static void SetHighFidelity()
{
    initialized = true;
    // ... set quality level
}
```

The `static bool initialized` ensures `SetHighFidelity()` runs exactly once regardless of which trigger fires first.

## Lesson

**On non-standard platforms (engine forks, custom OS), don't rely on a single initialization mechanism.** Use multiple triggers (RuntimeInitialize + Awake, etc.) with idempotency guards to ensure critical setup code runs.
