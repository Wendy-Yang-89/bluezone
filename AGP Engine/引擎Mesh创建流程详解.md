# 引擎Mesh创建流程详解

## 1. 概述

Lume引擎的Mesh创建采用三层架构：

| 层级 | 职责 | 核心函数 |
|------|------|----------|
| 第一层：几何生成 | 根据参数化方程生成顶点、法线、UV、索引等原始几何数据 | `GenerateSphereGeometry` |
| 第二层：IMeshBuilder管线 | 将几何数据注入IMeshBuilder，完成切线计算、格式映射、AABB计算，构建GPU可用的Mesh资源 | `GenerateSphereMesh` |
| 第三层：ECS实体化 | 将Mesh资源注册到ECS系统，附加Name/Uri组件，包装为可渲染的Scene节点实体 | `GenerateSphere` |

典型调用方式（OIT示例，`samples/multiplatform/oit/src/oit.cpp:539-543`）：

```cpp
meshUtil.GenerateSphere(*engine_, "sphere", materialHandle, 0.5f, 32, 32)
```

---

## 2. 三层调用链总览

```
GenerateSphere(ecs, name, material, radius, rings, sectors)          ← 第三层入口
│
├── GenerateSphereMesh(ecs, name, material, radius, rings, sectors)  ← 第二层入口
│   │
│   ├── ValidateSphereMeshParameters(radius, rings, sectors)         ← 参数校验
│   │
│   ├── GenerateSphereGeometry(radius, rings, sectors, geometry)     ← 第一层：几何生成
│   │   └── 输出: vertices, normals, uvs, indices
│   │
│   ├── CalculateTangents(...)                                       ← 切线计算
│   │
│   ├── PickIndexType(vertexCount)                                   ← 索引类型选择
│   │
│   ├── MakeSubmesh(material, vertexCount, indexCount, indexType)    ← 子网格构造
│   │
│   ├── InitializeBuilder(submesh)                                   ← Builder初始化
│   │   ├── 获取IRenderContext
│   │   ├── 获取VertexInputDeclaration (VID)
│   │   ├── CreateInstance<IMeshBuilder>
│   │   ├── builder->Initialize(vid, submeshCount)
│   │   ├── builder->AddSubmesh(submesh)
│   │   └── builder->Allocate()
│   │
│   ├── FillBuilder(*builder, vertexBuffers, indices)                ← 数据填充
│   │   ├── SetVertexData(positions, normals, uvs, dummy, tangents, dummy)
│   │   ├── CalculateAABB(positions)
│   │   └── SetIndexData(indices)
│   │
│   └── CreateMesh(ecs, *builder, name)                              ← 创建Mesh实体
│       ├── builder->CreateMesh(ecs)
│       ├── IUriComponentManager->Set(entity, name)
│       └── INameComponentManager->Set(entity, name)
│
└── GenerateEntity(ecs, name, meshHandle)                            ← 包装为渲染节点
```

---

## 3. 第一层：几何数据生成

### 3.1 函数签名

```cpp
// src/util/mesh_util.cpp:247
void GenerateSphereGeometry(float radius, uint32_t rings, uint32_t sectors, Geometry<uint32_t> geometry)
```

`Geometry` 是简单的引用包装模板（`src/util/mesh_util.cpp:115-121`）：

```cpp
template<typename IndexType>
struct Geometry {
    vector<Math::Vec3>& vertices;
    vector<Math::Vec3>& normals;
    vector<Math::Vec2>& uvs;
    vector<IndexType>& indices;
};
```

调用方在外部声明四个vector，以`Geometry`结构传入，函数直接填充。

### 3.2 球面参数化方程

球面使用经典球坐标系参数化，参数为纬度角（ring角度）和经度角（sector角度）：

```
ringAngle  = π × (ring / (rings - 1))         ∈ [0, π]
sectorAngle = 2π × (sector / (sectors - 1))    ∈ [0, 2π)
```

