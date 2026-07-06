# Manager Scripts Detail

## UrpManager

**File**: `Assets/Scripts/UrpManager.cs` (567 lines)

**Role**: Central hub for runtime URP pipeline modification. Other managers access URP settings through this class. This is the most critical manager — incorrect pipeline configuration causes silent rendering failures on mobile platforms.

### Pipeline Acquisition

```csharp
AcquireActivePipeline():
  1. activeUrpa = QualitySettings.renderPipeline as UniversalRenderPipelineAsset
  2. Fallback: GraphicsSettings.renderPipelineAsset as UniversalRenderPipelineAsset
  3. Reflect m_RendererDataList + m_DefaultRendererIndex => activeUrd
```

**Priority**: `QualitySettings.renderPipeline` > `GraphicsSettings.renderPipelineAsset`

The URD is acquired via reflection because `UniversalRenderPipelineAsset` doesn't expose its renderer data list publicly:
```csharp
ScriptableRendererData[] renderers = (ScriptableRendererData[])listField.GetValue(activeUrpa);
int defaultIndex = (int)indexField.GetValue(activeUrpa);
activeUrd = renderers[defaultIndex] as UniversalRendererData;
```

### Exposed Set Methods

| Method | Target | Access | Called By |
|---|---|---|---|
| `SetUrpMaxAdditionalLightsCount(int)` | `activeUrpa.maxAdditionalLightsCount` | Public property | LightManager |
| `SetUrpMSAASampeCount(int)` | `activeUrpa.msaaSampleCount` | Public property | CameraManager |
| `SetUrpHDR(bool)` | `activeUrpa.supportsHDR` | Public property | CameraManager |
| `SetUrpRenderScale(float)` | `activeUrpa.renderScale` | Public property | VolumeManager |
| `SetUrpUpscalingFilter(UpscalingFilterSelection)` | `activeUrpa.upscalingFilter` | Public property | VolumeManager |
| `SetUrpSupportsSoftShadows(bool)` | `m_SoftShadowsSupported` | Reflection | LightManager |
| `SetUrpSoftShadowQuality(SoftShadowQuality)` | `m_SoftShadowQuality` | Reflection | LightManager |
| `SetUrpRenderingMode(RenderingMode)` | `activeUrd.renderingMode` | Public property | UrpManager (self) |
| `SetSSAOField(feature, fieldInfo, name, value)` | SSAO `m_Settings.[name]` | Reflection chain | VolumeManager |

### SSAO Access Pattern

SSAO is a `ScriptableRendererFeature` on the `UniversalRendererData`. Its settings are in a private field `m_Settings`:

```
GetSSAOFeature()  -> find feature by type name "ScreenSpaceAmbientOcclusion" in activeUrd.rendererFeatures
GetSSAOField()    -> reflect m_Settings field on the feature object
SetSSAOField()    -> reflect target field on m_Settings value object, handle enum/primitive conversion
```

`SetSSAOField` handles three value types:
- **Enum**: `Enum.ToObject(targetType, value)` then `field.SetValue(settingsObj, enumValue)`
- **Primitive** (int, float, bool): `Convert.ChangeType(value, targetType)` then `field.SetValue(settingsObj, convertedValue)`
- **Other**: Direct `field.SetValue(settingsObj, value)`

### Editor State Backup

All modified URPA/URD/SSAO properties are backed up in `Awake()` and restored in `OnDestroy()`:

**Direct properties** (backed up as individual fields):
- `maxAdditionalLightsCount`, `msaaSampleCount`, `supportsHDR`, `renderScale`, `upscalingFilter`
- `renderingMode` (on URD)

**Reflection properties** (backed up via reflection read):
- `m_SoftShadowsSupported`, `m_SoftShadowQuality`
- `m_AdditionalLightsRenderingMode`, `m_AdditionalLightsPerObjectLimit`

**SSAO settings** (backed up via reflection Dictionary):
- `Dictionary<string, object>` captures all fields of the SSAO `m_Settings` object
- This ensures future SSAO field additions are automatically covered

All backup/restore code is wrapped in `#if UNITY_EDITOR` and compiles to nothing in builds.

### GI Refresh

After changing rendering mode, `RefreshGI()` is called to force environment lighting update:

```csharp
public void RefreshGI()
{
    RenderSettings.ambientMode = AmbientMode.Flat;
    RenderSettings.ambientMode = AmbientMode.Skybox;
    DynamicGI.UpdateEnvironment();
    if (RenderSettings.customReflectionTexture == null)
    {
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
    }
}
```

