# URP Pipeline Asset Priority: QualitySettings vs GraphicsSettings

## The Two Pipeline References

Unity has two places where a render pipeline asset can be assigned:

1. **`GraphicsSettings.renderPipelineAsset`** — Global, project-level default
2. **`QualitySettings.renderPipeline`** — Per quality level override

## Priority Rules

When Unity determines which pipeline asset to use:

```
QualitySettings.renderPipeline  >  GraphicsSettings.renderPipelineAsset
```

If the current quality level has a pipeline asset assigned, it **always** takes precedence over the global GraphicsSettings one. If the quality level has no pipeline assigned (null), Unity falls back to `GraphicsSettings.renderPipelineAsset`.

## How Quality Level Switching Works

When you call `QualitySettings.SetQualityLevel(index, true)`:

1. Unity switches to the quality level at `index`
2. If that quality level has a `renderPipeline` assigned, it becomes the active pipeline
3. `QualitySettings.renderPipeline` returns this new pipeline
4. All rendering switches to the new pipeline
5. If the new pipeline is a different type (e.g., switching from URP to HDRP), all cameras re-initialize

## Impact on This Project

In Tuanjie 2022.3.62t2, the quality levels are configured as:

| Quality Level | URP Asset | AdditionalLightsRenderingMode | PerObjectLimit |
|---|---|---|---|
| Performant | URP-Performant | 0 (Disabled) | 4 |
| Balanced | URP-Balanced | 1 (PerPixel) | 2 |
| High Fidelity | URP-HighFidelity | 1 (PerPixel) | 8 |

`QualityManager` sets the quality to "High Fidelity" at startup, which binds `URP-HighFidelity.asset` to `QualitySettings.renderPipeline`. `UrpManager` then reads this reference to get the active URPA.

**Critical**: `QualityManager` uses `[RuntimeInitializeOnLoadMethod(BeforeSceneLoad)]` which runs before any `MonoBehaviour.Awake()`. This ensures the quality level is already set (and `QualitySettings.renderPipeline` is updated) before `UrpManager.Awake()` runs. The ordering in `Demo.LoadScripts()` is a secondary safeguard.

## Runtime Mutation

When you modify `QualitySettings.renderPipeline` at runtime:

- **Editor**: The modified ScriptableObject persists to disk
- **Build**: Modifications are in-memory only (assets are read-only in the player)

This is why UrpManager uses `#if UNITY_EDITOR` backup/restore.
