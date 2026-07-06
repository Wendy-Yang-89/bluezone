# URP Runtime Pipeline Mutation: Clone vs Direct Modify

## The Problem

When you need to modify URP pipeline settings at runtime (e.g., changing MSAA, additional lights count, render scale), there are two approaches:

1. **Clone**: `Instantiate()` the pipeline asset, modify the clone, assign it to GraphicsSettings
2. **Direct Modify**: Get the active pipeline asset and modify it in-place

## Approach 1: Clone (Broken)

```csharp
var clone = Instantiate(originalUrpa);
clone.maxAdditionalLightsCount = 10;
GraphicsSettings.renderPipelineAsset = clone;
```

### Why This Seems Correct

- Intuition: "I don't want to modify the original, so I clone it"
- The original asset is preserved
- You can reset by assigning the original back

### Why It's Actually Broken

`Instantiate(UniversalRenderPipelineAsset)` performs a **shallow copy**. The problems:

1. **m_RendererDataList**: The cloned URPA's `m_RendererDataList` references the same `ScriptableRendererData` objects as the original. This is shared state — modifying the renderer data through the clone also modifies it through the original.

2. **PostProcessData**: URP internally references a `PostProcessData` ScriptableObject. The clone may have a null or broken reference to this, causing post-processing effects to fail on certain platforms.

3. **Internal Caches**: URP maintains internal caches (e.g., `m_AdditionalLightsBuffer`, `AdditionalLightsShadowCasterPass` resources) that are initialized when the pipeline first runs. The cloned asset hasn't gone through this initialization, so these caches are empty or inconsistent.

4. **Platform-Specific Failure**: On desktop/Editor, these issues may not manifest because the platform is more forgiving. On OHOS Vulkan, the pipeline's resource allocation is more sensitive — additional lights, post-processing, and other features silently fail.

5. **Renderer Feature State**: `ScriptableRendererFeature` objects on the renderer data are shared between original and clone. Their internal state (e.g., SSAO's compiled shader references) may be invalid when accessed through the clone.

## Approach 2: Direct Modify (Correct)

```csharp
var active = QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
active.maxAdditionalLightsCount = 10;
// Don't reassign — it's already the active pipeline
```

### Why This Works

- The pipeline asset is already fully initialized by Unity's rendering system
- All internal caches, buffers, and resources are valid
- Modifications are in-place — no broken references or missing state
- The pipeline sees the changes immediately (it reads from the same object)

### Why You Might Worry (But Shouldn't)

**"Won't this corrupt the asset?"**

- **Build**: The asset is loaded from read-only data. Modifications exist only in the process's memory. When the app exits, changes are discarded. Next launch gets the original values.
- **Editor PlayMode**: Yes, modifications persist to disk. But this is solved with backup/restore (see `editor-playmode-asset-persistence.md`), not with cloning.

**"What if QualitySettings.SetQualityLevel() is called?"**

- Calling `SetQualityLevel()` replaces `QualitySettings.renderPipeline` with the new level's asset. If you've modified the old asset, those changes are on the old object. You'd need to re-acquire the new active pipeline and apply your modifications again.

## Decision Matrix

| Scenario | Clone | Direct Modify |
|---|---|---|
| Build (OHOS/Android/iOS) | Broken (internal state) | Correct |
| Editor PlayMode (with backup/restore) | Unnecessary complexity | Correct |
| Editor Tooling (not PlayMode) | Acceptable for preview | Correct |
| Multiple quality levels | Complex (need clone per level) | Simple (re-acquire on level change) |

## Our Implementation

```csharp
// UrpManager.cs
void Awake()
{
    // Get the already-active pipeline, don't create a new one
    activeUrpa = QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
    if (activeUrpa == null)
        activeUrpa = GraphicsSettings.renderPipelineAsset as UniversalRenderPipelineAsset;
    // ... acquire activeUrd via reflection ...
    
    #if UNITY_EDITOR
    BackupEditorState();  // Save originals for Editor PlayMode
    #endif
}

void OnDestroy()
{
    #if UNITY_EDITOR
    RestoreEditorState();  // Undo modifications in Editor
    #endif
}
```

## Key Takeaway

**Never `Instantiate()` engine-internal ScriptableObjects that the rendering system manages.** The shallow copy creates an object with inconsistent internal state. Direct modification of the active pipeline is correct, safe in builds, and manageable in the Editor with backup/restore.