See `knowledge/gi-environment-refresh.md` for why the toggles are necessary.

### Diagnostics

`LogAdditionalLightsDiagnostics()` provides a comprehensive dump of additional lights state — useful for debugging rendering issues on device. Prints:
- Pipeline asset info (name, maxAdditionalLightsCount, graphicsDeviceType)
- Reflection fields (additionalLightsRenderingMode, additionalLightsPerObjectLimit)
- Quality level info
- All lights in scene (type, enabled, intensity, range, position)
- All renderers in scene (shader, layer, receiveShadows)
- Shader keyword status (`_ADDITIONAL_LIGHTS`)

---

## QualityManager

**File**: `Assets/Scripts/QualityManager.cs` (64 lines)

**Role**: Ensures the correct quality level is set at startup, which determines which URP asset is bound to `QualitySettings.renderPipeline`.

### Initialization

Dual-trigger mechanism for OpenHarmony compatibility:

1. `[RuntimeInitializeOnLoadMethod(BeforeSceneLoad)]` — static `InitializeQuality()`
2. `Awake()` — fallback if `RuntimeInitializeOnLoadMethod` didn't fire (known issue on OHOS)

Both gated by `static bool initialized` to prevent double execution.

### Quality Level Selection

- On `UNITY_OPENHARMONY`, `UNITY_ANDROID`, `UNITY_IOS`, `UNITY_EDITOR`: sets "High Fidelity"
- Other platforms: uses default quality level

**Critical**: After `QualitySettings.SetQualityLevel()`, `QualitySettings.renderPipeline` is updated to the URP asset bound to that quality level. UrpManager depends on this having happened before its `Awake()`.

### Why "High Fidelity"?

The "Performant" quality level has `AdditionalLightsRenderingMode = Disabled`, which means no point/spot lights will render. "High Fidelity" has `PerPixel` mode with a limit of 4, which is sufficient for the demo's lighting needs. The `LightManager` dynamically increases the limit as more lights are added.

---

## VolumeManager

**File**: `Assets/Scripts/VolumeManager.cs` (872 lines)

**Role**: Runtime post-processing effects management via URP Volume system + SSAO renderer feature modification.

### Architecture

VolumeManager uses two different systems for different effects:
1. **Volume/VolumeProfile** (standard URP): Bloom, Chromatic Aberration, Depth of Field, Motion Blur, Tonemapping, Vignette, Screen Space Lens Flare
2. **ScriptableRendererFeature reflection** (custom): SSAO — because SSAO is configured as a Renderer Feature on the UniversalRendererData, not as a Volume component

### Post-Processing Effects

| Effect | Default | Notes |
|---|---|---|
| Bloom | Off | Threshold=0.9, Intensity=10 |
| Chromatic Aberration | Off | Intensity=1.0 |
| Depth of Field | Off | Gaussian mode |
| Motion Blur | Off | CameraAndObjects mode, Low quality. Runtime guard checks shader.isSupported |
| Tonemapping | Off | ACES mode. Default off to avoid dark scene on first load |
| Vignette | Off | Intensity=1.0, Smoothness=0.2 |
| Screen Space Lens Flare | Off | Intensity=10. Requires Bloom intensity > 0 to appear |

### SSAO

Managed via UrpManager's reflection-based SSAO access (not Volume system):

- 11 fields: AOMethod, Intensity, Radius, Falloff, DirectLightingStrength, Source, NormalSamples, Downsample, AfterOpaque, BlurQuality, Samples
- VolumeManager calls `urpMgr.SetSSAOField()` for each
- SSAO feature's `SetActive(enableSsao)` controls whether the feature runs

### Upscaling

- `renderScale` and `upscalingFilter` set via `urpMgr.SetUrpRenderScale()` / `SetUrpUpscalingFilter()`
- These modify the pipeline asset, not the Volume

### Motion Blur Runtime Guard

Before enabling Motion Blur, checks `Shader.Find("Hidden/Universal Render Pipeline/CameraMotionBlur").isSupported`. If not supported (e.g., on OHOS Vulkan), auto-disables with a warning.

### VolumeProfile Creation

The VolumeProfile is created at runtime:
```csharp
globalVolumeProfile = ScriptableObject.CreateInstance<VolumeProfile>();
globalVolume.profile = globalVolumeProfile;
```

Each effect is added via `globalVolumeProfile.Add<EffectType>(true)` if not already present.

