# Texture2DArray: GPU-Native Alternative to Texture Atlas

## The Problem

When displaying multiple textures on a single surface (e.g., a billboard showing a grid of loaded textures), you need a way to efficiently sample different textures in a single draw call. Traditional approaches have significant limitations.

## Traditional Approach: Texture Atlas

A texture atlas combines multiple textures into a single large texture:

```
+-------+-------+
| Tex 0 | Tex 1 |
+-------+-------+
| Tex 2 | Tex 3 |
+-------+-------+
```

**Limitations**:
- All textures must have the **same resolution** (wasted space if they differ)
- **Mipmap bleeding**: At lower mip levels, adjacent textures bleed into each other at the seams
- Requires manual UV coordinate calculation (offset + tiling per texture)
- Adding/removing textures requires rebuilding the entire atlas
- Memory fragmentation: the atlas texture is always the size of the largest configuration

## Modern Approach: Texture2DArray

A `Texture2DArray` is a GPU-native texture type that stores multiple textures as array slices:

```
Slice 0: [full resolution texture]
Slice 1: [full resolution texture]
Slice 2: [full resolution texture]
...
```

Each slice is a full 2D texture with its own complete set of mipmaps. The GPU samples a specific slice using an additional coordinate.

### Advantages

1. **No mipmap bleeding**: Each slice has its own independent mip chain
2. **Native GPU support**: Single texture object, single sampler, single draw call
3. **Simple UV mapping**: Standard 0-1 UV range per slice, no offset/tiling calculation
4. **Dynamic creation**: Slices can be added/updated individually via `Graphics.CopyTexture()`
5. **No wasted space**: Each slice uses exactly the texture's own resolution

### Limitations

- All textures must have the **same resolution and format** (same constraint as atlas)
- Not supported on very old GPU hardware (OpenGL ES 2.0 / WebGL 1.0)
- Maximum array size depends on GPU (typically 2048 slices)

## Implementation in This Project

### Texture2DArray Creation

```csharp
private Texture2DArray CreateTextureArray()
{
    int width = loadedTextures[0].width;
    int height = loadedTextures[0].height;
    int count = loadedTextures.Count;

    Texture2DArray texArray = new Texture2DArray(
        width, height, count,
        loadedTextures[0].format,
        false  // mipChain — not needed for billboard display
    );

    for (int i = 0; i < count; i++)
    {
        // Copy source Texture2D (element 0, mip 0) to array slice i
        Graphics.CopyTexture(loadedTextures[i], 0, 0, texArray, i, 0);
    }

    return texArray;
}
```

**Key API**: `Graphics.CopyTexture(source, srcElement, srcMip, dest, destElement, destMip)`
- `srcElement = 0` for a Texture2D (no array slices)
- `destElement = i` for the target array slice index
- Both mip levels are 0 (base level)

### Custom Shader (TextureArrayGrid.shader)

The shader samples the texture array using the `_MainTex` uniform (typed as `sampler2DArray` in HLSL):

```hlsl
TEXTURE2D_ARRAY(_MainTex);
SAMPLER(sampler_MainTex);

// In fragment shader:
float2 uv = input.uv;
// Map UV to grid cell:
float2 cellUv = fmod(uv * float2(_GridCols, _GridRows), 1.0);
int sliceIndex = floor(uv.y * _GridRows) * _GridCols + floor(uv.x * _GridCols);
if (sliceIndex >= _TotalTextures) discard;
float4 color = SAMPLE_TEXTURE2D_ARRAY(_MainTex, sampler_MainTex, cellUv, sliceIndex);
```

The shader divides the quad into a grid (e.g., 3×2 for 6 textures) and maps each grid cell to a texture array slice.

### Material Setup

```csharp
billboardMaterial = new Material(Shader.Find("Hidden/TextureArrayGrid"));
billboardMaterial.SetTexture("_MainTex", textureArray);
billboardMaterial.SetFloat("_GridCols", cols);
billboardMaterial.SetFloat("_GridRows", rows);
billboardMaterial.SetFloat("_TotalTextures", loadedTextures.Count);
```

## Performance

- **Single draw call** for all textures (the entire billboard is one mesh + one material)
- **No CPU-side texture compositing** (unlike atlas approaches that require `Texture2D.ReadPixels()`)
- **GPU-native**: `CopyTexture` operates entirely on the GPU side (no readback to CPU)
- The texture array is destroyed in `OnDestroy()` to prevent memory leaks