笛卡尔坐标转换：

```
x = cos(sectorAngle) × sin(ringAngle)
y = sin(-π/2 + ringAngle) = -cos(ringAngle)
z = sin(sectorAngle) × sin(ringAngle)
```

注意源码中 `y = sin(-halfPi + ringAngle)`，利用 `sin(-π/2 + θ) = -cos(θ)`，因此：
- ring=0 时 ringAngle=0，y = sin(-π/2) = -1（南极）
- ring=rings-1 时 ringAngle=π，y = sin(π/2) = 1（北极）

最终顶点位置 = `(x × radius, y × radius, z × radius)`。

### 3.3 内存预分配

```cpp
const size_t maxVertexCount = rings * sectors;
const size_t maxIndexCount  = (rings - 1) * sectors * 6;
```

- 顶点数 = rings × sectors（每个ring-sector交叉点一个顶点）
- 索引数 = (rings-1) × sectors × 6（每个四边形拆为2个三角形，每三角形3个索引）

### 3.4 顶点生成

双重循环 `ring × sector`，每次迭代：

1. **计算ring相关量**：`ringAngle`、`ringSin = sin(ringAngle)`、`y`
2. **计算sector相关量**：`sectorAngle`、`x`、`z`
3. **写入顶点数据**：
   - `vertices.emplace_back(x * radius, y * radius, z * radius)` — 位置
   - `normals.emplace_back(x, y, z)` — 法线
   - `uvs.emplace_back(sectorF * s, ringF * r)` — 纹理坐标

#### 法线

由于球心在原点，法线 = 归一化的位置向量。源码中 `radius` 只乘在 `vertices` 上，`normals` 存储的是单位球上的方向 `(x, y, z)`，本身已归一化。

#### UV映射

```
u = sector / (sectors - 1)     ∈ [0, 1]
v = ring   / (rings - 1)       ∈ [0, 1]
```

v=0 对应南极，v=1 对应北极，u沿经度方向展开。

### 3.5 索引生成

仅当 `ring < rings - 1`（非极点环）时生成索引：

```cpp
const uint32_t curRow  = ring * sectors;
const uint32_t nextRow = (ring + 1) * sectors;
const uint32_t nextS   = (sector + 1) % sectors;

// 三角形1: curRow+sector → nextRow+sector → nextRow+nextS
// 三角形2: curRow+sector → nextRow+nextS  → curRow+nextS
```

每个(ring, sector)处的四边形由当前行和下一行的两个相邻顶点构成：

```
curRow+nextS ──── nextRow+nextS
     │  ╲  T2  ╱  │
     │   ╲    ╱    │
     │  T1 ╲ ╱     │
curRow+sector ──── nextRow+sector
```

`nextS = (sector + 1) % sectors` 实现经度方向的环形闭合。

### 3.6 具体数值举例：rings=4, sectors=8

| 参数 | 值 |
|------|-----|
| 顶点数 | 4 × 8 = 32 |
| 索引数 | 3 × 8 × 6 = 144 |
| 三角形数 | 144 / 3 = 48 |
| 四边形数 | 3 × 8 = 24 |

ring=0（南极）：ringAngle=0，ringSin=0，所有顶点汇聚于 (0, -radius, 0)

ring=1：ringAngle=π/3，8个顶点分布在纬度圈上

ring=2：ringAngle=2π/3，8个顶点分布在纬度圈上

ring=3（北极）：ringAngle=π，ringSin=0，所有顶点汇聚于 (0, radius, 0)

索引示例（ring=1, sector=0）：
- curRow = 1×8 = 8，nextRow = 2×8 = 16，nextS = 1
- 三角形1: 索引[8, 16, 17]
- 三角形2: 索引[8, 17, 9]

> 注意：极点处多个顶点重合（位置相同但UV不同），这是经纬线参数化的固有特征，会导致极点处三角形的退化。

---

