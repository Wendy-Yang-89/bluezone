# Case: ScriptableObject Asset Changes Persist After Editor PlayMode Exit

## Problem

When entering PlayMode in the Unity Editor, runtime modifications to `UniversalRenderPipelineAsset` and `UniversalRendererData` (e.g., changing MSAA, render scale, shadow settings) persisted after exiting PlayMode. The asset files on disk were modified.

## Error Log

No error. The symptom was that URP asset values changed during play were not reverted after stopping play.

## Diagnosis Process

1. Modified `renderScale` to 0.5 during PlayMode
2. Exited PlayMode
3. Inspected the URP asset — `renderScale` was still 0.5
4. Confirmed: `UniversalRenderPipelineAsset` is a ScriptableObject asset on disk
5. Direct modifications to ScriptableObject assets in PlayMode are written to the serialized data

## Root Cause

A common misconception: **Unity only auto-reverts changes to scene objects (GameObject/Component) when exiting PlayMode.** ScriptableObject assets are NOT scene objects — they live in the project's asset database. Modifying them during PlayMode modifies the actual disk asset, which persists.

This is especially insidious because:
- In the Editor, ScriptableObject assets are loaded from disk and their in-memory representation IS the asset
- There is no "domain reload" protection for ScriptableObject modifications
- The change is invisible until you check the asset or see side effects in the next play session

This is distinct from Build behavior:
- **Editor PlayMode**: Asset modifications persist to disk (need backup/restore)
- **Build**: Assets are read-only in the built player; modifications are in-memory only and discarded when the process exits

## Fix

Added `#if UNITY_EDITOR` backup/restore system in `UrpManager`:

```csharp
void Awake()
{
    AcquireActivePipeline();
    BackupEditorState();  // save all property values
}

void OnDestroy()
{
    RestoreEditorState();  // write back original values
}
```

The backup covers:
- All public URPA properties (maxAdditionalLightsCount, msaaSampleCount, supportsHDR, renderScale, upscalingFilter)
- All private URPA fields accessed via reflection (m_SoftShadowsSupported, m_SoftShadowQuality, m_AdditionalLightsRenderingMode, m_AdditionalLightsPerObjectLimit)
- URD properties (renderingMode)
- SSAO feature settings (all fields via reflection Dictionary)

The backup uses `#if UNITY_EDITOR` so it compiles to nothing in builds.

## Lesson

**ScriptableObject assets modified at runtime in the Editor will persist to disk.** Always implement a backup/restore mechanism for any ScriptableObject you modify during PlayMode. This does not apply to builds where assets are read-only.
