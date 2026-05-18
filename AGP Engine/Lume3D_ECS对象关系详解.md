# Lume3D ECS对象关系详解

## 一、概述

本文档详细说明 Lume3D ECS 架构中 Scene、Camera、Material、Submesh 等对象的对应关系，以及不同相机是否能看到不同材质的问题。

---

## 二、核心关系图

```
Scene (场景)
├── Camera (相机)
│   └── layerMask: 筛选可见对象
│   └── sceneId: 所属场景ID
│
├── RenderMesh (渲染网格实例)
│   └── mesh: → MeshComponent Entity
│   └── layerMask: 可见性控制
│   └── world: 世界矩阵
│
└── Mesh (网格资源)
    └── submeshes[]:
        └── material: → MaterialComponent Entity  ← 材质在这里绑定
        └── buffers: 顶点/索引数据
```

---

## 三、关键数据结构对应关系

| ECS层级 | 数据层级 | 说明 |
|--------|---------|------|
| Scene | `sceneId` | 场景容器 |
| Camera | `layerMask` | 通过 layerMask 筛选渲染对象 |
| RenderMeshComponent | `RenderMeshData` | 网格实例（世界矩阵） |
| MeshComponent | `RenderSubmeshIndices.meshId` | 网格资源（顶点数据） |
| MeshComponent::Submesh | `RenderSubmeshIndices.materialIndex` | **材质绑定点** |
| MaterialComponent | `RenderDataDefaultMaterial::MaterialData` | 材质数据 |

---

## 四、材质绑定位置

### 4.1 代码位置

材质绑定在 `MeshComponent::Submesh` 上，而不是在 RenderMesh 或 Camera 上：

```cpp
// mesh_component.h:146-147
struct Submesh {
    /** Material to be used with this submesh. */
    CORE_NS::Entity material {};  // ← 材质在这里绑定
    
    /** Additional materials for multi-material rendering */
    BASE_NS::vector<CORE_NS::Entity> additionalMaterials;
};
```

### 4.2 数据流向

```
MeshComponent::Submesh.material (Entity)
    ↓
RenderSubmeshIndices.materialIndex (uint32_t)
    ↓
RenderDataDefaultMaterial::MaterialData
    ↓
FillMaterialDefaultRenderSlotData → RenderSlotData
    ↓
渲染系统使用
```

---

## 五、Camera 如何影响渲染

Camera **不改变材质**，只通过以下方式筛选渲染对象：

### 5.1 layerMask 筛选

```cpp
// camera_component.h:255
DEFINE_BITFIELD_PROPERTY(uint64_t, layerMask, "Layer mask", ...)

// RenderMeshData.layerMask & Camera.layerMask != 0 → 对象可见
```

Camera 通过 `layerMask` 位运算筛选哪些 RenderMesh 应该被渲染。

### 5.2 sceneId 筛选

```cpp
// RenderMeshData.sceneId == Camera所在scene → 对象可见
```

### 5.3 View Frustum Culling

Camera 的视锥体剔除会进一步筛选不在视野内的对象。

---

## 六、核心问题解答

### 问题：对于不同的 camera，同一个 submesh 的 material 可以不一样吗？

**答案：不能。**

材质绑定在 `MeshComponent::Submesh` 上，与 Camera 无关。所有 Camera 看到的同一个 submesh 都使用相同的材质。

### 原因分析

1. **材质是资源级绑定**：Material 绑定在 MeshComponent 上，属于资源层
2. **Camera 是观察者**：Camera 只负责筛选（layerMask、sceneId、视锥体），不修改对象属性
3. **RenderMesh 是实例**：RenderMeshComponent 持有 Mesh 的引用，不修改 Mesh 的材质

---

## 七、如何实现"不同相机看到不同效果"

如果需要不同相机看到不同的材质效果，有以下方案：

### 方案A：多个 RenderMesh + 不同 Mesh（推荐）

创建两个 Mesh 实例，各自使用不同材质，配合 layerMask 分离：

```cpp
// 创建两个 Mesh，各自使用不同材质
Mesh mesh1; mesh1.submeshes[0].material = materialA;
Mesh mesh2; mesh2.submeshes[0].material = materialB;

// 创建两个 RenderMesh，使用不同的 layerMask
RenderMesh renderMesh1; 
renderMesh1.mesh = mesh1; 
renderMesh1.layerMask = LAYER_1;

RenderMesh renderMesh2; 
renderMesh2.mesh = mesh2; 
renderMesh2.layerMask = LAYER_2;

// Camera A 只看 LAYER_1
cameraA.layerMask = LAYER_1;

// Camera B 只看 LAYER_2
cameraB.layerMask = LAYER_2;
```

**优点：**
- 完全独立，每个相机看到不同的材质
- 可复用顶点数据（相同的 vertex/index buffer）

**缺点：**
- 需要创建额外的 Mesh 和 RenderMesh 实例

### 方案B：Shader 内根据 Camera 动态变化

不改变材质，在 Shader 中根据 camera index 选择不同的渲染参数：

```glsl
// 在 shader 中根据 camera index 选择不同的参数
uniform uint cameraIndex;

vec4 getMaterialColor() {
    if (cameraIndex == 0) {
        return baseColor * factorA;  // Camera A 的效果
    } else {
        return baseColor * factorB;  // Camera B 的效果
    }
}
```

**优点：**
- 不需要额外的 Mesh 实例
- 灵活，可以根据多个参数动态变化

**缺点：**
- 这不是"材质不同"，只是渲染效果不同
- Shader 需要特殊处理

### 方案C：RenderHandleComponent 动态切换（高级）

通过 RenderHandleComponent 在渲染前动态切换材质：

```cpp
// 在渲染前根据 Camera 切换材质
void OnPreRender(Camera camera) {
    if (camera == cameraA) {
        submesh.material = materialA;
    } else {
        submesh.material = materialB;
    }
    // 需要重新提交到 RenderDataStoreDefaultMaterial
}
```

**注意：** 这种方法会修改 MeshComponent，影响所有使用该 Mesh 的对象。

---

## 八、关键代码位置

| 文件路径 | 功能 |
|---------|------|
| `api/3d/ecs/components/mesh_component.h` | MeshComponent 定义，材质绑定点 |
| `api/3d/ecs/components/material_component.h` | MaterialComponent 定义 |
| `api/3d/ecs/components/camera_component.h` | CameraComponent 定义，layerMask |
| `api/3d/ecs/components/layer_component.h` | LayerComponent 定义 |
| `api/3d/ecs/components/layer_defines.h` | LayerFlagBits 定义 |
| `api/3d/ecs/components/render_mesh_component.h` | RenderMeshComponent 定义 |
| `api/3d/render/render_data_defines_3d.h` | RenderMeshData、RenderSubmeshIndices 定义 |
| `api/3d/render/intf_render_data_store_default_material.h` | MaterialData 定义 |

---

## 九、总结

### 9.1 对象关系要点

1. **Material** 绑定在 **MeshComponent::Submesh** 上
2. **Camera** 只筛选渲染对象，不修改材质
3. **RenderMesh** 持有 Mesh 引用，是网格实例
4. **LayerMask** 是 Camera 和 RenderMesh 之间的筛选桥梁

### 9.2 材质不可变性

同一个 submesh 在不同 Camera 下看到的材质是相同的。如果需要不同效果，需要：
- 创建多个 Mesh 实例 + layerMask 分离
- 或在 Shader 内动态处理

---

**文档版本**: 1.0  
**创建日期**: 2026-05-18  
**状态**: 新建