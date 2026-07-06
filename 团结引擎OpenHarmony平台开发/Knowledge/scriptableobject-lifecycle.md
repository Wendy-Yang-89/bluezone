# ScriptableObject Lifecycle: Editor vs Build

## Overview

ScriptableObject assets have fundamentally different lifecycle behaviors in the Unity Editor versus in a built player. Understanding this difference is critical for any project that modifies ScriptableObject assets at runtime.

## In the Editor

### Loading

ScriptableObject assets are loaded from disk into memory when first accessed. The in-memory instance IS the asset — there is no copy.

### Modification During PlayMode

When you modify a ScriptableObject's fields during PlayMode:

1. The modification happens to the **same object** that represents the asset on disk
2. When PlayMode ends, Unity **does NOT revert** ScriptableObject changes
3. The modified values persist to the asset file on disk
4. This is unlike MonoBehaviour/Component fields on scene objects, which Unity does auto-revert

This is a well-known Unity behavior that catches many developers off guard.

### Why This Happens

Unity's PlayMode state management uses **serialization** for scene objects. When entering PlayMode:
1. Unity serializes the current scene state
2. During PlayMode, modifications happen to the deserialized copy
3. When exiting, Unity re-serializes from the saved state, effectively "undoing" changes

But ScriptableObject assets are **project assets, not scene objects**. They are not part of the scene serialization domain. Unity doesn't track their original state because they're shared resources that exist outside the scene hierarchy.

### The Backup/Restore Pattern

To safely modify ScriptableObjects during Editor PlayMode:

```csharp
#if UNITY_EDITOR
private OriginalValues backup;

void Awake()
{
    backup = CaptureCurrentValues(scriptableObject);
    ModifyScriptableObject(scriptableObject);
}

void OnDestroy()
{
    RestoreValues(scriptableObject, backup);
}
#endif
```

Key considerations:
- Use `#if UNITY_EDITOR` — this is unnecessary in builds
- Backup BEFORE any modification
- Restore in `OnDestroy` (fires when exiting PlayMode)
- For reflection-based fields, use `Dictionary<string, object>` to capture all fields

## In a Built Player

### Loading

ScriptableObject assets are bundled into the player's data files. They are loaded into memory on first access.

### Modification at Runtime

When you modify a ScriptableObject's fields at runtime in a build:

1. The modification happens to the **in-memory copy** of the asset
2. The asset file on disk (inside the .apk/.app/.hap) is **read-only**
3. The modifications exist only in the process's memory
4. When the process exits, all modifications are discarded
5. Next launch loads the original asset values from disk

**No backup/restore is needed in builds.** This is why our UrpManager backup system uses `#if UNITY_EDITOR`.

### What About AssetBundles?

If the ScriptableObject comes from an AssetBundle:
- Same rules apply within the session
- Modifications persist in memory until the AssetBundle is unloaded
- `AssetBundle.Unload(true)` destroys modified instances
- `AssetBundle.Unload(false)` leaves modified instances in memory (dangerous)

## Common Pitfalls

1. **"I modified it in PlayMode and it stuck!"** — This is the #1 surprise. ScriptableObject changes persist in Editor.

2. **"I Instantiate()'d it, so it's safe"** — `Instantiate()` creates a shallow copy. Internal references (to other ScriptableObjects, textures, etc.) still point to the original assets. This can cause subtle bugs.

3. **"EditorUtility.SetDirty() will help"** — No, this marks the asset as modified for saving. It makes persistence MORE likely, not less.

4. **"ScriptableObject.CreateInstance() is the same as new"** — No. `CreateInstance()` goes through Unity's native initialization. `new` creates an unmanaged C# object that Unity doesn't track.

5. **"I'll just reset values in OnDisable"** — `OnDisable` is not guaranteed to fire when exiting PlayMode in all Unity versions. `OnDestroy` is more reliable for MonoBehaviour cleanup.