## 4. 第二层：IMeshBuilder管线

### 4.1 函数签名

```cpp
// src/util/mesh_util.cpp:769
Entity MeshUtil::GenerateSphereMesh(
    const IEcs& ecs, const string_view name, Entity material,
    float radius, uint32_t rings, uint32_t sectors)
```

返回值为 `Entity`，即Mesh实体句柄；失败时返回空Entity。

### 4.2 参数校验

```cpp
if (!ValidateSphereMeshParameters(radius, rings, sectors)) {
    return {};
}
```

校验规则基于以下常量：

| 常量 | 值 | 含义 |
|------|-----|------|
| `SPHERE_MIN_RINGS` | 2 | 最小环数（南北极两点） |
| `SPHERE_MIN_SECTORS` | 2 | 最小扇区数 |
| `MESH_MAX_SECTORS` | 4096 | 最大扇区数（防止索引溢出） |

radius必须为正数，rings ≥ 2，sectors ∈ [2, 4096]。

### 4.3 切线计算

```cpp
vector<Math::Vec4> tangents(vertices.size());
CalculateTangents(
    indices, vertices, normals, uvs,
    PrimitiveTopology::CORE_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, tangents);
```

切线向量用于法线贴图（normal mapping），由位置、法线、UV通过相邻三角形的纹理空间梯度推导。输出为 `Vec4`，第四分量为副法线方向的符号（handedness）。

### 4.4 索引类型选择

```cpp
// src/util/mesh_util.cpp:543-546
IndexType PickIndexType(uint32_t vertexCount)
{
    return vertexCount <= UINT16_MAX ? CORE_INDEX_TYPE_UINT16 : CORE_INDEX_TYPE_UINT32;
}
```

| 顶点数 | 索引类型 | 每索引字节数 |
|--------|----------|-------------|
| ≤ 65535 | `CORE_INDEX_TYPE_UINT16` | 2 |
| > 65535 | `CORE_INDEX_TYPE_UINT32` | 4 |

示例：rings=32, sectors=32 → 顶点数=1024 → 使用uint16索引。

### 4.5 子网格构造

```cpp
// src/util/mesh_util.cpp:532-541
IMeshBuilder::Submesh MakeSubmesh(Entity material, uint32_t vertexCount, uint32_t indexCount, IndexType indexType)
{
    IMeshBuilder::Submesh submesh;
    submesh.material    = material;
    submesh.vertexCount = vertexCount;
    submesh.indexCount  = indexCount;
    submesh.indexType   = indexType;
    submesh.tangents    = true;
    return submesh;
}
```

`Submesh` 完整定义（`api/3d/util/intf_mesh_builder.h:59-83`）：

| 字段 | 类型 | 默认值 | MakeSubmesh设置 |
|------|------|--------|----------------|
| `vertexCount` | uint32_t | 0 | 传入值 |
| `indexCount` | uint32_t | 0 | 传入值 |
| `instanceCount` | uint32_t | 1 | 默认 |
| `morphTargetCount` | uint32_t | 0 | 默认 |
| `indexType` | IndexType | UINT32 | PickIndexType结果 |
| `material` | Entity | 空 | 传入值 |
| `tangents` | bool | false | **true** |
| `colors` | bool | false | 默认 |
| `joints` | bool | false | 默认 |
| `inputAssembly` | RenderSubmeshInputAssemblyType | TOPOLOGY | 默认 |

### 4.6 Builder初始化

