# UpdateMaterialData 与 AddFrameMaterialData 的区别

## 背景

`RenderDataStoreDefaultMaterial` 是 Lume3D 渲染管线中的核心材质数据存储，管理所有材质的 uniform 数据、GPU 资源句柄和渲染标志。它采用两级材质数据模型：**持久材质数据**通过 `UpdateMaterialData` 维护，在材质生命周期内跨帧存在，支持材质缓存与复用；**帧材质实例**通过 `AddFrameMaterialData` 维护，仅在单帧渲染期间有效，用于支持 GPU Instancing 和渲染排序。这一区分的必要性在于：同一材质可能被多个网格实例引用，但每帧的实例数量和渲染顺序不同，因此需要将"材质定义"与"每帧的材质引用"分离。两者的核心差异在于生命周期——持久 vs 帧临时。

---

## 1. 函数定义

### 1.1 UpdateMaterialData

**文件位置：** `submodules/Lume3D/src/render/datastore/render_data_store_default_material.cpp:918-957`

**接口声明（3 个重载，均为 public virtual）：**
`submodules/Lume3D/api/3d/render/intf_render_data_store_default_material.h:363-400`

```cpp
// 完整版本（带自定义绑定）
virtual uint32_t UpdateMaterialData(
    const uint64_t id,
    const RenderDataDefaultMaterial::InputMaterialUniforms& materialUniforms,
    const RenderDataDefaultMaterial::MaterialHandlesWithHandleReference& materialHandles,
    const RenderDataDefaultMaterial::MaterialData& materialData,
    const BASE_NS::array_view<const uint8_t> customPropertyData,
    const BASE_NS::array_view<const RENDER_NS::RenderHandleReference> customBindings) = 0;

// 简化版本（无自定义绑定）
virtual uint32_t UpdateMaterialData(
    const uint64_t id, ..., const array_view<const uint8_t> customPropertyData) = 0;

// 最简版本（无自定义数据）
virtual uint32_t UpdateMaterialData(
    const uint64_t id, ..., const MaterialData& materialData) = 0;
```

**核心逻辑**（`render_data_store_default_material.cpp:918-941`）：

```cpp
uint32_t RenderDataStoreDefaultMaterial::UpdateMaterialData(
    const uint64_t id, const InputMaterialUniforms& materialUniforms,
    const MaterialHandlesWithHandleReference& materialHandles,
    const MaterialData& materialData, const array_view<const uint8_t> customData,
    const array_view<const RenderHandleReference> customBindings)
{
    PLUGIN_ASSERT(matData_.allUniforms.size() == matData_.data.size());
    if (const auto iter = matData_.materialIdToIndex.find(id);
        iter != matData_.materialIdToIndex.cend()) {
        // 材质已存在：原地更新，返回已有索引
        PLUGIN_ASSERT(iter->second < matData_.allUniforms.size());
        const uint32_t materialIndex = AddMaterialDataImpl(
            iter->second, materialUniforms, materialHandles, materialData, customData, customBindings);
        PLUGIN_ASSERT(materialIndex == iter->second);
        return iter->second;
    } else {
        // 材质不存在：创建新材质，写入哈希表
        const uint32_t materialIndex =
            AddMaterialDataImpl(~0U, materialUniforms, materialHandles, materialData, customData, customBindings);
        matData_.materialIdToIndex.insert_or_assign(id, materialIndex);
        return materialIndex;
    }
}
```

---

### 1.2 AddFrameMaterialData

**接口声明（1 个重载，public virtual）：**
`submodules/Lume3D/api/3d/render/intf_render_data_store_default_material.h:425-430`

```cpp
// 接口唯一重载：无 ID 的帧临时材质（标记为 DEPRECATED，建议优先使用 id 方式）
virtual RenderFrameMaterialIndices AddFrameMaterialData(
    const RenderDataDefaultMaterial::InputMaterialUniforms& materialUniforms,
    const RenderDataDefaultMaterial::MaterialHandlesWithHandleReference& materialHandles,
    const RenderDataDefaultMaterial::MaterialData& materialData,
    const BASE_NS::array_view<const uint8_t> customPropertyData,
    const BASE_NS::array_view<const RENDER_NS::RenderHandleReference> customBindings) = 0;
```

**实现类额外重载（非虚，内部使用）：**
`render_data_store_default_material.h:141`

```cpp
// 按已有材质索引 + 实例数量添加帧引用（非接口方法）
RenderFrameMaterialIndices AddFrameMaterialData(uint32_t index, uint32_t instanceCount);
```

**核心逻辑**（`render_data_store_default_material.cpp:959-1009`）：

