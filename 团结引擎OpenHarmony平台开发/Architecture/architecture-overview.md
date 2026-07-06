# UnityDemo Architecture Overview

## Project Info

- **Engine**: Tuanjie 2022.3.62t2 (Unity fork, not stock Unity Editor)
- **Render Pipeline**: URP 14.1.0
- **UI Framework**: TextMeshPro 3.0.9
- **Target Platforms**: OpenHarmony (OHOS), Android, iOS, Editor
- **Build Backend**: IL2CPP

## Repository Layout

```
UnityDemo/
  SkyboxDemo/                <- Unity project (open this folder in Unity Hub)
    Assets/
      Scripts/               <- All C# runtime scripts (see manager-scripts-detail.md)
      Resources/             <- Runtime-loaded assets (Resources.Load<>() only)
        Models/              <- Suzanne variants (Suzanne_5w, _20w, _50w, _100w)
        Prefabs/             <- UI prefabs (Canvas, Panel, Button, Dropdown, etc.)
        Textures/            <- Skybox textures, test textures
        ShaderVariants.shadervariants  <- SVC for URP shader variant preservation
      Editor/                <- Editor-only scripts (IncludeShaders.cs)
      Shaders/               <- Custom shaders (TextureArrayGrid.shader)
      Settings/              <- URP pipeline assets bound to QualitySettings levels
        URP-Performant.asset
        URP-Balanced.asset
        URP-HighFidelity.asset
    Packages/manifest.json   <- Package versions
  CommonModels/              <- Source copies of 3D models (also in Resources/Models/)
  CommonPrefabs/             <- Source copies of UI prefabs
  CommonScipts/              <- Source copies of scripts (directory name has typo)
  CommonTextures/            <- Source copies of HDR textures
```

> **Note**: The `Common*` root directories are **source/out-of-Unity backups**, not loaded by the game. The runtime code only reads from `SkyboxDemo/Assets/Resources/`.

## Architecture

### Single-GameObject Pattern

All manager scripts attach to a **single GameObject**. `Demo.cs` is the entrypoint:

```
Demo.Start()
  -> LoadScripts()     // GetComponent or AddComponent for each manager
  -> DrawUI()          // Each manager's DrawUI(UIBuilder) creates its UI section
```

No Canvas or UI exists in the scene hierarchy before play — everything is constructed programmatically at runtime.

### Initialization Order (Demo.LoadScripts)

The order matters because later managers reference earlier ones:

| # | Manager | Key Action | Dependencies |
|---|---|---|---|
| 1 | UIBuilder | Loaded first, disabled (`enabled = false`) | None |
| 2 | QualityManager | Sets quality level => binds URP pipeline asset | None |
| 3 | UrpManager | Acquires active pipeline from `QualitySettings.renderPipeline` | QualityManager must run first |
| 4 | CameraManager | Gets `urpMgr` reference | UrpManager |
| 5 | VolumeManager | Gets `urpMgr` reference | UrpManager |
| 6 | LightManager | Gets `urpMgr` reference | UrpManager |
| 7 | SkyboxManager | Standalone | None |
| 8 | ModelImporter | Standalone | None |
| 9 | MaterialManager | Gets `modelImporter` reference | ModelImporter |
| 10 | TextureManager | Standalone | None |
| 11 | TransparentManager | Standalone | None |

**Why QualityManager must run before UrpManager**: `QualitySettings.SetQualityLevel()` binds the URP asset for that quality level to `QualitySettings.renderPipeline`. UrpManager reads this property to get the active pipeline. If the quality level isn't set first, UrpManager may get the wrong pipeline or null.

### Manager Dependency Graph

```
QualityManager ──sets quality──> QualitySettings.renderPipeline (=> URP-HighFidelity.asset)
UrpManager ──reads──> QualitySettings.renderPipeline (=> activeUrpa, activeUrd)
    ├── CameraManager.urpMgr   (MSAA, HDR)
    ├── VolumeManager.urpMgr   (SSAO via reflection, RenderScale, UpscalingFilter)
    └── LightManager.urpMgr    (SoftShadows, MaxAdditionalLights)
ModelImporter ──provides renderer──> MaterialManager.modelImporter
```

### Quality Level URP Asset Binding

Each quality level in Project Settings > Quality is bound to a specific URP asset:

```
Quality Level          URP Asset                    AdditionalLights
────────────────────────────────────────────────────────────────────
Performant (index 0)   Assets/Settings/URP-Performant    Mode=Disabled, Limit=4
Balanced (index 1)     Assets/Settings/URP-Balanced      Mode=PerPixel, Limit=2
High Fidelity (index 2) Assets/Settings/URP-HighFidelity Mode=PerPixel, Limit=8
```

When `QualityManager.SetHighFidelity()` calls `QualitySettings.SetQualityLevel(2, true)`, Unity binds `URP-HighFidelity.asset` to `QualitySettings.renderPipeline`. This is the asset that UrpManager acquires and modifies.

### Key Design Patterns

#### 1. Runtime UI Construction (UIBuilder)

All UI is built programmatically at runtime. No Canvas exists in the scene hierarchy before play.

