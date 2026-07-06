# Case: CreatePrimitive MeshCollider Stripped in Tuanjie Build

## Problem

`TextureManager` and `TransparentManager` used `GameObject.CreatePrimitive(PrimitiveType.Quad)` to create quad meshes. This caused a build error on Tuanjie 2022.3.62t2.

## Error Log

```
The type or namespace name 'MeshCollider' could not be found
```

## Diagnosis Process

1. Build failed with `MeshCollider` not found
2. Searched codebase — no explicit `MeshCollider` usage
3. Discovered `GameObject.CreatePrimitive()` internally adds a `MeshCollider` component
4. In Tuanjie's stripped build, `MeshCollider` class is removed by IL2CPP stripping

## Root Cause

`GameObject.CreatePrimitive(PrimitiveType.Quad)` is a convenience method that creates:
- A GameObject with MeshFilter + MeshRenderer
- **A MeshCollider component** (added automatically)

In Tuanjie's build configuration (especially for OHOS), the `MeshCollider` class is stripped by IL2CPP because no code references it directly. The `CreatePrimitive` method uses it internally, but the linker doesn't see this dependency.

This is a Tuanjie-specific issue — stock Unity typically preserves `MeshCollider` in the linked output.

## Fix

Replace `CreatePrimitive(PrimitiveType.Quad)` with manual quad mesh creation:

```csharp
private static Mesh CreateQuadMesh()
{
    Mesh mesh = new Mesh();
    mesh.vertices = new Vector3[]
    {
        new Vector3(-0.5f, -0.5f, 0f),
        new Vector3(0.5f, -0.5f, 0f),
        new Vector3(-0.5f, 0.5f, 0f),
        new Vector3(0.5f, 0.5f, 0f)
    };
    mesh.uv = new Vector2[]
    {
        new Vector2(0f, 0f),
        new Vector2(1f, 0f),
        new Vector2(0f, 1f),
        new Vector2(1f, 1f)
    };
    mesh.triangles = new int[] { 0, 2, 1, 2, 3, 1 };
    mesh.RecalculateNormals();
    return mesh;
}
```

Then use `MeshFilter.mesh = CreateQuadMesh()` + `MeshRenderer` instead of `CreatePrimitive`.

## Lesson

**In engine forks (Tuanjie, etc.), be cautious with convenience APIs that internally reference types that might be stripped.** Prefer explicit construction to avoid hidden dependencies on stripped classes.