```cpp
// src/util/mesh_util.cpp:990-1009
IMeshBuilder::Ptr MeshUtil::InitializeBuilder(const IMeshBuilder::Submesh& submesh) const
{
    IMeshBuilder::Ptr builder;
    if (IClassRegister* classRegister = factory_.GetInterface<IClassRegister>(); classRegister) {
        auto renderContext = CORE3D_NS::GetInstance<IRenderContext>(*classRegister, UID_RENDER_CONTEXT);
        if (!renderContext) {
            return {};
        }
        IShaderManager& shaderManager = renderContext->GetDevice().GetShaderManager();
        const VertexInputDeclarationView vertexInputDeclaration =
            shaderManager.GetVertexInputDeclarationView(shaderManager.GetVertexInputDeclarationHandle(
                DefaultMaterialShaderConstants::VERTEX_INPUT_DECLARATION_FORWARD));
        builder = CORE3D_NS::CreateInstance<IMeshBuilder>(*renderContext, UID_MESH_BUILDER);
        builder->Initialize(vertexInputDeclaration, 1);
        builder->AddSubmesh(submesh);
        builder->Allocate();
    }
    return builder;
}
```

初始化流程：

```
IClassRegister
    │
    ├── GetInstance<IRenderContext>(UID_RENDER_CONTEXT)
    │       │
    │       └── IRenderContext
    │               │
    │               └── GetDevice().GetShaderManager()
    │                       │
    │                       └── GetVertexInputDeclarationView(VERTEX_INPUT_DECLARATION_FORWARD)
    │                               │
    │                               └── VertexInputDeclarationView (VID)
    │                                       定义顶点属性的布局和语义
    │
    ├── CreateInstance<IMeshBuilder>(renderContext, UID_MESH_BUILDER)
    │
    ├── builder->Initialize(vid, submeshCount=1)
    │       告知Builder：使用此VID布局，包含1个子网格
    │
    ├── builder->AddSubmesh(submesh)
    │       注册子网格的元数据（顶点数、索引数、材质等）
    │
    └── builder->Allocate()
            根据VID和Submesh信息分配GPU缓冲区
```

关键点：
- `VERTEX_INPUT_DECLARATION_FORWARD` 指定前向渲染通道的顶点输入布局，决定了SetVertexData时各属性的解析方式
- `Initialize` 的第二个参数 `1` 表示子网格数量
- `Allocate()` 在 `AddSubmesh` 之后调用，一次性分配所需内存

### 4.7 数据填充

```cpp
// src/util/mesh_util.cpp:555-562
void FillBuilder(IMeshBuilder& builder, const VertexBufferData& vertexBuffers, IMeshBuilder::DataBuffer indices)
{
    IMeshBuilder::DataBuffer dummy {};
    builder.SetVertexData(
        0, vertexBuffers.positions, vertexBuffers.normals, vertexBuffers.uvs,
        dummy, vertexBuffers.tangents, dummy);
    builder.CalculateAABB(0, vertexBuffers.positions);
    builder.SetIndexData(0, indices);
}
```

`SetVertexData` 参数列表（子网格索引0）：

| 参数位置 | 属性 | 数据来源 | 说明 |
|----------|------|----------|------|
| 1 | positions | vertices | Vec3 |
| 2 | normals | normals | Vec3 |
| 3 | uvs | uvs | Vec2 |
| 4 | (reserved) | dummy | 空 |
| 5 | tangents | tangents | Vec4 |
| 6 | (reserved) | dummy | 空 |

两个 `dummy` 占位符对应VID中定义但不使用的数据槽（副法线、颜色等）。

`CalculateAABB` 根据位置数据计算轴对齐包围盒，用于视锥裁剪。

### 4.8 数据格式映射 — FillData\<T\>模板

```cpp
// src/util/mesh_util.cpp:700-729
template<typename T>
constexpr inline IMeshBuilder::DataBuffer FillData(array_view<const T> c) noexcept
{
    Format format = BASE_FORMAT_UNDEFINED;
    if constexpr (is_same_v<T, Math::Vec2>) {
        format = BASE_FORMAT_R32G32_SFLOAT;
    } else if constexpr (is_same_v<T, Math::Vec3>) {
        format = BASE_FORMAT_R32G32B32_SFLOAT;
    } else if constexpr (is_same_v<T, Math::Vec4>) {
        format = BASE_FORMAT_R32G32B32A32_SFLOAT;
    } else if constexpr (is_same_v<T, uint16_t>) {
        format = BASE_FORMAT_R16_UINT;
    } else if constexpr (is_same_v<T, uint32_t>) {
        format = BASE_FORMAT_R32_UINT;
    }
    return IMeshBuilder::DataBuffer { format, sizeof(T),
        { reinterpret_cast<const uint8_t*>(c.data()), c.size() * sizeof(T) } };
}
```