```cpp
// 重载1：按索引 + 实例数（:959-986）
RenderFrameMaterialIndices RenderDataStoreDefaultMaterial::AddFrameMaterialData(
    const uint32_t index, const uint32_t instanceCount)
{
    if (index >= matData_.data.size()) {
        // 索引无效：返回空结果并记录验证警告
        return {};
    }
    // 单实例快速路径：直接复用已有帧索引
    if ((instanceCount == 1U) && (index < matData_.frameIndices.size())
        && (matData_.frameIndices[index] == index)) {
        UpdateFrameMaterialResourceReferences(index);
        return { index, index };
    } else {
        // 多实例或首次添加：追加到 frameIndices
        const uint32_t frameMaterialOffset = static_cast<uint32_t>(matData_.frameIndices.size());
        matData_.frameIndices.append(instanceCount, index);
        UpdateFrameMaterialResourceReferences(index);
        return { index, frameMaterialOffset };
    }
}

// 重载2：无 ID 帧临时材质（:988-1009，DEPRECATED 兼容支持）
RenderFrameMaterialIndices RenderDataStoreDefaultMaterial::AddFrameMaterialData(
    const InputMaterialUniforms& materialUniforms, ...)
{
    // 不经过 materialIdToIndex，直接创建无 ID 材质
    const uint32_t materialIndex = AddMaterialDataImpl(~0U, ...);
    matData_.data[materialIndex].noId = true; // 标记为帧结束后自动销毁
    const uint32_t materialOffset = static_cast<uint32_t>(matData_.frameIndices.size());
    matData_.frameIndices.push_back(materialIndex);
    return { materialIndex, materialOffset };
}
```

---

## 2. 核心区别对比

| 方面 | UpdateMaterialData | AddFrameMaterialData |
|------|-------------------|---------------------|
| **函数类型** | public virtual（3 个重载） | public virtual（1 个重载）+ 内部非虚重载 |
| **返回类型** | `uint32_t`（材质索引） | `RenderFrameMaterialIndices { index, frameOffset }` |
| **关键输入** | `uint64_t id`（材质实体 ID） | `uint32_t index`（已有材质索引）或完整材质数据 |
| **数据持久性** | 持久（存入 `materialIdToIndex` 哈希表） | 帧临时（存入 `frameIndices` 数组，帧结束清空） |
| **生命周期** | 材质整个生命周期 | 单帧 |
| **抽象级别** | 材质定义级别 | 帧材质引用级别 |
| **调用频率** | 低（材质创建/更新时） | 高（每帧每个可见网格实例） |
| **查询方式** | 哈希查找 O(1) | 数组索引直接访问 O(1) |
| **验证机制** | `PLUGIN_ASSERT` 断言 | 索引范围检查 + `CORE3D_VALIDATION_ENABLED` 日志 |
| **内存管理** | 哈希表动态插入 | `frameIndices.append` 批量追加 |

---

## 3. 协作关系与数据流

### 3.1 渲染管线中的协作流程

```
MaterialComponent 更新
        │
        ▼
  UpdateMaterialData(id, ...)        ← 材质定义阶段（低频）
        │
        ├─ 查找 materialIdToIndex 哈希表
        │   ├─ 命中 → 原地更新 allUniforms[index]
        │   └─ 未命中 → AddMaterialDataImpl → 写入哈希表
        │
        ▼
  返回 materialIndex（持久索引）
        │
        ═══════════════════════════════════════
        │         帧边界（每帧重复）          │
        ═══════════════════════════════════════
        │
        ▼
  RenderSystem 遍历可见 Submesh
        │
        ▼
  AddFrameMaterialData(index, instanceCount)   ← 帧引用阶段（高频）
        │
        ├─ 单实例快速路径 → frameIndices[index] 复用
        └─ 多实例/首次   → frameIndices.append(instanceCount, index)
        │
        ▼
  frameIndices 数组 → 排序/分组 → GPU Draw Call
```

### 3.2 典型调用代码

```cpp
// 1. 材质定义：RenderSystem 更新材质（render_system.cpp）
uint32_t materialIndex = dsMaterial_->UpdateMaterialData(
    matEntity.id, materialUniforms, materialHandles, matData, customData, customBindings);

// 2. 帧引用：RenderSystem 每帧添加可见网格的材质实例
RenderFrameMaterialIndices rfmi = dsMaterial_->AddFrameMaterialData(materialIndex, instanceCount);

// 3. 渲染：使用 frameOffset 定位 uniform 数据
cmdList.BindDescriptorSet(0, fgds.set0);
cmdList.DrawInstanced(..., instanceCount);
```

