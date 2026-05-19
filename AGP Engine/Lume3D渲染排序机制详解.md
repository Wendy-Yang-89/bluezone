# Lume3D 渲染排序机制详解

## 概述

Lume3D 渲染系统通过多级排序机制控制物体的渲染顺序，包括 `renderSortLayer`、`renderSortLayerOrder` 和 `sortType` 三层排序参数。本文档详细分析这些参数的定义、作用和排序算法实现。

---

## 一、排序层级定义

### 1.1 数据结构定义

**文件位置：** `api/3d/ecs/components/material_component.h:222-234`

```cpp
struct RenderSort {
    /**
     * Render sort layer. Within a render slot a layer can define a sort layer order.
     * There are 0-63 values available. Default id value is 32.
     * 0 first, 63 last
     * 
     * Typical use cases:
     * 1. Set render sort layer to objects which render with depth test without depth write.
     * 2. Always render character and/or camera object first to cull large parts of view.
     * 3. Sort e.g. plane layers.
     */
    uint8_t renderSortLayer { DEFAULT_RENDER_SORT_LAYER_ID };
    
    /**
     * Sort layer order to describe fine order within sort layer.
     * Valid order 0 - 255
     */
    uint8_t renderSortLayerOrder { 0u };
};
```

**同时在 MeshComponent::Submesh 中定义：**

```cpp
struct Submesh {
    uint8_t renderSortLayer { DEFAULT_RENDER_SORT_LAYER_ID };
    uint8_t renderSortLayerOrder { 0u };
};
```

---

### 1.2 参数详解

| 参数 | 类型 | 范围 | 默认值 | 排序规则 | 作用 |
|------|------|------|--------|----------|------|
| **renderSortLayer** | `uint8_t` | 0-63 | 32 | 0最先，63最后 | 粗粒度层级排序，将物体分组到不同渲染批次 |
| **renderSortLayerOrder** | `uint8_t` | 0-255 | 0 | 0最先，255最后 | 细粒度层级内排序，控制同一层级内的渲染顺序 |

---

## 二、排序类型定义

### 2.1 RenderSlotSortType

**文件位置：** `api/3d/render/intf_render_data_store_default_material.h`

```cpp
enum RenderSlotSortType : uint8_t {
    BY_MATERIAL = 0,      // 按材质排序（优先减少状态切换）
    FRONT_TO_BACK = 1,    // 从后往前（深度大先渲染）
    BACK_TO_FRONT = 2,    // 从前往后（深度小先渲染）
};
```

---

## 三、排序优先级体系

渲染系统的多级排序优先级：

```
1. RenderSlot（渲染槽） - 最高优先级，决定渲染管线
   ↓
2. sortType（排序类型） - 决定排序算法
   ↓
3. renderSortLayer（粗粒度层级） - 中等优先级
   ↓
4. renderSortLayerOrder（细粒度层级） - 低优先级
   ↓
5. Material/Shader Hash（材质哈希）或 Depth（深度）
```

---

## 四、排序算法实现

### 4.1 renderSortHash 计算

**文件位置：** `src/render/datastore/render_data_store_default_material.cpp:197-208`

```cpp
inline constexpr uint16_t GetRenderSortLayerHash(const RenderSubmesh& submesh)
{
    // 如果 submesh 的层级是默认值，则使用 material 的排序值
    if ((submesh.layers.meshRenderSortLayer == RenderSceneDataConstants::DEFAULT_RENDER_SORT_LAYER_ID) &&
        (submesh.layers.meshRenderSortLayerOrder == 0)) {
        // 使用 Material 的排序值
        return (static_cast<uint16_t>(submesh.layers.materialRenderSortLayer) << 8u) |
               (static_cast<uint16_t>(submesh.layers.materialRenderSortLayerOrder) & 0xffu);
    } else {
        // 使用 Submesh 的排序值（覆盖 Material 的值）
        return (static_cast<uint16_t>(submesh.layers.meshRenderSortLayer) << 8u) |
               (static_cast<uint16_t>(submesh.layers.meshRenderSortLayerOrder) & 0xffu);
    }
}
```

