# Shader Variant Collection in Tuanjie Engine

In the Unity/Tuanjie rendering pipeline, **Shader Variant Collection (SVC)** is more than just a checklist—it's a lifesaver for performance on mobile platforms, especially **OpenHarmony (Vulkan)**. Here is a detailed breakdown of the concepts and workflows.

## Shader Variant
GPUs hate logical branching (like `if-else`) during rendering. To maximize throughput, the compiler generates multiple hard-coded "clones" of a shader for every combination of enabled features (Keywords).
-   **Variant Explosion (Permutation)**:
    If your shader defines:
    -   `#pragma multi_compile _ FOG_ON` (2 states)
    -   `#pragma multi_compile _ LIGHTMAP_ON` (2 states)
    -   `#pragma multi_compile _ HIGH_QUALITY` (2 states)
    
    The total number of variants is $2 \times 2 \times 2 = 8$. A complex shader with 10 toggles results in $2^{10} = 1024$ variants. This explains why shader compilation can take hours for large projects.
    
### `multi_compile` & `shader_feature`
In the Unity/Tuanjie engine shader development, `multi_compile` and `shader_feature` are the two core directives used to define **Shader Variants**. Think of them as "preprocessor macros" that determine which combinations of shader code will be compiled into your final application bundle.

Understanding the difference is critical for managing build size and avoiding the dreaded "pink shader" error on mobile platforms like **OpenHarmony**.


#### 1. `multi_compile`: The All-Rounder (Never Lost)
`multi_compile` generates **every possible** combination of keyword versions during the build process.
-   **Behavior**: Unity compiles all variants regardless of whether they are actually used by any material in your scene.
-   **Best For**: **Global** or **frequently toggled** states. Examples:
    -   Lighting modes (Dynamic shadows, point light counts).
    -   Fog (Fog On/Off).
    -   Global post-processing toggles.
-   **Pros**: Extremely safe for runtime switching via scripts (`Shader.EnableKeyword`). You never have to worry about a "missing variant."
-   **Cons**: Causes **"Variant Explosion."** If you define 5 sets of `multi_compile` with 2 options each, it generates $2^5 = 32$ variants, significantly increasing build size and memory usage.
- 
#### 2. `shader_feature`: The Lean Expert (On-Demand)
`shader_feature` is a "stripped-down" version of `multi_compile`.
-   **Behavior**: During the build, Unity checks your project to see if **any material** actually uses a specific keyword. If no material uses it, that variant is **Stripped** (excluded from the build).
-   **Best For**: **Material-level** settings that rarely change. Examples:
    -   Normal Map toggles.   
    -   Emission toggles. 
    -   Specific texture blending modes.
-   **Pros**: Greatly reduces shader size by only including what is strictly necessary.
-   **Cons**: **High runtime risk.** If no material uses "Normal Mapping" at build time, but you try to enable it via script at runtime, the variant won't exist. The object will turn **bright pink** (the Error Shader).
    
#### 3. Comparison Table
| Feature | `multi_compile` | `shader_feature` | 
|---------|-----------------|------------------| 
| **Build Behavior** | Includes **all** defined combinations | Includes only variants **used by materials** | 
| **Keyword Scope** | Usually Global Keywords | Usually Local Keywords | 
| **Runtime Switching** | Safe to toggle via script anytime | Script toggling may fail if stripped | 
| **Build Size Impact** | High (lots of variants) | Low (on-demand only) | 
| **Typical Examples** | `DIRECTIONAL`, `SHADOWS_SCREEN`, `FOG_EXP` | `_NORMALMAP`, `_ALPHATEST_ON`|

