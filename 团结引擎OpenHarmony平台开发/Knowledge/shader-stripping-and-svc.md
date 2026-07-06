# Shader Stripping and ShaderVariantCollection in Tuanjie/URP

## The Shader Stripping Problem

Unity's IL2CPP build pipeline performs **shader variant stripping** — it removes shader variants (combinations of shader passes + keywords) that it determines are unused. This reduces build size and load time but can cause runtime failures if a needed variant is stripped.

### How Unity Determines "Used" Variants

Unity considers a variant "used" if:

1. A material in the build references the shader AND has the corresponding keywords enabled
2. The shader is in "Always Included Shaders" list (Graphics Settings)
3. The shader variant is in a `ShaderVariantCollection` that's in "Preloaded Assets"

Any variant NOT matched by these rules may be stripped.

### The Problem with Always Included Shaders

Adding a shader to "Always Included Shaders" includes **ALL** its variants. For URP shaders like `Universal Render Pipeline/Lit`, this can be hundreds of variants:

```
Lit shader variants = PassTypes × KeywordCombinations
  = (SRP, ShadowCaster, DepthOnly, DepthNormals, Meta, ...) × (_ADDITIONAL_LIGHTS, _SURFACE_TYPE_TRANSPARENT, _ALPHAPREMULTIPLY_ON, _MAIN_LIGHT_SHADOWS, _SHADOWS_SOFT, ...)
```

This leads to **variant explosion** — the build includes far more variants than needed, increasing:
- Build time
- Build size
- Runtime shader compilation time (stuttering on first use)
- Memory usage

## ShaderVariantCollection (SVC) Approach

A `ShaderVariantCollection` lets you specify **exactly which variants** you need:

```csharp
var variant = new ShaderVariantCollection.ShaderVariant(shader, passType, keywords);
```

### How SVC Works

1. Create an SVC asset listing specific shader + pass + keyword combinations
2. Add the SVC to PlayerSettings > Preloaded Assets
3. At build time, Unity includes these specific variants
4. At runtime, these variants are pre-compiled and loaded, avoiding runtime compilation stutter

### SVC vs Always Included Shaders

| Aspect | Always Included Shaders | ShaderVariantCollection |
|---|---|---|
| Granularity | All variants of a shader | Specific variants |
| Build size | Large (hundreds of variants) | Small (only needed variants) |
| Runtime stutter | May still stutter on uncompiled variants | Pre-compiled, no stutter |
| Setup complexity | Simple (drag shader into list) | Complex (must enumerate variants) |

## Our Approach (IncludeShaders.cs)

We use a **hybrid** approach:

1. **Always Included Shaders**: Only for shaders that don't have variant issues:
   - Skybox shaders (simple, few variants)
   - Custom shaders (`Hidden/TextureArrayGrid`)
   - Hidden URP shaders that might be stripped (`CameraMotionBlur`)

2. **ShaderVariantCollection**: For URP shaders with complex variant requirements:
   - Only the specific pass types + keyword combinations used by MaterialManager and TransparentManager
   - URP Lit/SimpleLit/Unlit with specific combinations like `_ADDITIONAL_LIGHTS`, `_SURFACE_TYPE_TRANSPARENT`, `_ALPHAPREMULTIPLY_ON`

3. **Remove URP shaders from Always Included Shaders**: Since they're managed via SVC, having them in both would include all variants anyway, defeating the purpose.

## Tuanjie-Specific Notes

### PassType.ScriptableRenderPipeline

URP uses `PassType.ScriptableRenderPipeline` (not `PassType.Normal`). Using the wrong pass type causes `ArgumentException` when creating `ShaderVariant`.

### ShaderVariantCollection Not Inheriting ScriptableObject

In Tuanjie, `ShaderVariantCollection` does not inherit from `ScriptableObject` in the normal way — you must use `new ShaderVariantCollection()` instead of `ScriptableObject.CreateInstance<ShaderVariantCollection>()` when creating programmatically.

### Missing Variants

Tuanjie's URP build may strip certain variants that stock Unity includes:
- `Lit ShadowCaster + _SURFACE_TYPE_TRANSPARENT`
- `Unlit SRP + _SURFACE_TYPE_TRANSPARENT`
- `Unlit ShadowCaster`
- `SimpleLit SRP + _SURFACE_TYPE_TRANSPARENT`

These must be explicitly added to the SVC. The `AddVariantSafe()` method catches `ArgumentException` for variants that don't exist in the shader.

## Debugging Shader Stripping Issues

1. **Build log**: Check the build output for shader compilation warnings
2. **`Shader.Find()` at runtime**: Returns null if the shader was completely stripped
3. **`shader.isSupported`**: Returns false if the shader exists but the current platform variant was stripped
4. **Frame Debugger**: Check if expected render passes are executing
5. **IncludeShaders.cs logging**: Prints all SVC variants at build time for verification