类型到GPU格式的映射：

| C++类型 | GPU格式 | 字节数 | 用途 |
|---------|---------|--------|------|
| `Math::Vec2` | `BASE_FORMAT_R32G32_SFLOAT` | 8 | UV坐标 |
| `Math::Vec3` | `BASE_FORMAT_R32G32B32_SFLOAT` | 12 | 位置、法线 |
| `Math::Vec4` | `BASE_FORMAT_R32G32B32A32_SFLOAT` | 16 | 切线 |
| `uint16_t` | `BASE_FORMAT_R16_UINT` | 2 | 索引（小网格） |
| `uint32_t` | `BASE_FORMAT_R32_UINT` | 4 | 索引（大网格） |

`DataBuffer` 结构体（`api/3d/util/intf_mesh_builder.h:121-128`）：

```cpp
struct DataBuffer {
    Format format { BASE_FORMAT_UNDEFINED };       // GPU数据格式
    size_t stride { 0u };                          // 单元素字节数
    BASE_NS::array_view<const uint8_t> buffer;     // 原始字节视图
};
```

`FillData` 将类型化的 `vector<T>` 转换为 `DataBuffer`：标注格式、步长、以及将数据指针 `reinterpret_cast` 为 `const uint8_t*` 并计算总字节数。这是CPU内存到GPU缓冲区上传前的标准中间表示。

---

## 5. 第三层：ECS实体化

### 5.1 GenerateSphere

```cpp
// src/util/mesh_util.cpp:949-957
Entity MeshUtil::GenerateSphere(
    const IEcs& ecs, const string_view name, Entity material,
    float radius, uint32_t rings, uint32_t sectors)
{
    const Entity meshHandle = GenerateSphereMesh(ecs, name, material, radius, rings, sectors);
    if (meshHandle == Entity {}) {
        return {};
    }
    return GenerateEntity(ecs, name, meshHandle);
}
```

这是最外层入口，串联第二层和第三层：
1. 调用 `GenerateSphereMesh` 获取Mesh实体
2. 调用 `GenerateEntity` 将Mesh实体包装为可渲染节点

### 5.2 CreateMesh — Mesh实体的注册

```cpp
// src/util/mesh_util.cpp:1012-1020
Entity MeshUtil::CreateMesh(const IEcs& ecs, const IMeshBuilder& builder, const string_view name) const
{
    auto meshEntity = builder.CreateMesh(const_cast<IEcs&>(ecs));
    if (!name.empty()) {
        GetManager<IUriComponentManager>(ecs)->Set(meshEntity, { string(name) });
        GetManager<INameComponentManager>(ecs)->Set(meshEntity, { string(name) });
    }
    return meshEntity;
}
```

三步操作：

1. **`builder.CreateMesh(ecs)`** — 将Builder中已填充的GPU数据提交到ECS，创建一个拥有MeshComponent的实体
2. **`IUriComponentManager->Set`** — 为实体设置URI组件，用于资源定位
3. **`INameComponentManager->Set`** — 为实体设置名称组件，用于编辑器和调试

此时实体仅有MeshComponent + NameComponent + UriComponent，尚未具备渲染能力。

### 5.3 GenerateEntity — 可渲染节点的创建

```cpp
return GenerateEntity(ecs, name, meshHandle);
```

`GenerateEntity` 将Mesh实体包装为Scene节点，附加NodeComponent、RenderMeshComponent等组件，使其成为可参与渲染管线的工作节点。这是从"Mesh数据资源"到"可渲染场景对象"的关键转换。

