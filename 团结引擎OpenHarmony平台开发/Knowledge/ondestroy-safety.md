# OnDestroy Safety Patterns in Unity Runtime Scripts

## Overview

When a MonoBehaviour's `OnDestroy()` is called, the application state may be partially torn down. This can cause null reference exceptions and other errors if cleanup code naively accesses objects that have already been destroyed.

This is especially problematic when:
- Exiting PlayMode in the Editor
- Loading a new scene that destroys the current scene's objects
- The script holds references to other objects that may be destroyed first

## Common Failure Scenarios

### 1. UniversalRenderPipeline.asset Is Null

When exiting PlayMode, Unity's render pipeline may be unbound before `OnDestroy()` runs:

```csharp
// Dangerous:
void OnDestroy()
{
    urpMgr.SetUrpMaxAdditionalLightsCount(0);  // may crash if pipeline is null
}
```

**Fix**: Guard with null check:

```csharp
void OnDestroy()
{
    if (UniversalRenderPipeline.asset == null) return;
    urpMgr.SetUrpMaxAdditionalLightsCount(0);
}
```

### 2. Referenced Managers Are Already Destroyed

In the single-GameObject pattern, all managers are on the same GameObject. Unity destroys components in an undefined order. If LightManager's `OnDestroy` tries to access UrpManager, it may already be null:

```csharp
// Dangerous:
void OnDestroy()
{
    urpMgr.SetUrpSupportsSoftShadows(true);  // urpMgr may be null
}
```

**Fix**: Simplify OnDestroy to not depend on other managers:

```csharp
void OnDestroy()
{
    // Direct cleanup, no cross-manager dependencies
    for (int i = lights.Count - 1; i >= 0; i--)
    {
        if (lights[i] != null) Destroy(lights[i].gameObject);
    }
    lights.Clear();
}
```

### 3. Destroy vs DestroyImmediate

In Editor edit mode (not PlayMode), `Destroy()` is queued and won't execute until the next frame, which never comes. Use `DestroyImmediate()` instead:

```csharp
if (Application.isEditor && !Application.isPlaying)
    DestroyImmediate(obj);
else
    Destroy(obj);
```

### 4. Scene Objects Already Destroyed

When a scene is unloaded, all GameObjects in that scene are destroyed. If `OnDestroy` tries to find or access scene objects:

```csharp
// Dangerous:
void OnDestroy()
{
    Camera.main.Reset();  // Camera.main may be null
}
```

**Fix**: Cache references during Awake/Start and null-check in OnDestroy:

```csharp
private Camera mainCamera;  // cached in Start()

void OnDestroy()
{
    if (mainCamera != null)
    {
        mainCamera.Reset();
    }
}
```

## Patterns Used in This Project

### LightManager.OnDestroy — Simplified Direct Cleanup

```csharp
private void OnDestroy()
{
    for (int i = lights.Count - 1; i >= 0; i--)
    {
        RemoveLight(i);
    }
    lights.Clear();
}
```

Does NOT call `RemoveLights()` (which would call `urpMgr.SetUrpMaxAdditionalLightsCount()`), because UrpManager may already be destroyed. Instead, just destroys the GameObjects directly.

### CameraManager.OnDestroy — Cached Reference + Null Check

```csharp
private void OnDestroy()
{
    if (mainCamera != null)
    {
        mainCamera.Reset();
        mainCamera = null;
        mainCameraData = null;
    }
    urpMgr = null;  // just null the reference, don't try to use it
}
```

### UrpManager.OnDestroy — Editor State Restore

```csharp
private void OnDestroy()
{
    RestoreEditorState();  // restores original property values
}
```

`RestoreEditorState()` internally checks `backupSaved` and `activeUrpa != null` before doing anything.

### VolumeManager.OnDestroy — Dual Destruction

```csharp
private void OnDestroy()
{
    DestroyPostProcessingEffects();  // just null references
    DestroyGlobalVolume();           // uses DestroyImmediate in edit mode
    urpMgr = null;
}
```

## General Guidelines

1. **Don't call methods on other managers in OnDestroy** — they may already be destroyed
2. **Cache references during initialization** — don't use `FindObjectOfType<>()` or `.main` in OnDestroy
3. **Null-check everything** — assume any reference may be null
4. **Use the Editor/Build dual destruction pattern** for runtime-created objects
5. **Keep OnDestroy simple** — only destroy objects you created, don't try to "undo" state changes that affect other systems
6. **Guard with `UniversalRenderPipeline.asset == null`** before any URP-related operations