**Hash计算公式：**
```
renderSortHash = (renderSortLayer << 8) | (renderSortLayerOrder & 0xFF)
```

**示例：**
- renderSortLayer = 10, renderSortLayerOrder = 5 → Hash = 2565
- renderSortLayer = 20, renderSortLayerOrder = 3 → Hash = 5123

---

### 4.2 Submesh vs Material 优先级

```
优先级规则：
1. Submesh 的排序值优先于 Material 的排序值
   - 如果 submesh.renderSortLayer != 32（默认值）
   - 则使用 submesh 的排序值

2. 否则使用 Material 的排序值
   - 如果 submesh 使用默认值
   - 则继承 material 的排序值
```

---

### 4.3 sortKey 计算（64位）

**文件位置：** `src/render/render_node_scene_util.cpp:370-376`

```cpp
// 计算基础 sortKey（深度）
const float zVal = Math::abs(pos.z);
uint64_t sortKey = Math::min(maxUDepth, static_cast<uint64_t>(double(zVal) * camSortCoefficient));

if (renderSlotInfo.sortType == RenderSlotSortType::BY_MATERIAL) {
    // High 32bits for render sort hash, Low 32bits for depth
    sortKey |= (((uint64_t)submeshMatData.renderSortHash & sRenderMask) << sRenderShift);
} else {
    // High 32bits for depth, Low 32bits for render sort hash
    sortKey = (sortKey << sDepthShift) | ((uint64_t)slotSubmeshMatData[idx].renderSortHash & sRenderMask);
}
```

**常量定义：**
```cpp
constexpr uint64_t sDepthShift = 32U;   // 深度位移量
constexpr uint64_t sRenderShift = 32U;  // 渲染哈希位移量
```

---

## 五、排序比较运算符

**文件位置：** `src/render/render_node_scene_util.cpp:50-72`

```cpp
inline bool operator<(const SlotSubmeshIndex& lhs, const SlotSubmeshIndex& rhs)
{
    // Sorting is always ascending by sortLayerKey. For equal sortLayerKeys sortKey defines the order.
    if (lhs.sortLayerKey < rhs.sortLayerKey) {
        return true;
    } else if (lhs.sortLayerKey == rhs.sortLayerKey) {
        return (lhs.sortKey < rhs.sortKey);
    }
    return false;
}

inline bool operator>(const SlotSubmeshIndex& lhs, const SlotSubmeshIndex& rhs)
{
    // Sorting is always ascending by sortLayerKey. For equal sortLayerKeys sortKey defines the order.
    if (lhs.sortLayerKey < rhs.sortLayerKey) {
        return true;
    } else if (lhs.sortLayerKey == rhs.sortLayerKey) {
        return (lhs.sortKey > rhs.sortKey);  // sortKey 降序
    }
    return false;
}
```

**关键点：**
- `operator<`: sortLayerKey 升序 + sortKey 升序
- `operator>`: sortLayerKey 升序 + sortKey 降序
- sortLayerKey 总是升序（值越小越靠前）

---

## 六、不同 sortType 的排序规则详解

### 6.1 BY_MATERIAL 模式

**排序函数调用：**
```cpp
// render_node_scene_util.cpp:390
std::sort(refSubmeshIndices.begin(), refSubmeshIndices.end(), Less<SlotSubmeshIndex>());
```

**sortKey 位分布：**
```
[63 ... 32][31 ... 0]
 渲染排序Hash   深度值
```

**排序规则（使用 operator< 升序）：**

| 参数 | 排序方向 | 说明 |
|------|----------|------|
| **renderSortLayer** | 值越小越靠前 | 0最先渲染，63最后 |
| **renderSortLayerOrder** | 值越小越靠前 | 0最先渲染，255最后 |
| **depth（深度）** | 值越小越靠前（近→远） | 相同材质内从近到远渲染 |

**排序流程：**
```
1. 先按 sortLayerKey 升序（renderSortLayer 小到大）
2. 再按 sortKey 升序
   - sortKey 高32位 = renderSortHash（小到大）
   - sortKey 低32位 = depth（小到大）
3. 按材质分组，每组内找最小深度
4. 最终按 sortLayerKey + minDepth 升序排列
```

