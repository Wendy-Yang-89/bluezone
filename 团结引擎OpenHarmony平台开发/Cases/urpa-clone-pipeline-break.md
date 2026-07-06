# Case: URPA Instantiate Breaks Pipeline on OHOS Vulkan

## Problem

After adding point/spot lights on OpenHarmony (OHOS), additional lights did not render. The scene only had the directional light. This worked correctly in the Unity Editor and on Android.

## Error Log

No explicit error was logged. The symptom was a silent rendering failure:
- `LightManager.AddLights()` logged lights being created successfully
- `maxAdditionalLightsCount` was set correctly via `urpMgr.SetUrpMaxAdditionalLightsCount()`
- `Shader.IsKeywordEnabled("_ADDITIONAL_LIGHTS")` returned `true`
- All light objects had correct type, intensity, range, and position
- But point/spot lights had **zero visual effect** on the model

## Diagnosis Process

1. **Verified light creation**: All lights had correct `LightType`, `intensity`, `range`, `position`. No lights were null or disabled.
2. **Verified URP settings**: `maxAdditionalLightsCount` was being set to the expected value.
3. **Verified shader keyword**: `Shader.IsKeywordEnabled("_ADDITIONAL_LIGHTS")` returned `true`, indicating the shader was prepared for additional lights.
4. **Verified rendering mode**: `AdditionalLightsRenderingMode` was `PerPixel` (not Disabled).
5. **Compared platforms**: Worked in Editor, worked on Android, failed on OHOS.
6. **Suspected UrpManager's clone approach**: UrpManager was cloning the URPA via `Instantiate(baseUrpa)` on `Awake()`, then assigning the clone to `GraphicsSettings.renderPipelineAsset`.
7. **Tested without cloning**: Removed the clone, modified the original URPA directly — additional lights rendered correctly on OHOS.

## Root Cause

`Instantiate(UniversalRenderPipelineAsset)` performs a **shallow copy**. The cloned URPA shares the same `m_RendererDataList` array reference as the original, but several critical internal states are broken:

### 1. PostProcessData

URP internally references a `PostProcessData` ScriptableObject that provides shared post-processing resources (shaders, textures, etc.). The cloned URPA's reference to this object may be null or broken on certain platforms. This causes post-processing effects to fail silently.

### 2. Internal Caches and Buffers

URP maintains internal caches that are initialized when the pipeline first runs:
- `m_AdditionalLightsBuffer`: GPU buffer for additional light data (position, color, intensity, etc.)
- `AdditionalLightsShadowCasterPass`: Shadow rendering resources for additional lights
- Various renderer-internal state objects

The cloned asset bypasses this initialization. On some platforms, these caches remain empty, so URP has no GPU buffer to write light data into.

### 3. Platform-Specific Sensitivity

On desktop/Editor, these issues may not manifest because:
- The desktop GPU driver is more forgiving of uninitialized resources
- The Vulkan validation layers in the Editor are less strict
- The Editor may re-initialize some pipeline state when the asset is assigned

On OHOS Vulkan, the pipeline's resource allocation is more sensitive:
- The Vulkan driver requires properly allocated buffers before rendering
- The mobile GPU has stricter memory management
- Missing buffer allocations result in silent rendering failures (no error, no output)

### 4. Renderer Feature State

`ScriptableRendererFeature` objects on the `UniversalRendererData` (e.g., SSAO) are shared between the original and clone. Their internal compiled shader references and GPU resources may be invalid when accessed through the clone's rendering path.

## Fix

Replaced the clone approach with direct modification of the active pipeline asset:

```csharp
// Before (broken on OHOS):
void Awake()
{
    baseUrpa = QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
    runtimeUrpa = Instantiate(baseUrpa);
    GraphicsSettings.renderPipelineAsset = runtimeUrpa;
}

// After (correct):
void Awake()
{
    activeUrpa = QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
    // Modify activeUrpa directly — no cloning, no reassignment
}
```

**Why this works**: `QualitySettings.renderPipeline` returns the URPA that Unity's rendering system has already fully initialized. All internal caches, buffers, and GPU resources are valid. Modifying its properties in-place is safe because the pipeline reads from the same object each frame.

**Editor safety**: Since modifying the URPA directly persists changes to disk in Editor PlayMode, we added backup/restore (see `cases/editor-playmode-asset-persistence.md`):

```csharp
void Awake()
{
    AcquireActivePipeline();
    BackupEditorState();  // #if UNITY_EDITOR only
}

void OnDestroy()
{
    RestoreEditorState();  // #if UNITY_EDITOR only
}
```

## Lesson

**Do not `Instantiate()` ScriptableObject assets that the engine uses internally for rendering.** The shallow copy creates an object with inconsistent internal state. The failure is:
- **Silent** — no error or warning
- **Platform-specific** — may work on desktop but fail on mobile
- **Hard to diagnose** — all visible parameters look correct

Direct modification of the active pipeline is correct, safe in builds, and manageable in the Editor with backup/restore.
