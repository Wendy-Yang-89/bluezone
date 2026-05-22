# ECS对象关系与材质绑定详解

## 问题背景

在3D渲染系统中，一个常见问题是：**不同相机能否看到同一个物体的不同材质效果？** 典型应用场景：

- 小地图相机使用简化材质，主相机使用完整材质
- 编辑器相机显示调试信息，游戏相机显示最终效果
- VR左右眼渲染不同的视觉效果

要回答此问题，需理解 Lume3D ECS 架构中各对象的层级关系和材质绑定的具体位置。

---

## 一、ECS架构基础

Lume3D 采用 **ECS（Entity-Component-System）** 数据驱动架构：

| 概念 | 定义 | 本文档涉及的示例 |
|------|------|-----------------|
| **Entity** | 唯一标识符（`CORE_NS::Entity`，内部为 `uint64_t id`），代表场景中的一个对象 | MeshComponent Entity、MaterialComponent Entity、CameraComponent Entity |
| **Component** | 数据容器，存储对象的特定属性 | MeshComponent（几何+材质绑定）、MaterialComponent（材质数据）、CameraComponent（观察参数） |
| **System** | 逻辑处理器，操作具有特定Component的Entity | RenderSystem（渲染）、FillMaterialDefaultRenderSlotData（材质填充） |

ECS架构将数据与逻辑分离，便于扩展和复用。

---

## 二、对象层级与材质绑定位置

### 2.1 各对象职责

| 对象 | ECS组件 | 层级 | 职责 | 是否修改材质 |
|------|---------|------|------|-------------|
| **Scene** | — | 顶层容器 | 管理场景内的相机、灯光、渲染对象等实体。多个Scene相互隔离（如主场景、UI场景、编辑器场景） | — |
| **Camera** | `CameraComponent` | 观察者 | 定义观察参数（位置、朝向、视锥体、layerMask），筛选可见对象 | **否** |
| **RenderMeshComponent** | `RenderMeshComponent` | 实例 | Mesh在场景中的实例化：持有mesh引用、世界矩阵、layerMask。同一Mesh可被多个RenderMesh引用（资源复用） | **否** |
| **MeshComponent** | `MeshComponent` | 资源 | 定义几何数据（顶点/索引缓冲）和材质绑定（Submesh::material） | **是（绑定点）** |
| **MaterialComponent** | `MaterialComponent` | 资源 | 定义表面渲染属性（纹理、参数、渲染状态） | — |

### 2.2 层级关系图

```
Scene ──────────────────────────────────────────────────── 顶层容器，多场景隔离
 │
 ├── Camera ───────────────────────────────────── 观察者层
 │    │  CameraComponent
 │    ├── 位置/朝向  ──► 世界坐标系中的相机位置和视线方向
 │    ├── frustum    ──► 视锥体（Frustum），定义可见范围，用于视锥体剔除
 │    ├── layerMask  ──► uint64_t 位掩码，与RenderMesh.layerMask位运算筛选可见对象
 │    └── sceneId    ──► 所属场景ID
 │
 ├── RenderMeshComponent ──────────────────────── 实例层
 │    │  RenderMeshData
 │    ├── meshId     ──► 引用 MeshComponent Entity（不修改材质）
 │    ├── world      ──► 世界矩阵，定义实例的世界坐标变换
 │    └── layerMask  ──► uint64_t 可见性控制，与Camera.layerMask配合筛选
 │
 └── MeshComponent ────────────────────────────── 资源层（材质在此绑定）
      │  RenderSubmeshIndices
      └── submeshes[]:
           │  Submesh 结构体
           ├── material ──► CORE_NS::Entity → MaterialComponent Entity ← 材质绑定在这里
           ├── additionalMaterials ──► BASE_NS::vector<CORE_NS::Entity> 多材质渲染
           └── buffers   ──► 顶点缓冲 + 索引缓冲
                │
                └── Submesh典型示例：汽车模型
                     ├── Submesh[0]: 车身 → 金属材质
                     ├── Submesh[1]: 车窗 → 玻璃材质
                     └── Submesh[2]: 轮胎 → 橡胶材质
```

**关键结论**：材质绑定在 **MeshComponent::Submesh.material**（资源层），而非 RenderMeshComponent（实例层）或 Camera（观察者层）。Camera 和 RenderMeshComponent 都不修改材质。

---

## 三、关键数据结构对应关系