**适用场景：**
- 不透明物体渲染
- 减少状态切换（材质分组）
- 减少 overdraw（近→远渲染，深度测试剔除）

---

### 6.2 FRONT_TO_BACK 模式

**排序函数调用：**
```cpp
// render_node_scene_util.cpp:446-448
// front-to-back render layer sort is 0 -> 63
std::sort(refSubmeshIndices.begin(), refSubmeshIndices.end(), Less<SlotSubmeshIndex>());
```

**sortKey 位分布：**
```
[63 ... 32][31 ... 0]
   深度值      渲染排序Hash
```

**排序规则（使用 operator< 升序）：**

| 参数 | 排序方向 | 说明 |
|------|----------|------|
| **renderSortLayer** | 值越小越靠前 | 0最先渲染，63最后 |
| **renderSortLayerOrder** | 值越小越靠前 | 0最先渲染，255最后 |
| **depth（深度）** | 值越小越靠前（近→远） | 从前景到背景渲染 |

**渲染顺序图示：**
```
相机位置
    ↓
    ├─ depth=0（最近） → 最先渲染
    ├─ depth=5
    ├─ depth=10
    └─ depth=20（最远） → 最后渲染
    
方向：近 → 远（FRONT_TO_BACK）
```

**适用场景：**
- 透明物体渲染（从近到远）
- OIT 算法兼容
- 正确的深度顺序

---

### 6.3 BACK_TO_FRONT 模式

**排序函数调用：**
```cpp
// render_node_scene_util.cpp:449-451
// back-to-front render layer sort is 63 -> 0
std::sort(refSubmeshIndices.begin(), refSubmeshIndices.end(), Greater<SlotSubmeshIndex>());
```

**sortKey 位分布：**
```
[63 ... 32][31 ... 0]
   深度值      渲染排序Hash
```

**排序规则（使用 operator> 降序）：**

| 参数 | 排序方向 | 说明 |
|------|----------|------|
| **renderSortLayer** | 值越小越靠前 | 仍为升序（0最先） |
| **renderSortLayerOrder** | 值越小越靠前 | 仍为升序（0最先） |
| **depth（深度）** | 值越大越靠前（远→近） | 从背景到前景渲染 |

**渲染顺序图示：**
```
相机位置
    ↓
    ├─ depth=20（最远） → 最先渲染
    ├─ depth=10
    ├─ depth=5
    └─ depth=0（最近） → 最后渲染
    
方向：远 → 近（BACK_TO_FRONT）
```

**适用场景：**
- 透明物体渲染（从远到近）
- 标准透明混合顺序
- 确保后渲染的透明物体正确覆盖

---

### 6.4 排序规则总结表

| sortType | renderSortLayer | renderSortLayerOrder | depth | 渲染方向 |
|-----------|-----------------|----------------------|-------|----------|
| **BY_MATERIAL** | 小→大（升序） | 小→大（升序） | 小→大（近→远） | 材质优先，减少状态切换 |
| **FRONT_TO_BACK** | 小→大（升序） | 小→大（升序） | 小→大（近→远） | 从前景到背景 |
| **BACK_TO_FRONT** | 小→大（升序） | 小→大（升序） | 大→小（远→近） | 从背景到前景 |

**关键结论：**
- `renderSortLayer` 和 `renderSortLayerOrder` 在所有模式下都是**值越小越靠前渲染**
- `depth` 的排序方向由 `sortType` 决定：
  - BY_MATERIAL / FRONT_TO_BACK: **值越小越靠前**（近→远）
  - BACK_TO_FRONT: **值越大越靠前**（远→近）

---

## 七、使用场景

### 7.1 深度测试但不写入深度的对象

```cpp
// 透明效果、粒子系统
materialHandle->renderSort.renderSortLayer = 10;
materialHandle->renderSort.renderSortLayerOrder = 0;
```

---

### 7.2 角色/相机对象优先渲染

```cpp
// 优先渲染用于视锥剔除优化
characterMaterial->renderSort.renderSortLayer = 0;
characterMaterial->renderSort.renderSortLayerOrder = 0;
```