---

## 6. IMeshBuilder核心数据结构

### 6.1 DataBuffer

```cpp
// api/3d/util/intf_mesh_builder.h:121-128
struct DataBuffer {
    Format format { BASE_FORMAT_UNDEFINED };       // Vulkan兼容的格式枚举
    size_t stride { 0u };                          // 单个元素的字节大小
    BASE_NS::array_view<const uint8_t> buffer;     // 数据的字节视图（不拥有内存）
};
```

`DataBuffer` 是CPU端数据到GPU缓冲区的桥梁。`buffer` 是非拥有视图，指向调用方持有的 `vector` 内存。因此Builder在 `Allocate()` 之后、`CreateMesh()` 之前，原始vector必须保持有效。

### 6.2 Submesh

```cpp
// api/3d/util/intf_mesh_builder.h:59-83
struct Submesh {
    uint32_t vertexCount { 0u };
    uint32_t indexCount { 0u };
    uint32_t instanceCount { 1u };
    uint32_t morphTargetCount { 0u };
    IndexType indexType { CORE_INDEX_TYPE_UINT32 };
    Entity material;
    bool tangents { false };
    bool colors { false };
    bool joints { false };
    RenderSubmeshInputAssemblyType inputAssembly {
        RenderSubmeshInputAssemblyType::CORE_RENDER_SUBMESH_INPUT_ASSEMBLY_TOPOLOGY};
};
```

| 字段 | 说明 |
|------|------|
| `vertexCount` | 子网格顶点数 |
| `indexCount` | 子网格索引数 |
| `instanceCount` | 实例化渲染的实例数，默认1 |
| `morphTargetCount` | 变形目标数，用于动画融合 |
| `indexType` | uint16或uint32 |
| `material` | 关联的材质实体 |
| `tangents` | 是否包含切线数据 |
| `colors` | 是否包含顶点颜色 |
| `joints` | 是否包含骨骼权重 |
| `inputAssembly` | 拓扑类型（三角形列表、条带等） |

### 6.3 IMeshBuilder工作流程

```
CreateInstance<IMeshBuilder>
        │
        ▼
   Initialize(VID, submeshCount)
        │  注册顶点布局和子网格数量
        ▼
   AddSubmesh(submesh) × N
        │  注册每个子网格的元数据
        ▼
   Allocate()
        │  根据元数据分配缓冲区
        ▼
   SetVertexData(submeshIndex, positions, normals, uvs, ..., tangents, ...)
   CalculateAABB(submeshIndex, positions)
   SetIndexData(submeshIndex, indices)
        │  填充实际几何数据
        ▼
   CreateMesh(ecs)
        │  提交到ECS，返回Mesh实体
        ▼
   [Mesh Entity]
```

---

## 7. 完整数据流图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         用户层调用                                      │
│   meshUtil.GenerateSphere(ecs, "sphere", material, 0.5f, 32, 32)      │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  第一层：几何数据生成                                                    │
│                                                                         │
│   参数: radius=0.5, rings=32, sectors=32                                │
│          │                                                              │
│          ▼                                                              │
│   ┌──────────────────────────────────────┐                              │
│   │  球面参数化                           │                              │
│   │  ringAngle  = π × ring/31            │                              │
│   │  sectorAngle = 2π × sector/31        │                              │
│   │          │                           │                              │
│   │          ▼                           │                              │
│   │  笛卡尔坐标                           │                              │
│   │  x = cos(sectorAngle)×sin(ringAngle) │                              │
│   │  y = sin(-π/2 + ringAngle)           │                              │
│   │  z = sin(sectorAngle)×sin(ringAngle) │                              │
│   └──────────────┬───────────────────────┘                              │
│                  │                                                      │
│                  ▼                                                      │
│   输出数据:                                                              │
│   ┌────────────────┐  ┌────────────────┐  ┌──────────┐  ┌───────────┐ │
│   │ vertices       │  │ normals        │  │ uvs      │  │ indices   │ │
│   │ Vec3 × 1024    │  │ Vec3 × 1024    │  │ Vec2×1024│  │ uint32    │ │
│   │ 12 bytes each  │  │ 12 bytes each  │  │ 8 each   │  │ × 5952    │ │
│   └───────┬────────┘  └───────┬────────┘  └────┬─────┘  └─────┬─────┘ │
└───────────┼───────────────────┼────────────────┼──────────────┼────────┘
            │                   │                │              │
            ▼                   ▼                │              │
