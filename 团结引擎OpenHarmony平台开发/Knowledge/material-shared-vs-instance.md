# renderer.material vs renderer.sharedMaterial

## Overview

When accessing materials on a Renderer, Unity provides two properties that behave very differently:

- `renderer.material` — Returns an **instance** of the material
- `renderer.sharedMaterial` — Returns the **original shared** material

## renderer.material

### Behavior

```csharp
Material mat = renderer.material;
```

1. On first access, Unity checks if the renderer already has an instance material
2. If not, Unity creates a **clone** of the shared material (`new Material(shared)`)
3. The clone is assigned to the renderer
4. Subsequent `renderer.material` calls return the same clone
5. Modifying the clone does NOT affect other renderers using the same shared material

### Important Details

- The clone is created lazily (on first get)
- The clone is named `"<SharedMaterialName> (Instance)"`
- The clone adds to the material count in the "Materials" panel
- Modifications to the clone are **independent** of the original
- Calling `renderer.material` on multiple renderers with the same shared material creates **separate clones for each**

### When to Use

- When you need to modify a material for a **single renderer** without affecting others
- When you need per-object material properties (e.g., different colors per object)

## renderer.sharedMaterial

### Behavior

```csharp
Material mat = renderer.sharedMaterial;
```

1. Returns the original material asset directly
2. No cloning occurs
3. **Modifying this material affects ALL renderers using it**
4. In the Editor, modifications persist to the asset on disk

### When to Use

- When reading material properties without modifying them
- When you intentionally want changes to affect all users of the material
- When restoring the original material (e.g., in `OnDestroy`)

## In This Project

### MaterialManager

```csharp
// Apply: creates instance, modifications don't affect other renderers
renderer.material = runtimeMaterial;

// Remove: restores the original shared material
renderer.sharedMaterial = originalMaterial;
```

The `originalMaterial` is captured via `renderer.sharedMaterial` **before** the first `renderer.material` access, because accessing `renderer.material` creates the instance and "replaces" the shared reference.

### TransparentManager

Each transparent plane gets a unique material instance:

```csharp
Material mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
// ... configure mat ...
renderer.material = mat;  // assigns the unique instance
```

Since each plane has its own color, each needs its own material. Using `sharedMaterial` here would make all planes the same color.

### TextureManager (Billboard)

```csharp
billboardMaterial = new Material(Shader.Find("Hidden/TextureArrayGrid"));
renderer.material = billboardMaterial;
```

Single billboard with a unique material — no sharing concern.

## Common Pitfalls

1. **Material leak**: Every `renderer.material` access creates a new instance if none exists. If you access it in `Update()` without caching, you'll create a new instance every frame. **Always cache the reference.**

2. **Orphaned instances**: If you assign `renderer.material` but never destroy the instance, it persists in memory. Always `Destroy()` instance materials when the object is destroyed.

3. **Editor persistence**: Modifying `renderer.sharedMaterial` in Editor PlayMode persists to disk (same ScriptableObject behavior as described in scriptableobject-lifecycle.md).

4. **Reading the wrong one**: If you've already triggered instance creation via `renderer.material`, then `renderer.sharedMaterial` still returns the **original**, not the instance. Use `renderer.material` to get the current active material.

5. **Multiple materials**: For renderers with multiple materials (sub-meshes), use `renderer.materials` / `renderer.sharedMaterials` (arrays). Note that `renderer.materials` creates instances for ALL sub-materials on access.