#### 4. Best Practices for OpenHarmony (Vulkan) Development
Since you are optimizing for OpenHarmony, keep these points in mind for your **Shader Variant Collection (SVC)**:
1.  **The Dynamic Switching Trap**: If your Skybox Manager toggles effects (e.g., "High Quality Sun" vs "No Sun") using `shader_feature`, and your initial material doesn't have the sun enabled, the build won't include the "Sun" variant. It will fail on the device.
2.  **Forced Inclusion**: If you must use `shader_feature` to keep the build size small but still need to toggle it via script, you **must** manually add those keyword combinations to your **Shader Variant Collection**. This tells the engine: "I'll need this later, don't strip it!" 
3.  **Vulkan Strictness**: The Vulkan drivers on OpenHarmony are very strict. If a variant is stripped via `shader_feature` and you try to force it active, Vulkan might throw a driver-level error or cause the rendering process to hang.

#### 5. Code Example
OpenGL Shading Language
```GLSL
// Build generates: None and FOG_ON (both versions included regardless)
#pragma multi_compile _ FOG_ON 

// Build generates: NORMAL_ON ONLY if a material has it checked in the Inspector
#pragma shader_feature _ NORMAL_ON 
```

## Shader Variant Collection
### Why do we need SVC?
#### **A. Avoiding the "Pink Screen of Death" (Stripping)**
Unity optimizes the build by "stripping" variants that aren't used by any **static material asset** in the scene.
-   **The Trap**: Effects controlled purely via script (e.g., `material.EnableKeyword("LOW_HEALTH_GLOW")`).
-   **Result**: At runtime, if you enable a keyword that was stripped during the build, the GPU has no machine code to run, resulting in a pink "Error Shader." SVC forces Unity to keep these dynamic variants in the build.

#### **B. Eliminating "First-Sight Stutter" (Runtime Compilation)**
On OpenHarmony (Vulkan), the shader binary (SPIR-V) often requires a final link/compile pass by the driver before the first frame is rendered.
-   **The Hitch**: Without pre-warming, the main thread will hang for hundreds of milliseconds while the GPU compiles the shader during a heavy action or skybox swap.
-   **Result**: The player experiences a noticeable frame drop or "hitch."

### 3. Workflow: Efficient SVC Collection
#### **Practical: Auto-Capture Process (The Pro Method)**
1.  **Clear Cache**: Run the game in the Unity Editor.
2.  **Playthrough**: Play through the game manually, ensuring all effects, skybox swaps, and lighting conditions are triggered.  
3.  **Capture**: 
    -   Go to `Edit > Project Settings > Graphics`.
    -   Locate `Shader Loading` at the bottom.
    -   Click `Save to asset`. This exports all variants currently resident in memory to an SVC file.

#### **Code: The WarmUp Logic**
It is recommended to run this during a loading screen. Note that `WarmUp` is a synchronous, heavy operation.
```csharp
using UnityEngine;

public class ShaderPreloader : MonoBehaviour
{
    public ShaderVariantCollection globalSVC;

    void Awake()
    {
        if (globalSVC != null && !globalSVC.isWarmedUp)
        {
            double startTime = Time.realtimeSinceStartupAsDouble;
            // Pre-compiles all variants in the collection and uploads to GPU
            globalSVC.WarmUp();
            Debug.Log($"Shader Pre-warm complete in {Time.realtimeSinceStartupAsDouble - startTime}s");
        }
    }
}
```

#### Expert "Rules of Thumb"
| Dimension | Insight | 
|-----------|---------| 
| **Memory vs. Startup** | Bigger is not always better. A massive SVC consumes VRAM and can significantly slow down app startup. Split SVCs by module (e.g., UI, Environment, VFX). | 
| **Keyword Scopes** | `Shader.EnableKeyword` (Global) vs. `material.EnableKeyword` (Local). SVC's auto-capture is sometimes inconsistent with local keywords; manual verification is advised. | 
| **Vulkan Specifics** | On Vulkan, even with SVC, if Pipeline State (like Blend Mode or Z-Test) changes, a recompile might still be triggered. |
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTExNDAyNjI5MTAsLTE4ODYzNDM5MDIsLT
EwOTEzMDAxMTZdfQ==
-->