┌───────────────────────────────────────────────┐│              │
│  CalculateTangents                             ││              │
│  输入: indices, vertices, normals, uvs         ││              │
│  输出: tangents (Vec4 × 1024)                  ││              │
└───────────────────────┬───────────────────────┘│              │
                        │                        │              │
                        ▼                        ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  第二层：IMeshBuilder管线                                                │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────┐           │
│   │  FillData<T> 类型 → DataBuffer 映射                     │           │
│   │                                                         │           │
│   │  vector<Vec3> → DataBuffer{R32G32B32_SFLOAT, 12, ptr}   │           │
│   │  vector<Vec2> → DataBuffer{R32G32_SFLOAT,     8,  ptr}   │           │
│   │  vector<Vec4> → DataBuffer{R32G32B32A32_SFLOAT,16, ptr}  │           │
│   │  vector<uint32>→ DataBuffer{R32_UINT,         4,  ptr}   │           │
│   └────────────────────────┬────────────────────────────────┘           │
│                            │                                            │
│                            ▼                                            │
│   ┌─────────────────────────────────────────────────────────┐           │
│   │  InitializeBuilder                                       │           │
│   │  1. IRenderContext → IShaderManager → VID                │           │
│   │  2. CreateInstance<IMeshBuilder>                         │           │
│   │  3. Initialize(VID, submeshCount=1)                     │           │
│   │  4. AddSubmesh({material, 1024, 5952, UINT16, ...})     │           │
│   │  5. Allocate() — GPU缓冲区分配                           │           │
│   └────────────────────────┬────────────────────────────────┘           │
│                            │                                            │
│                            ▼                                            │
│   ┌─────────────────────────────────────────────────────────┐           │
│   │  FillBuilder                                             │           │
│   │  SetVertexData(0, positions, normals, uvs, _, tangents) │           │
│   │  CalculateAABB(0, positions)                             │           │
│   │  SetIndexData(0, indices)                                │           │
│   └────────────────────────┬────────────────────────────────┘           │
│                            │                                            │
│                            ▼                                            │
│   ┌─────────────────────────────────────────────────────────┐           │
│   │  CreateMesh                                              │           │
│   │  builder.CreateMesh(ecs)  → Mesh Entity                  │           │
│   │  IUriComponentManager->Set(entity, "sphere")             │           │
│   │  INameComponentManager->Set(entity, "sphere")            │           │
│   └────────────────────────┬────────────────────────────────┘           │
│                            │                                            │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  第三层：ECS实体化                                                       │
│                                                                         │
│   GenerateEntity(ecs, "sphere", meshHandle)                             │
│   │                                                                     │
│   │  Mesh Entity ──包装──▶ Renderable Node Entity                       │
│   │                                                                     │
│   │  ┌──────────────────────────────┐                                   │
│   │  │  Node Entity 组件构成         │                                   │
│   │  │  ├─ NodeComponent            │  场景图节点（变换、层级）            │
│   │  │  ├─ RenderMeshComponent      │  渲染引用（指向Mesh + Material）    │
│   │  │  └─ ...                      │                                   │
│   │  └──────────────────────────────┘                                   │
│   │                                                                     │
│   └────────────────────────────────────────────▶ 返回 Node Entity       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
