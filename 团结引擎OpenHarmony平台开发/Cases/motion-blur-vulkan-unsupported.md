# Case: CameraMotionBlur Shader Unsupported on OHOS Vulkan

## Problem

Enabling Motion Blur on OpenHarmony had no visual effect, despite the effect being marked as active in the Volume.

## Error Log

No error by default. After adding explicit shader checks:

```
[VolumeManager] MotionBlur shader check: shader=Hidden/Universal Render Pipeline/CameraMotionBlur, isSupported=False, graphicsDeviceType=Vulkan
```

## Diagnosis Process

1. Enabled Motion Blur in VolumeManager — no visual effect on OHOS
2. Added `Shader.Find("Hidden/Universal Render Pipeline/CameraMotionBlur")` check
3. Shader was found but `isSupported` was `false`
4. Checked `SystemInfo.graphicsDeviceType` = `Vulkan` on OHOS
5. Examined `CameraMotionBlur.shader` source code
6. Found `#pragma exclude_renderers gles` on line 4

## Root Cause

The `CameraMotionBlur.shader` contains `#pragma exclude_renderers gles`, which excludes GLES 2.0. This should not affect Vulkan. However, on OHOS:

1. The Graphics API configuration is `m_APIs: 150000000b000000` = OpenGLES3 (primary) + Vulkan (fallback)
2. At runtime, `SystemInfo.graphicsDeviceType = Vulkan`, meaning the device is running on the Vulkan fallback
3. The `isSupported = false` on Vulkan suggests either:
   - The shader's Vulkan variant was stripped during build (shader stripping removed it because no scene usage reference existed)
   - The shader compilation for Vulkan failed on Tuanjie's shader compiler

The most likely cause is **shader stripping**: since `CameraMotionBlur` is a hidden/internal shader not referenced by any material in the scene, the build pipeline may have stripped its Vulkan variant or the entire shader.

## Fix

Two-part fix:

1. **IncludeShaders.cs**: Added `CameraMotionBlur` to `AlwaysIncludedShaderNames` to prevent stripping:
   ```csharp
   private static readonly string[] AlwaysIncludedShaderNames = new string[]
   {
       "Hidden/TextureArrayGrid",
       "Hidden/Universal Render Pipeline/CameraMotionBlur"
   };
   ```

2. **VolumeManager**: Added runtime guard — check `shader.isSupported` before enabling Motion Blur, auto-disable if unsupported:
   ```csharp
   if (enableMotionBlur)
   {
       Shader motionBlurShader = Shader.Find("Hidden/Universal Render Pipeline/CameraMotionBlur");
       if (motionBlurShader == null || !motionBlurShader.isSupported)
       {
           enableMotionBlur = false;
       }
   }
   ```

3. **MotionBlurMode**: Changed default from `CameraOnly` to `CameraAndObjects` — URP only generates motion vector textures when mode is `CameraAndObjects` (see `UniversalRenderer.cs:1863`).

## Lesson

**Hidden/internal URP shaders can be stripped in builds if not explicitly referenced.** Always add them to "Always Included Shaders" or ShaderVariantCollection. Additionally, `shader.isSupported` is the definitive runtime check — don't assume a shader works just because `Shader.Find()` returns non-null.
