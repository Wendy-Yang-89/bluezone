# Additional Lights in URP: Keywords, Rendering Modes, and Pipeline Configuration

## Overview

In URP, "Additional Lights" refers to all lights except the main directional light — point lights, spot lights, and area lights. These lights require specific pipeline configuration and shader keyword support to render correctly.

## The Three Layers of Configuration

### Layer 1: Pipeline Asset — AdditionalLightsRenderingMode

`UniversalRenderPipelineAsset` has an internal field `m_AdditionalLightsRenderingMode` with three values:

| Value | Mode | Behavior |
|---|---|---|
| 0 | Disabled | Additional lights are completely ignored. Only the main directional light renders. |
| 1 | Per Pixel | Additional lights are rendered per-pixel (higher quality, more expensive) |
| 2 | Per Vertex | Additional lights are rendered per-vertex (lower quality, cheaper) |

**Critical**: If this is set to `Disabled` (0), no point/spot lights will render regardless of any other settings. This is the default for the "Performant" quality level.

This field is **private** (`m_AdditionalLightsRenderingMode`), so it must be accessed via reflection:

```csharp
FieldInfo field = typeof(UniversalRenderPipelineAsset).GetField(
    "m_AdditionalLightsRenderingMode",
    BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public
);
field.SetValue(activeUrpa, 1);  // PerPixel
```

### Layer 2: Pipeline Asset — maxAdditionalLightsCount

`UniversalRenderPipelineAsset.maxAdditionalLightsCount` (public property) controls how many additional lights can affect a single object. This is a **per-object limit** — if you have 20 point lights but `maxAdditionalLightsCount = 4`, each object will only be lit by the 4 brightest/closest lights.

```csharp
activeUrpa.maxAdditionalLightsCount = 16;
```

The runtime constant `UniversalRenderPipeline.maxVisibleAdditionalLights` reflects the actual limit in use.

### Layer 3: Shader Keyword — _ADDITIONAL_LIGHTS

The `_ADDITIONAL_LIGHTS` shader keyword must be enabled for the Lit/SimpleLit shaders to include the additional lights rendering pass. URP typically enables this automatically when:
- `AdditionalLightsRenderingMode` is not Disabled
- There is at least one additional light in the scene
- The object's material supports the keyword

Check at runtime:

```csharp
Debug.Log(Shader.IsKeywordEnabled("_ADDITIONAL_LIGHTS"));
```

## Common Failure Modes

### Failure 1: Wrong Quality Level → Disabled Mode

If the quality level is "Performant" (AdditionalLightsRenderingMode = 0/Disabled), no additional lights render. This was caused by the `UNITY_OHOS` vs `UNITY_OPENHARMONY` macro bug (see `cases/unity-openharmony-macro.md`).

**Symptom**: Lights are created, `_ADDITIONAL_LIGHTS` keyword is off, no visual effect from point/spot lights.

**Fix**: Set quality level to "High Fidelity" (or any level with PerPixel mode).

### Failure 2: Cloned URPA Loses Internal State

When `Instantiate()` is used to clone the URPA, the clone's internal buffer allocation for additional lights may be broken, especially on OHOS Vulkan. (See `cases/urpa-clone-pipeline-break.md`.)

**Symptom**: All settings look correct in logs, but lights still don't render on device.

**Fix**: Modify the original URPA directly instead of cloning.

### Failure 3: Shader Variant Stripped

The `_ADDITIONAL_LIGHTS` variant of URP Lit/SimpleLit may be stripped from the build if not explicitly referenced. (See `knowledge/shader-stripping-and-svc.md`.)

**Symptom**: Works in Editor, fails in build. Frame Debugger shows no additional lights pass.

**Fix**: Add `_ADDITIONAL_LIGHTS` variants to ShaderVariantCollection.

## Dynamic maxAdditionalLightsCount Adjustment

In LightManager, the limit is dynamically adjusted based on the number of active additional lights:

```csharp
private void UpdateMaxAdditionalLights()
{
    if (urpMgr == null) return;
    if (UniversalRenderPipeline.asset == null) return;  // safety guard for OnDestroy

    int additionalCount = 0;
    foreach (Light l in lights)
    {
        if (l != null && l.type != LightType.Directional)
            additionalCount++;
    }

    int maxLights = Mathf.Max(additionalCount, 8);
    urpMgr.SetUrpMaxAdditionalLightsCount(maxLights);
}
```

The minimum of 8 ensures the pipeline always has some headroom even with 0 additional lights (prevents overhead from constant re-allocation when adding the first few lights).

## Quality Level Configuration

In this project, the URP assets for each quality level are configured as:

| Quality Level | AdditionalLightsRenderingMode | PerObjectLimit | File |
|---|---|---|---|
| Performant | 0 (Disabled) | 4 | `Assets/Settings/URP-Performant.asset` |
| Balanced | 1 (PerPixel) | 2 | `Assets/Settings/URP-Balanced.asset` |
| High Fidelity | 1 (PerPixel) | 8 | `Assets/Settings/URP-HighFidelity.asset` |

The `QualityManager` sets "High Fidelity" at startup, then `LightManager` dynamically increases `maxAdditionalLightsCount` as lights are added.

## Diagnostics

Use UrpManager's `LogAdditionalLightsDiagnostics()` to dump a complete diagnostic report:

```csharp
urpMgr.LogAdditionalLightsDiagnostics();
```

This prints:
- `maxAdditionalLightsCount` and `maxVisibleAdditionalLights`
- `additionalLightsRenderingMode` (via reflection)
- `additionalLightsPerObjectLimit` (via reflection)
- Current quality level and bound pipeline asset
- All lights in the scene (type, enabled, intensity, range)
- All renderers in the scene (shader, layer, receiveShadows)
- `_ADDITIONAL_LIGHTS` keyword status