- Prefabs loaded via `Resources.Load<GameObject>("Prefabs/[name]")`
- `UIBuilder.CreateCanvas()` creates the root Canvas
  - Mobile: `CanvasScaler.ScaleWithScreenSize` with `referenceResolution = Screen.size / 3.0`
  - Desktop: `CanvasScaler.ConstantPixelSize` with `scaleFactor = 1.0`
- ScrollView with `VerticalLayoutGroup` + `ContentSizeFitter` as the main container
- Each manager calls `uUIBuilder.CreateText/Dropdown/Toggle/Slider/Button()`
- All UI elements use `LayoutElement.preferredHeight = 10` for consistent spacing (no per-element scaling)

#### 2. DrawUI(UIBuilder) Pattern

Every manager implements a `DrawUI(UIBuilder)` method called by `Demo.DrawUI()`. The pattern:

```
Manager UI = Inspector fields + Runtime UI widgets + Event handlers

Inspector fields  ──OnValidate──>  Runtime UI widgets (sync UI to Inspector)
Runtime UI widgets ──OnXxxChange──>  Inspector fields (sync Inspector to UI)
Both ──"Update" button──>  Apply to runtime objects
```

This creates a **tri-directional sync**: Inspector ↔ UI widgets ↔ Runtime objects. The "Update" button is the explicit trigger that applies the current Inspector state to the actual runtime objects (materials, lights, camera, etc.).

#### 3. Runtime URP Mutation (UrpManager)

UrpManager acquires the active `UniversalRenderPipelineAsset` from `QualitySettings.renderPipeline`, then exposes Set methods for properties that other managers need. It does NOT clone the pipeline asset — it modifies the current one directly.

- **Editor**: `Awake()` backs up all modified properties; `OnDestroy()` restores them
- **Build**: No backup needed (asset modifications are in-memory only, discarded on process exit)

See `knowledge/urp-pipeline-mutation.md` for the full analysis of why cloning is broken.

#### 4. Reflection for Internal URP Fields

Some URP properties lack public setters:
- `m_SoftShadowsSupported`, `m_SoftShadowQuality`, `m_AdditionalLightsRenderingMode`, `m_AdditionalLightsPerObjectLimit`
- SSAO `m_Settings` inner fields (`AOMethod`, `Intensity`, `Radius`, etc.)

These are accessed via `System.Reflection` with `BindingFlags.NonPublic | BindingFlags.Instance`.

For SSAO, a two-level reflection chain is used:
1. Get `m_Settings` field from the SSAO feature object
2. Get/set the target field from the `m_Settings` value object

#### 5. Editor/Build Dual Destruction

Managers that create runtime objects use a dual destruction pattern:

```csharp
if (Application.isEditor && !Application.isPlaying)
    DestroyImmediate(obj);
else
    Destroy(obj);
```

`DestroyImmediate` is required in Editor edit mode (not PlayMode) because `Destroy` is delayed and won't execute until the next frame, which never comes in edit mode.

#### 6. OnValidate + delayCall Pattern

For Inspector changes that must not execute during serialization:

```csharp
private void OnValidate()
{
    EditorApplication.delayCall -= SafeSyncFromInspector;
    EditorApplication.delayCall += SafeSyncFromInspector;
}
```

The `-=` before `+=` prevents duplicate registration. The `delayCall` ensures the code runs after Unity finishes serialization, avoiding "SendMessage cannot be called during Awake" errors.

#### 7. GI Environment Refresh Pattern

After changing the skybox or rendering mode, the environment lighting must be forced to refresh:

```csharp
RenderSettings.ambientMode = AmbientMode.Flat;
RenderSettings.ambientMode = AmbientMode.Skybox;
DynamicGI.UpdateEnvironment();
RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
```

The `ambientMode` and `defaultReflectionMode` toggles are NOT redundant — they trigger internal Unity callbacks that `DynamicGI.UpdateEnvironment()` alone cannot. See `knowledge/gi-environment-refresh.md` for details.

### Resource Loading Convention

All runtime assets use `Resources.Load<>()`:
- Textures: `Resources.Load<Texture2D>("Textures/[name]")`
- Cubemaps: `Resources.Load<Cubemap>("Textures/[name]")`
- Models: `Resources.Load<GameObject>("Models/[name]")`
- Prefabs: `Resources.Load<GameObject>("Prefabs/[name]")`
- Shaders: `Shader.Find("Shader/Name")` (built-in) or `Shader.Find("Hidden/Custom")` (custom)

**Important**: `Shader.Find()` only works for shaders that are included in the build. Hidden/internal shaders may be stripped — see `knowledge/shader-stripping-and-svc.md`.

### Shader Inclusion Strategy

The project uses a hybrid approach managed by `IncludeShaders.cs` (see `knowledge/shader-stripping-and-svc.md`):

1. **Always Included Shaders**: Skybox shaders + custom/hidden shaders (few variants, must not be stripped)
2. **ShaderVariantCollection**: URP Lit/SimpleLit/Unlit with only the specific keyword combinations used at runtime
3. **URP shaders removed from Always Included Shaders** to prevent variant explosion (managed via SVC instead)