---

## LightManager

**File**: `Assets/Scripts/LightManager.cs` (682 lines)

**Role**: Runtime creation and management of directional, point, and spot lights with circular arrangement.

### Light Creation

Lights are created as new GameObjects with `Light` component. After creation, `TransformLights()` arranges them in a circle around `gameObject.transform.position` at configurable `radius` and `height`:

```csharp
float angle = (360.0f / lights.Count) * i * Mathf.Deg2Rad;
float lightX = targetPos.x + radius * Mathf.Cos(angle);
float lightZ = targetPos.z + radius * Mathf.Sin(angle);
```

Each light is oriented to face the target: `Quaternion.LookRotation(targetPos - lightPos)`.

### Additional Lights Management

- `UpdateMaxAdditionalLights()`: counts non-directional lights, sets `urpMgr.SetUrpMaxAdditionalLightsCount(max(count, 8))`
- Minimum of 8 prevents constant re-allocation when adding the first few lights
- Safety guard: `if (UniversalRenderPipeline.asset == null) return;` prevents crash in OnDestroy
- Logs `_ADDITIONAL_LIGHTS` keyword status and `maxVisibleAdditionalLights` after adding lights

### Start Initialization

```csharp
urpMgr.SetUrpSupportsSoftShadows(false);
urpMgr.SetUrpSoftShadowQuality(SoftShadowQuality.Low);
```

Soft shadows are disabled by default for performance on mobile.

### OnDestroy

Simplified direct cleanup — just destroys light GameObjects without calling `UpdateMaxAdditionalLights()` (UrpManager may already be destroyed):

```csharp
for (int i = lights.Count - 1; i >= 0; i--)
{
    RemoveLight(i);
}
lights.Clear();
```

---

## CameraManager

**File**: `Assets/Scripts/CameraManager.cs` (437 lines)

**Role**: Runtime camera settings (Anti-Aliasing, MSAA, HDR, Dithering).

### Camera Access

- `mainCamera = Camera.main`
- `mainCameraData = GetComponent<UniversalAdditionalCameraData>()` (adds if missing)
- Enables `renderPostProcessing = true` — required for Volume effects to render

### AA / MSAA Interaction

- TAA and MSAA are **mutually exclusive** — if both are selected, the later one disables the earlier
- MSAA sample count set via `urpMgr.SetUrpMSAASampeCount()` (pipeline-level, affects all cameras)
- TAA quality and contrast-adaptive sharpening set on `mainCameraData.taaSettings`

### Anti-Aliasing Options

| Mode | Property Set | Level |
|---|---|---|
| None | `mainCameraData.antialiasing = AntialiasingMode.None` | — |
| FXAA | `mainCameraData.antialiasing = AntialiasingMode.FastApproximateAntialiasing` | — |
| SMAA | `mainCameraData.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing` | Low/Medium/High |
| TAA | `mainCameraData.antialiasing = AntialiasingMode.TemporalAntiAliasing` | VeryLow..VeryHigh |

---

## SkyboxManager

**File**: `Assets/Scripts/SkyboxManager.cs` (860 lines)

**Role**: Runtime skybox material creation and application for 5 skybox types with 3 quality levels each.

### Supported Skybox Types

| Type | Shader | Textures | Key Properties |
|---|---|---|---|
| Procedural | `Skybox/Procedural` | None (procedural) | SunDisk, SunSize, AtmosphereThickness, Exposure |
| Cubemap | `Skybox/Cubemap` | 1 Cubemap | Tint, Exposure, Rotation |
| 6 Sided | `Skybox/6 Sided` | 6 Texture2D | Tint, Exposure, Rotation |
| Panoramic | `Skybox/Panoramic` | 1 Texture2D | Tint, Exposure, Rotation, Mapping, ImageType, 3DLayout |
| Mobile | `Mobile/Skybox` | 6 Texture2D | Tiling/Offset per face |

### Quality Levels

3 quality levels with pre-loaded texture lists for each type:
- Low (1k = 1024px)
- Medium (2k = 2048px)
- High (4k = 4096px)

All textures are loaded in `Start()` via `Resources.Load<>()` into `List<Texture2D>` / `List<Cubemap>` indexed by quality level.

### Shader References

Shaders are stored as public `Shader` fields for two purposes:
1. **Serialization**: Ensures the shader is included in the build (referenced by the scene)
2. **Runtime**: Falls back to `Shader.Find()` if the Inspector reference is null