| ECS层级 | 数据层级 | 关键成员 | 说明 |
|--------|---------|---------|------|
| Scene | `RenderMeshData` | `sceneId : uint64_t` | 场景容器 |
| Camera | `CameraComponent` | `layerMask : uint64_t` | 通过 layerMask 筛选渲染对象 |
| RenderMeshComponent | `RenderMeshData` | `meshId : uint64_t`<br>`layerMask : uint64_t`<br>`sceneId : uint64_t` | 网格实例 |
| MeshComponent | `RenderSubmeshIndices` | `meshId : uint64_t` | 网格资源（顶点数据） |
| MeshComponent::Submesh | `RenderSubmeshIndices` | `materialIndex : uint32_t` | **材质绑定点** |
| MaterialComponent | `RenderDataDefaultMaterial::MaterialData` | `materialShader`<br>`depthShader`<br>`renderMaterialFlags`<br>`materialType` | 材质数据 |

---

## 四、材质绑定代码

### 4.1 绑定位置

材质绑定在 `MeshComponent::Submesh` 上（资源层），而非 RenderMesh 或 Camera 上：

```cpp
// api/3d/ecs/components/mesh_component.h:147-150
struct Submesh {
    /** Material to be used with this submesh. */
    CORE_NS::Entity material {};                    // line 147 ← 材质在这里绑定

    /** Material to be used with this submesh. */
    BASE_NS::vector<CORE_NS::Entity> additionalMaterials;  // line 150
};
```

- `material`：主材质，类型为 `CORE_NS::Entity`（即 `Core::Entity`，内部为 `uint64_t id`）
- `additionalMaterials`：额外材质列表，用于多材质渲染场景

### 4.2 数据流向

```
MeshComponent::Submesh.material (CORE_NS::Entity)
    ↓ 解析为索引
RenderSubmeshIndices.materialIndex (uint32_t)
    ↓ 索引查找
RenderDataDefaultMaterial::MaterialData (包含materialShader、depthShader等)
    ↓ 填充渲染槽
FillMaterialDefaultRenderSlotData → RenderSlotData
    ↓
渲染系统使用
```

---

## 五、Camera 如何筛选渲染对象

Camera **不改变材质**，仅通过以下三重筛选决定可见性：

| 筛选机制 | 代码位置 | 筛选规则 | 说明 |
|---------|---------|---------|------|
| **layerMask** | `camera_component.h:255-256` | `RenderMeshData.layerMask & Camera.layerMask != 0` → 可见 | uint64_t 位运算，LayerFlagBits 定义各层 |
| **sceneId** | `RenderMeshData.sceneId : uint64_t` | `RenderMeshData.sceneId == Camera所在Scene` → 可见 | 仅渲染同场景对象 |
| **视锥体剔除** | Camera Frustum | 对象在视锥体内 → 可见 | 进一步剔除视野外对象 |

### 5.1 layerMask 详解

```cpp
// api/3d/ecs/components/camera_component.h:255-256
DEFINE_BITFIELD_PROPERTY(uint64_t, layerMask, "Layer mask",
    PropertyFlags::IS_BITFIELD, VALUE(LayerConstants::LOW_32_LAYER_MASK), LayerFlagBits)

// api/3d/ecs/components/layer_defines.h:28
enum LayerFlagBits : uint64_t {
    CORE_LAYER_FLAG_BIT_00 = 0x1,
    CORE_LAYER_FLAG_BIT_01 = 0x2,
    ...
    CORE_LAYER_FLAG_BIT_63 = 0x8000000000000000,
    CORE_LAYER_FLAG_BIT_ALL = 0xFFFFFFFFFFFFFFFF
};

// api/3d/ecs/components/layer_defines.h:99
struct LayerConstants {
    static constexpr uint64_t DEFAULT_LAYER_MASK { LayerFlagBits::CORE_LAYER_FLAG_BIT_00 };  // 0x1
    static constexpr uint64_t LOW_32_LAYER_MASK  { LayerFlagBits::CORE_LAYER_FLAG_BIT_LOW_32 };  // 低32位
    static constexpr uint64_t ALL_LAYER_MASK     { LayerFlagBits::CORE_LAYER_FLAG_BIT_ALL };  // 所有层
    static constexpr uint64_t NONE_LAYER_MASK    { LayerFlagBits::CORE_LAYER_FLAG_BIT_NONE };  // 无层
};
```

LayerComponent 也可为 Entity 设置 layerMask（`layer_component.h:33-34`），与 Camera 配合筛选。

