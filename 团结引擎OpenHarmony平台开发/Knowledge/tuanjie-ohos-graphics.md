# Tuanjie OpenHarmony Graphics API Behavior

## OHOS Graphics API Configuration

In Tuanjie 2022.3.62t2, the OpenHarmony PlayerSettings graphics API configuration uses:

```
m_APIs: 150000000b000000
```

Decoding the hex values:
- `0x15 = 21` = OpenGLES3 (primary)
- `0x0B = 11` = Vulkan (fallback)

The order matters: Unity tries the primary API first, then falls back to the secondary if the primary fails.

## Runtime Graphics Device

Despite OpenGLES3 being configured as primary, the actual runtime device on OHOS test devices reports:

```
SystemInfo.graphicsDeviceType = Vulkan
```

This means:
1. The device attempted OpenGLES3 first
2. OpenGLES3 was unavailable or failed initialization
3. Unity fell back to Vulkan
4. All rendering uses the Vulkan code path

## Implications for URP Effects

### Motion Blur

`CameraMotionBlur.shader` contains `#pragma exclude_renderers gles` (line 4). This excludes GLES 2.0 only — it should NOT exclude Vulkan. However:

- `Shader.Find("Hidden/Universal Render Pipeline/CameraMotionBlur")` returns non-null
- `shader.isSupported` returns `false` on OHOS Vulkan

Possible causes:
1. **Shader stripping**: The Vulkan variant was stripped during build because no material references it
2. **Compilation failure**: Tuanjie's shader compiler failed to compile the Vulkan variant
3. **Runtime incompatibility**: The shader uses features not available in the OHOS Vulkan implementation

Our fix: Added `CameraMotionBlur` to Always Included Shaders (anti-stripping) + runtime `isSupported` guard.

### Additional Lights

Additional lights (point/spot) work correctly on OHOS Vulkan when:
- `AdditionalLightsRenderingMode = PerPixel` (not Disabled)
- `maxAdditionalLightsCount` is set appropriately
- The URPA is the original bound to QualitySettings (not a cloned instance)

They fail when the URPA is cloned via `Instantiate()` because the clone's internal state is inconsistent on the Vulkan code path.

### SSAO

SSAO works correctly on OHOS Vulkan. Its shader is included via the Renderer Feature reference (not stripped).

## Graphics API Debugging Commands

```csharp
// Check which graphics API is active
Debug.Log(SystemInfo.graphicsDeviceType);           // Vulkan
Debug.Log(SystemInfo.graphicsDeviceName);            // Device-specific GPU name
Debug.Log(SystemInfo.graphicsDeviceVersion);         // Vulkan API version

// Check shader support
Shader s = Shader.Find("Path/To/Shader");
Debug.Log(s?.isSupported);                           // true/false

// Check rendering capabilities
Debug.Log(SystemInfo.supportsComputeShaders);
Debug.Log(SystemInfo.supportsAsyncGPUReadback);
```

## Key Takeaways

1. **Don't assume the primary Graphics API is the one actually used** — always check `SystemInfo.graphicsDeviceType` at runtime
2. **Shader `isSupported` is the definitive check** — `Shader.Find()` returning non-null doesn't mean the shader works on the current platform
3. **Vulkan on OHOS may have quirks** — some shaders/features that work on desktop Vulkan may not work on OHOS Vulkan due to driver/implementation differences
4. **Always test on actual hardware** — Graphics API behavior can differ between the Editor, stock Android, and OHOS even when using the same API