```csharp
if (proceduralShader == null) proceduralShader = Shader.Find("Skybox/Procedural");
```

### Skybox Application

`ApplySkyboxToScene()` sets `RenderSettings.skybox` and forces GI refresh:
1. Toggle `ambientMode` Flat→Skybox (forces ambient color recalculation)
2. `DynamicGI.UpdateEnvironment()` (updates GI system)
3. Toggle `defaultReflectionMode` Custom→Skybox (regenerates default reflection cubemap — fixes black specular)

### Panoramic Rotation Offset

Panoramic skybox has a 90° rotation offset (`panoramicRotationOffset = 90.0f`) to align with the cubemap/6-sided skybox orientations:
```csharp
skybox.SetFloat("_Rotation", (panoramicRotation + panoramicRotationOffset) % 360);
```

---

## ModelImporter

**File**: `Assets/Scripts/ModelImporter.cs` (276 lines)

**Role**: Runtime model loading with quality variants.

### Model Variants

| Quality | Resource | Description |
|---|---|---|
| Low | `Models/Suzanne_5w` | 5万 (50k) polygons |
| Normal | `Models/Suzanne_20w` | 20万 (200k) polygons |
| High | `Models/Suzanne_50w` | 50万 (500k) polygons |
| Ultra | `Models/Suzanne_100w` | 100万 (1M) polygons |

### Renderer Access

`GetRenderer()` provides the spawned model's Renderer for MaterialManager:
```csharp
public Renderer GetRenderer()
{
    if (_renderer == null && spawnedModel != null)
        _renderer = spawnedModel.GetComponent<Renderer>();
    return _renderer;
}
```

### GI Flag Setting

After loading, the renderer's material is set to `RealtimeEmissive` and toggled to force a refresh:
```csharp
_renderer.material.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
_renderer.enabled = false;
_renderer.enabled = true;
DynamicGI.UpdateEnvironment();
```

---

## MaterialManager

**File**: `Assets/Scripts/MaterialManager.cs` (429 lines)

**Role**: Runtime material creation with URP shader variants and surface type configuration.

### Shader Modes

- Lit (Metallic/Specular workflow)
- Unlit
- Simple Lit

### Surface Types

- **Opaque**: `SrcBlend=One, DstBlend=Zero, ZWrite=1, Queue=Geometry`
  - Disables `_SURFACE_TYPE_TRANSPARENT`, `_ALPHAPREMULTIPLY_ON`
- **Transparent (Premultiplied Alpha)**: `SrcBlend=One, DstBlend=OneMinusSrcAlpha, ZWrite=0, Queue=Transparent`
  - Enables `_SURFACE_TYPE_TRANSPARENT`, `_ALPHAPREMULTIPLY_ON`
  - Base color alpha set to 0.6 by default when transparent is selected

### Material Application

- Apply: `renderer.material = runtimeMaterial` (creates implicit instance per renderer)
- Remove: `renderer.sharedMaterial = originalMaterial` (restores the original shared material)
- `originalMaterial` is captured via `renderer.sharedMaterial` **before** the first `renderer.material` access

---

## TextureManager

**File**: `Assets/Scripts/TextureManager.cs` (334 lines)

**Role**: Texture loading, Texture2DArray creation, and billboard display.

### Texture2DArray

Multiple textures loaded into a GPU texture array for single draw call rendering:

```csharp
Texture2DArray(width, height, count, format, false)
Graphics.CopyTexture(src2D, 0, 0, texArray, sliceIndex, 0)
```

### Billboard

- Uses custom shader `Hidden/TextureArrayGrid` for grid display
- Mesh: manually created quad (avoids `CreatePrimitive` which adds MeshCollider — see `cases/meshcollider-build-error.md`)
- Size: calculated from FOV and screen aspect to fit visible area while preserving grid proportions (see `cases/billboard-proportions.md`)
- Orientation: always faces camera (`transform.LookAt(camera)` + 180° flip in `Update()`)
- `billboardScreenRatio` (0.1–1.0, default 1.0) controls how much of the visible screen the billboard fills

### Cleanup

On destroy, the billboard, material, and Texture2DArray are all properly destroyed using the Editor/Build dual destruction pattern.

---

## TransparentManager

**File**: `Assets/Scripts/TransparentManager.cs` (236 lines)

**Role**: Creates transparent planes for alpha blending testing at configurable distances.

### Plane Creation