---

## 4. 数据结构

### 4.1 MaterialData

```cpp
struct MaterialData {
    MaterialShaderWithHandleReference materialShader;
    MaterialShaderWithHandleReference depthShader;
    RenderExtraRenderingFlags extraMaterialRenderingFlags { 0u };
    RenderMaterialFlags renderMaterialFlags { RENDER_MATERIAL_SHADOW_RECEIVER_BIT |
                                                  RENDER_MATERIAL_SHADOW_CASTER_BIT |
                                                  RENDER_MATERIAL_PUNCTUAL_LIGHT_RECEIVER_BIT |
                                                  RENDER_MATERIAL_INDIRECT_LIGHT_RECEIVER_BIT |
                                                  RENDER_MATERIAL_INDIRECT_IRRADIANCE_LIGHT_RECEIVER_BIT };
    RenderMaterialType materialType { RenderMaterialType::METALLIC_ROUGHNESS };
    uint32_t customRenderSlotId { ~0u };
};
```

### 4.2 RenderFrameMaterialIndices

定义于 `render_data_defines_3d.h:173`：

```cpp
struct RenderFrameMaterialIndices {
    uint32_t index { RenderSceneDataConstants::INVALID_INDEX };        // 材质数据索引
    uint32_t frameOffset { RenderSceneDataConstants::INVALID_INDEX };  // 帧材质偏移量（支持 Instancing 去重）
};
```

---

## 5. 性能特征

### UpdateMaterialData

- **哈希查找** O(1) 平均，通过 `materialIdToIndex` 快速定位已有材质
- **材质复用**：已有材质原地更新，不重复创建
- **内存**：O(n) 哈希表 + uniform 存储，n 为材质总数
- **建议**：避免每帧不必要的 UpdateMaterialData 调用，仅在材质数据实际变化时调用

### AddFrameMaterialData

- **单实例快速路径**：`frameIndices[index] == index` 时直接返回，零额外开销
- **批量追加**：`frameIndices.append(instanceCount, index)` 一次性添加多个实例
- **内存**：O(m) frameIndices 数组，m 为每帧可见实例总数
- **建议**：合理预分配 frameIndices 容量以减少每帧 realloc

---

## 6. 使用场景与最佳实践

| 场景 | 使用哪个 | 说明 |
|------|---------|------|
| 材质首次创建 | UpdateMaterialData | 通过 id 创建，写入哈希表 |
| 材质属性修改 | UpdateMaterialData | 通过 id 查找并原地更新 |
| 每帧可见网格收集 | AddFrameMaterialData | 将 materialIndex 加入 frameIndices |
| GPU Instancing | AddFrameMaterialData | 传入 instanceCount > 1 |
| 无 ID 调试网格 | AddFrameMaterialData（接口重载） | 帧结束自动销毁（DEPRECATED） |

**关键原则**：
1. 先调用 `UpdateMaterialData` 获取/更新 `materialIndex`，再每帧调用 `AddFrameMaterialData` 引用该索引
2. `UpdateMaterialData` 不应在每帧对未变化的材质重复调用
3. `AddFrameMaterialData(index, instanceCount)` 是渲染热路径，单实例走快速路径几乎零开销

---

## 7. 调试验证要点

**UpdateMaterialData**：`PLUGIN_ASSERT(matData_.allUniforms.size() == matData_.data.size())` 确保数据一致性；`PLUGIN_ASSERT(materialIndex == iter->second)` 确保原地更新后索引不变。

**AddFrameMaterialData**：当 `index >= matData_.data.size()` 时，在 `CORE3D_VALIDATION_ENABLED` 模式下输出 `"AddFrameMaterialData index of material (idx=%u) not updated prior add"` 警告——表明在调用 AddFrameMaterialData 之前未先调用 UpdateMaterialData。

---

## 8. 参考代码

| 文件 | 说明 |
|------|------|
| `submodules/Lume3D/src/render/datastore/render_data_store_default_material.cpp:918-957` | UpdateMaterialData 实现 |
| `submodules/Lume3D/src/render/datastore/render_data_store_default_material.cpp:959-1009` | AddFrameMaterialData 实现 |
| `submodules/Lume3D/api/3d/render/intf_render_data_store_default_material.h:363-430` | 接口声明 |
| `submodules/Lume3D/api/3d/render/render_data_defines_3d.h:173` | RenderFrameMaterialIndices 定义 |
| `submodules/Lume3D/src/render/datastore/render_data_store_default_material.h:133-141` | 实现类声明（含非虚重载） |
| `submodules/Lume3D/src/ecs/systems/render_system.cpp` | 典型调用方 |
