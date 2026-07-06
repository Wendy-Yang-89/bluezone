# GI Environment Refresh: Why Toggling Modes Is Necessary

## Overview

When changing the skybox material or URP rendering mode at runtime, the scene's environment lighting (ambient light, reflections) doesn't automatically update. Several Unity APIs must be called in a specific pattern to force a complete refresh.

## The Problem

After calling `RenderSettings.skybox = newSkyboxMaterial`, you might expect:
- Ambient lighting to update based on the new skybox colors
- Specular reflections to show the new skybox
- The environment to look consistent with the new skybox

But without explicit refresh calls, the scene retains the old lighting. The skybox image changes, but everything illuminated by it still uses the old ambient/reflection data.

## The Refresh Pattern

```csharp
// 1. Apply the new skybox
RenderSettings.skybox = skyboxMaterial;

// 2. Force ambient lighting recalculation
RenderSettings.ambientMode = AmbientMode.Flat;
RenderSettings.ambientMode = AmbientMode.Skybox;

// 3. Trigger global illumination update
DynamicGI.UpdateEnvironment();

// 4. Force reflection recalculation (fixes black specular)
if (RenderSettings.customReflectionTexture == null)
{
    RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
    RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
}
```

## Why Each Step Is Necessary

### Step 2: Ambient Mode Toggle

`DynamicGI.UpdateEnvironment()` alone is **insufficient** to recalculate ambient lighting when the skybox changes. The ambient mode toggle triggers an internal Unity callback that re-samples the skybox for ambient color:

- Setting `AmbientMode.Flat` tells Unity "use a flat ambient color"
- Setting `AmbientMode.Skybox` tells Unity "sample the skybox for ambient color"
- The transition from Flat → Skybox forces Unity to re-read the current skybox material

Without this toggle, `DynamicGI.UpdateEnvironment()` may use cached ambient values from the previous skybox.

### Step 3: DynamicGI.UpdateEnvironment()

This API updates the real-time global illumination system with the current environment settings. It tells the GI system to re-converge based on the new skybox. This is necessary for:
- Real-time GI lit objects
- Ambient probe updates
- Lightmap-adjacent systems

### Step 4: Default Reflection Mode Toggle

When no manual Reflection Probe exists in the scene, Unity generates a default reflection from the skybox. After changing the skybox, this default reflection can become stale, resulting in **black specular highlights** on metallic/smooth objects.

The toggle forces Unity to regenerate the default reflection cubemap (SpecCube):
- Setting `Custom` tells Unity "use a custom reflection texture"
- Setting `Skybox` tells Unity "generate reflection from the skybox"
- The transition forces regeneration of the internal SpecCube texture

**Important**: The `if (RenderSettings.customReflectionTexture == null)` guard ensures we only do this when no manual reflection is assigned. If a custom reflection exists, toggling to Skybox would discard it.

## When to Use This Pattern

- After changing `RenderSettings.skybox` (SkyboxManager.ApplySkyboxToScene)
- After changing URP rendering mode (UrpManager.SetUrpRenderingMode → RefreshGI)
- After any runtime modification that affects environment lighting

## Why Not Just DynamicGI.UpdateEnvironment()?

A common mistake is calling only `DynamicGI.UpdateEnvironment()` and expecting everything to refresh. This works for some cases (e.g., when a light changes intensity) but not for skybox changes. The ambient mode and reflection mode toggles trigger additional internal callbacks that `UpdateEnvironment()` doesn't cover.

## Editor vs Build

This pattern works identically in both Editor and Build. The toggles are lightweight — they don't cause visible flickering because the mode transitions happen within the same frame.

## Performance Considerations

- `DynamicGI.UpdateEnvironment()` can be expensive if the scene has many real-time GI lit objects
- The ambient/reflection mode toggles are cheap (they set a flag and schedule an update)
- Only call this when the skybox or rendering mode actually changes, not every frame
