# Shader Variant Collection in Tuanjie Engine


## `multi_compile` & `shader_feature`
In the Unity/Tuanjie engine shader development, `multi_compile` and `shader_feature` are the two core directives used to define **Shader Variants**. Think of them as "preprocessor macros" that determine which combinations of shader code will be compiled into your final application bundle.

Understanding the difference is critical for managing build size and avoiding the dreaded "pink shader" error on mobile platforms like **OpenHarmony**.

----------

## 1. `multi_compile`: The All-Rounder (Never Lost)

`multi_compile` generates **every possible** combination of keyword versions during the build process.

-   **Behavior**: Unity compiles all variants regardless of whether they are actually used by any material in your scene.
    
-   **Best For**: **Global** or **frequently toggled** states. Examples:
    
    -   Lighting modes (Dynamic shadows, point light counts).
        
    -   Fog (Fog On/Off).
        
    -   Global post-processing toggles.
        
-   **Pros**: Extremely safe for runtime switching via scripts (`Shader.EnableKeyword`). You never have to worry about a "missing variant."
    
-   **Cons**: Causes **"Variant Explosion."** If you define 5 sets of `multi_compile` with 2 options each, it generates $2^5 = 32$ variants, significantly increasing build size and memory usage.
    

----------

## 2. `shader_feature`: The Lean Expert (On-Demand)

`shader_feature` is a "stripped-down" version of `multi_compile`.

-   **Behavior**: During the build, Unity checks your project to see if **any material** actually uses a specific keyword. If no material uses it, that variant is **Stripped** (excluded from the build).
    
-   **Best For**: **Material-level** settings that rarely change. Examples:
    
    -   Normal Map toggles.
        
    -   Emission toggles.
        
    -   Specific texture blending modes.
        
-   **Pros**: Greatly reduces shader size by only including what is strictly necessary.
    
-   **Cons**: **High runtime risk.** If no material uses "Normal Mapping" at build time, but you try to enable it via script at runtime, the variant won't exist. The object will turn **bright pink** (the Error Shader).
    

----------

## 3. Comparison Table

**Feature**

**multi_compile**

**shader_feature**

**Build Behavior**

Includes **all** defined combinations

Includes only variants **used by materials**

**Keyword Scope**

Usually Global Keywords

Usually Local Keywords

**Runtime Switching**

Safe to toggle via script anytime

Script toggling may fail if stripped

**Build Size Impact**

High (lots of variants)

Low (on-demand only)

**Typical Examples**

`DIRECTIONAL`, `SHADOWS_SCREEN`, `FOG_EXP`

`_NORMALMAP`, `_ALPHATEST_ON`

----------

## 4. Best Practices for OpenHarmony (Vulkan) Development

Since you are optimizing for OpenHarmony, keep these points in mind for your **Shader Variant Collection (SVC)**:

1.  **The Dynamic Switching Trap**: If your Skybox Manager toggles effects (e.g., "High Quality Sun" vs "No Sun") using `shader_feature`, and your initial material doesn't have the sun enabled, the build won't include the "Sun" variant. It will fail on the device.
    
2.  **Forced Inclusion**: If you must use `shader_feature` to keep the build size small but still need to toggle it via script, you **must** manually add those keyword combinations to your **Shader Variant Collection**. This tells the engine: "I'll need this later, don't strip it!"
    
3.  **Vulkan Strictness**: The Vulkan drivers on OpenHarmony are very strict. If a variant is stripped via `shader_feature` and you try to force it active, Vulkan might throw a driver-level error or cause the rendering process to hang.
    

----------

## 5. Code Example

OpenGL Shading Language

```
// Build generates: None and FOG_ON (both versions included regardless)
#pragma multi_compile _ FOG_ON 

// Build generates: NORMAL_ON ONLY if a material has it checked in the Inspector
#pragma shader_feature _ NORMAL_ON 
```

> **Expert Guide**: As you optimize your Skybox Manager, are you considering moving some rarely used features (like 3D Layout or Mirroring) from `multi_compile` to `shader_feature` to reduce the final package size?
<!--stackedit_data:
eyJoaXN0b3J5IjpbMTc2MzA1MjMwMCwtMTA5MTMwMDExNl19
-->