### 5.2 sceneId 筛选

```cpp
// RenderMeshData.sceneId 与 Camera 所属 Scene 的 sceneId 一致时才渲染
// 跨场景的对象不会出现在其他场景的渲染中
```

### 5.3 视锥体剔除

Camera 的视锥体（Frustum）定义可见范围，不在视野内的对象被剔除，不参与渲染。

---

## 六、核心问题解答

### 问题：对于不同的 Camera，同一个 Submesh 的 Material 可以不一样吗？

**答案：不能。**

材质绑定在 `MeshComponent::Submesh` 上，与 Camera 无关。所有 Camera 看到的同一个 Submesh 都使用相同的材质。

**原因**：

1. **材质是资源级绑定**：Material 绑定在 MeshComponent（资源层），属于共享资源
2. **Camera 是观察者**：Camera 只负责三重筛选（layerMask、sceneId、视锥体），不修改对象属性
3. **RenderMesh 是实例**：RenderMeshComponent 持有 Mesh 的引用和世界矩阵，不修改 Mesh 的材质

---

## 七、如何实现"不同相机看到不同效果"

| 方案 | 原理 | 优点 | 缺点 |
|-----|------|------|------|
| **A: 多Mesh + layerMask** | 创建两个Mesh各自绑定不同材质，配合layerMask分离 | 完全独立，可复用顶点数据 | 需额外Mesh和RenderMesh实例 |
| **B: Shader内动态** | Shader根据cameraIndex选择不同渲染参数 | 不需额外实例，灵活 | 只是效果不同而非材质不同 |
| **C: 动态切换材质** | 渲染前根据Camera切换Submesh.material | 直接有效 | 修改MeshComponent影响所有引用该Mesh的对象 |

### 方案A：多Mesh + layerMask（推荐）

```cpp
// 创建两个 Mesh，各自绑定不同材质
Mesh mesh1; mesh1.submeshes[0].material = materialA;  // 简化材质
Mesh mesh2; mesh2.submeshes[0].material = materialB;  // 完整材质
// 两个 Mesh 可共享相同的 vertex/index buffer（资源复用）

// 创建两个 RenderMesh，使用不同 layerMask
RenderMesh renderMesh1; renderMesh1.mesh = mesh1; renderMesh1.layerMask = LAYER_1;
RenderMesh renderMesh2; renderMesh2.mesh = mesh2; renderMesh2.layerMask = LAYER_2;

// Camera A 只看 LAYER_1（简化材质），Camera B 只看 LAYER_2（完整材质）
cameraA.layerMask = LAYER_1;
cameraB.layerMask = LAYER_2;
```

### 方案B：Shader 内动态选择

```glsl
uniform uint cameraIndex;

vec4 getMaterialColor() {
    if (cameraIndex == 0) {
        return baseColor * factorA;  // Camera A 的效果（如简化着色）
    } else {
        return baseColor * factorB;  // Camera B 的效果（如完整着色）
    }
}
```

这不是"材质不同"，而是同一材质在 Shader 内根据 Camera 参数选择不同的渲染路径。

### 方案C：动态切换材质（需谨慎）

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

**注意**：此方法修改 MeshComponent，影响**所有**使用该 Mesh 的对象。仅在 Mesh 仅被单一 RenderMesh引用时可安全使用。

---

## 八、关键代码位置

| 文件路径 | 关键定义 |
|---------|---------|
| `api/3d/ecs/components/mesh_component.h` | `MeshComponent::Submesh`（147行：material，150行：additionalMaterials） |
| `api/3d/ecs/components/material_component.h` | `MaterialComponent`（Type枚举、TextureInfo、Shader等） |
| `api/3d/ecs/components/camera_component.h` | `CameraComponent`（255-256行：layerMask） |
| `api/3d/ecs/components/render_mesh_component.h` | `RenderMeshComponent`（mesh、renderMeshBatch、customData） |
| `api/3d/ecs/components/layer_component.h` | `LayerComponent`（33-34行：layerMask） |
| `api/3d/ecs/components/layer_defines.h` | `LayerFlagBits : uint64_t`（28行），`LayerConstants`（99行） |
| `api/3d/render/render_data_defines_3d.h` | `RenderMeshData`（140行），`RenderSubmeshIndices`（379行） |
| `api/3d/render/intf_render_data_store_default_material.h` | `RenderDataDefaultMaterial::MaterialData`（183行，嵌套在RenderDataDefaultMaterial内） |