- Manual quad mesh (same `CreateQuadMesh()` pattern as TextureManager)
- URP/Lit shader with `_SURFACE_TYPE_TRANSPARENT` enabled
- Premultiplied alpha blending: `SrcBlend=SrcAlpha, DstBlend=OneMinusSrcAlpha`
- Planes arranged along camera forward at increasing distances: `startDistance + i * adaptiveSpacing`
- Size adapts to camera FOV: `Mathf.Min(visibleHeight, visibleWidth) * planeScreenRatio`
- Spacing adapts to plane size: `adaptiveSpacing = adaptiveSize * 1.2f`
- Each plane gets a unique HSV-based color with configurable alpha

---

## UIBuilder

**File**: `Assets/Scripts/UIBuilder.cs` (580 lines)

**Role**: Programmatic UI construction from prefabs loaded via `Resources.Load`.

### Supported UI Elements

Canvas, Panel, Button, Text (TMP), Dropdown (TMP), ScrollView, Slider, Toggle, Separator, EventSystem

### Mobile UI Scaling

- `CanvasScaler.ScaleWithScreenSize` with `referenceResolution = Screen.size / 3.0`
- `matchWidthOrHeight = 0.5`
- All elements use `LayoutElement.preferredHeight = 10` (no per-element UI_SCALE)
- See `knowledge/mobile-ui-scaling.md` for the full design rationale

### Dropdown Fix

- Template must be `SetActive(false)` to avoid interfering with `VerticalLayoutGroup`
- `GetComponentInChildren<TextMeshProUGUI>(true)` to search inactive children
- See `cases/dropdown-layout-error.md` for details

### ScrollView Configuration

```csharp
layoutGroup.spacing = 4;
layoutGroup.padding = new RectOffset(8, 8, 8, 8);
layoutGroup.childControlWidth = true;
layoutGroup.childControlHeight = false;
layoutGroup.childForceExpandWidth = true;
layoutGroup.childForceExpandHeight = false;

sizeFitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
sizeFitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
```

---

## CameraController

**File**: `Assets/Scripts/CameraController.cs` (180 lines)

**Role**: Orbital camera with Move/Rotate modes.

### Input Handling

- **Desktop**: Right-click drag to orbit (Rotate mode) or pan (Move mode)
- **Mobile**: Single-finger drag to orbit/pan, two-finger pinch to zoom
- **UI penetration guard**: `EventSystem.current.IsPointerOverGameObject()` prevents camera control when touching UI elements
  - Desktop: `IsPointerOverGameObject()` (no parameter)
  - Mobile: `IsPointerOverGameObject(Input.GetTouch(0).fingerId)` (with finger ID)

### Camera Modes

| Mode | Right-Click Drag / Single Finger | Two Fingers |
|---|---|---|
| Rotate | Orbit around target | Pinch zoom |
| Move | Pan target offset | Pinch zoom |

---

## IncludeShaders (Editor)

**File**: `Assets/Editor/IncludeShaders.cs` (232 lines)

**Role**: Pre-build shader inclusion management via `IPreprocessBuildWithReport`. Implements the project's hybrid shader preservation strategy.

### Strategy

1. **Always Included Shaders**: Skybox shaders + `Hidden/TextureArrayGrid` + `CameraMotionBlur`
2. **ShaderVariantCollection**: URP Lit/SimpleLit/Unlit with specific keyword combinations
3. **Remove URP shaders from Always Included Shaders** (managed via SVC to avoid variant explosion)

### SVC Variants

```
Lit:     SRP, SRP+_ADDITIONAL_LIGHTS, SRP+_ADDITIONAL_LIGHTS+_SURFACE_TYPE_TRANSPARENT,
         SRP+_SURFACE_TYPE_TRANSPARENT, SRP+_SURFACE_TYPE_TRANSPARENT+_ALPHAPREMULTIPLY_ON,
         ShadowCaster
SimpleLit: SRP, SRP+_ADDITIONAL_LIGHTS, SRP+_ADDITIONAL_LIGHTS+_SURFACE_TYPE_TRANSPARENT,
           SRP+_SURFACE_TYPE_TRANSPARENT, ShadowCaster
Unlit:   SRP
```

Note: Unlit has no `_ADDITIONAL_LIGHTS` variant because Unlit materials are not affected by lighting.

### Build-Time Logging

`EnsureShaderVariantCollection()` logs all included variants to the build console, making it easy to verify the SVC contents.

See `knowledge/shader-stripping-and-svc.md` for the full strategy explanation.