---

### 7.3 平面层级排序

```cpp
// 背景平面
backgroundMaterial->renderSort.renderSortLayer = 5;
// 中景平面
midgroundMaterial->renderSort.renderSortLayer = 10;
// 前景平面
foregroundMaterial->renderSort.renderSortLayer = 15;
```

---

### 7.4 Submesh 覆盖 Material 排序

```cpp
// Material 设置默认排序
materialHandle->renderSort.renderSortLayer = 32;

// Submesh 设置自定义排序（会覆盖 Material 的值）
submesh.renderSortLayer = 15;
submesh.renderSortLayerOrder = 3;
```

---

## 八、推荐的层级分配

| 层级范围 | 用途 | 示例 |
|----------|------|------|
| 0-9 | 优先渲染对象 | 角色、相机、重要UI |
| 10-19 | 背景层 | 天空盒、远距离地形 |
| 20-29 | 中景层 | 主要场景物体 |
| 30-39 | 默认层 | 普通物体（默认值32） |
| 40-49 | 前景层 | 近距离物体、装饰 |
| 50-59 | 特殊效果层 | 粒子系统、后处理 |
| 60-63 | 最后渲染层 | 覆盖层、调试信息 |

---

## 九、性能优化建议

### 9.1 BY_MATERIAL 模式优化

1. **减少状态切换**
   - 相同材质物体连续渲染
   - 避免频繁切换 shader、材质参数

2. **减少 overdraw**
   - 相同材质内按深度排序
   - 深度测试剔除被遮挡物体

3. **提高缓存命中率**
   - 材质数据局部性好
   - 纹理缓存更有效

---

### 9.2 FRONT_TO_BACK 模式优化

1. **正确的透明混合**
   - 深度大的物体先渲染
   - 正确的深度顺序

2. **材质分组**
   - 相同深度内按材质分组
   - 减少状态切换

---

### 9.3 视锥剔除优化

```cpp
// 优先渲染可能遮挡大面积的对象
largeObject->renderSort.renderSortLayer = 0;
```

---

## 十、常见问题

### Q1：为什么默认值是32？

**A：** 32是中间值，允许在前后插入其他层级，提供灵活性。

---

### Q2：Submesh 和 Material 的排序值如何交互？

**A：** Submesh 排序值优先，只有 Submesh 使用默认值(32, 0)时才使用 Material 的值。

---

### Q3：renderSortLayerOrder 范围为何是0-255？

**A：** 8位无符号整数，在排序Hash中占用低8位，提供足够精细度。

---

## 十一、调试验证

### 11.1 检查 sortKey

```cpp
CORE_LOG_D("sortKey: 0x%016llX, depth: %f, renderHash: 0x%08X", 
    sortKey, zVal, submeshMatData.renderSortHash);
```

---

### 11.2 验证位分布

```cpp
uint32_t high32 = (sortKey >> 32) & 0xFFFFFFFF;
uint32_t low32 = sortKey & 0xFFFFFFFF;

if (sortType == BY_MATERIAL) {
    CORE_LOG_D("High32(renderHash): 0x%08X, Low32(depth): 0x%08X", high32, low32);
} else {
    CORE_LOG_D("High32(depth): 0x%08X, Low32(renderHash): 0x%08X", high32, low32);
}
```

---

## 十二、版本历史

| 版本 | 日期 | 描述 |
|------|------|------|
| 1.0 | 2025-05-19 | 合并 renderSortLayer、renderSortLayerOrder 和 sortType 文档 |

---

## 十三、参考资料

| 文件 | 描述 |
|------|------|
| `api/3d/ecs/components/material_component.h` | RenderSort 定义 |
| `api/3d/ecs/components/mesh_component.h` | Submesh 排序定义 |
| `api/3d/render/intf_render_data_store_default_material.h` | RenderSlotSortType 定义 |
| `src/render/datastore/render_data_store_default_material.cpp` | renderSortHash 计算 |
| `src/render/render_node_scene_util.cpp` | sortKey 计算 |
| `samples/multiplatform/oit/src/oit.cpp` | OIT 排序示例 |