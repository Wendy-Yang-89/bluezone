# OIT（Order Independent Transparency）配置位置分析

## 概述

本文档详细分析了在 Lume3D 模块中新增 OIT（Order Independent Transparency）相关配置的最佳位置，包括配置类型（OIT 算法类型）和启用标志（是否使用 OIT）。

---

## 1. 现有配置架构探索

### 1.1 主要配置组件

Lume3D 模块中有以下主要配置组件：

| 组件 | 文件位置 | 作用 | 级别 |
|--------|-----------|------|------|
| **CameraComponent** | `api/3d/ecs/components/camera_component.h` | 相机渲染配置 | 相机级别 |
| **MaterialComponent** | `api/3d/ecs/components/material_component.h` | 材质属性配置 | 材质级别 |
| **RenderConfigurationComponent** | `api/3d/ecs/components/render_configuration_component.h` | 场景渲染配置 | 场景级别 |
| **PostProcessConfiguration** | `api/render/datastore/render_data_store_render_pods.h` | 后处理配置 | 后处理级别 |

### 1.2 CameraComponent 分析

**文件位置：** `api/3d/ecs/components/camera_component.h:63-102`

```cpp
enum PipelineFlagBits : uint32_t {
    CLEAR_DEPTH_BIT = (1 << 0),
    CLEAR_COLOR_BIT = (1 << 1),
    MSAA_BIT = (1 << 2),              // MSAA 配置
    ALLOW_COLOR_PRE_PASS_BIT = (1 << 3),
    FORCE_COLOR_PRE_PASS_BIT = (1 << 4),
    HISTORY_BIT = (1 << 5),
    JITTER_BIT = (1 << 6),
    VELOCITY_OUTPUT_BIT = (1 << 7),
    DEPTH_OUTPUT_BIT = (1 << 8),
    // ... 更多标志
};

enum class RenderingPipeline : uint8_t {
    LIGHT_FORWARD = 0,
    FORWARD = 1,
    DEFERRED = 2,
    CUSTOM = 3,
};
```

**特点：**
- ✅ 已有 `PipelineFlagBits` 枚举，包含 MSAA_BIT、CLEAR_DEPTH_BIT 等渲染相关标志
- ✅ 已有 `RenderingPipeline` 枚举（LIGHT_FORWARD、FORWARD、DEFERRED、CUSTOM）
- 这些是**相机级别**的渲染配置

### 1.3 MaterialComponent 分析

**文件位置：** `api/3d/ecs/components/material_component.h:253-365`

```cpp
enum LightingFlagBits : uint32_t {
    SHADOW_RECEIVER_BIT = (1 << 0),
    SHADOW_CASTER_BIT = (1 << 1),
    PUNCTUAL_LIGHT_RECEIVER_BIT = (1 << 2),
    INDIRECT_LIGHT_RECEIVER_BIT = (1 << 3),
    INDIRECT_IRRADIANCE_LIGHT_RECEIVER_BIT = (1 << 4),
};

// 材质纹理和参数
DEFINE_PROPERTY(Type, type, "Material Type", 0, VALUE(Type::METALLIC_ROUGHNESS))
DEFINE_PROPERTY(float, alphaCutoff, "Alpha Cutoff", 0, VALUE(1.0f))
```

**特点：**
- ✅ 包含材质纹理、材质参数（baseColor、normal、material、emissive 等）
- ✅ 包含 `LightingFlagBits`（SHADOW_RECEIVER_BIT、PUNCTUAL_LIGHT_RECEIVER_BIT 等）
- 这些是**材质级别**的配置

### 1.4 RenderConfigurationComponent 分析

**文件位置：** `api/3d/ecs/components/render_configuration_component.h`

```cpp
enum SceneShadowType : uint8_t {
    PCF = 0,
    VSM = 1,
};

enum SceneShadowQuality : uint8_t {
    LOW = 0,
    NORMAL = 1,
    HIGH = 2,
    ULTRA = 3,
};

enum SceneOITType : uint8_t {
    PPLL = 0,  // Per-Pixel Linked List
    WBOIT = 1, // Weighted Blended OIT
    AT = 2,    // Adaptive Transparency
};

enum SceneRenderingFlagBits : uint8_t {
    CREATE_RNGS_BIT = (1 << 0),
};
```

**特点：**
- ✅ 场景级别的渲染配置
- ✅ 已有 `SceneOITType` 枚举（PPLL、WBOIT、AT）
- ✅ 已有阴影类型和质量配置
- ✅ 影响整个场景的渲染方式

### 1.5 PostProcessConfiguration 分析（不适用）

**文件位置：** `api/render/datastore/render_data_store_render_pods.h:398-489`

```cpp
enum PostProcessEnableFlagBits : uint32_t {
    ENABLE_TONEMAP_BIT = (1 << 0),
    ENABLE_VIGNETTE_BIT = (1 << 1),
    ENABLE_DITHER_BIT = (1 << 2),
    ENABLE_BLOOM_BIT = (1 << 9),
    ENABLE_FXAA_BIT = (1 << 10),
    ENABLE_TAA_BIT = (1 << 11),
    ENABLE_DOF_BIT = (1 << 12),
    // ... 更多后处理标志
};
```

**特点：**
- ✅ 已有 `PostProcessEnableFlagBits` 枚举
- ✅ 这些是**后处理**配置（tonemap、bloom、TAA、DOF 等）
- ❌ OIT 不是后处理技术

---

## 2. OIT 示例代码分析

### 2.1 OIT 示例实现

**文件位置：** `samples/multiplatform/oit/src/oit.cpp`

```cpp
// OIT 示例使用自定义 render node graph
renderNodeGraph_ = CreateRenderNodeGraph("assets://app/renderNodeGraph.json");

// 注册自定义 OIT render node
static constexpr RenderNodeTypeInfo gRenderNodes[] = {
    Fill<RenderNodeTypeInfo, OIT_NS::RenderNodeOIT>()
};

for (const auto& info: gRenderNodes) {
    GetPluginRegister().RegisterTypeInfo(info);
}
```

**关键点：**
- OIT 通过自定义 render node 实现
- 使用 `RenderNodeDefaultMaterialRenderSlot` 进行渲染
- 使用 `RenderDataStorePod` 的 `CORE3D_POST_PROCESS_CAM` 配置

### 2.2 OIT Render Node Graph

**文件位置：** `samples/multiplatform/oit/assets/app/rendernodegraphs/baseline.rng`

```json
{
    "renderNodeGraphName": "oitSdrBaselineRng",
    "nodes": [
        {
            "typeName": "RenderNodeDefaultMaterialRenderSlot",
            "nodeName": "CORE3D_RN_CAM_DM_SO_LWRP",
            "renderDataStore": {
                "dataStoreName": "RenderDataStorePod",
                "typeName": "RenderDataStorePod",
                "configurationName": "CORE3D_POST_PROCESS_CAM"
            },
            "renderSlot": "CORE3D_RS_DM_FW_OPAQUE",
            "renderPass": {
                "attachments": [
                    {
                        "loadOp": "clear",
                        "clearDepth": [ 1.0, 0 ],
                        "name": "depth"
                    },
                    {
                        "loadOp": "dont_care",
                        "name": "output"
                    }
                ],
                "subpass": {
                    "subpassFlags": "merge_bit",
                    "depthAttachmentIndex": 0,
                    "colorAttachmentIndices": [ 1 ]
                }
            }
        }
    ]
}
```

**关键点：**
- OIT 使用 `RenderNodeDefaultMaterialRenderSlot`
- 使用 `RenderDataStorePod` 的配置
- OIT 是在渲染管线中实现的，不是后处理

---

## 3. OIT 技术特性分析

### 3.1 OIT（Order Independent Transparency）特点

**OIF 技术定义：**
- ✅ 解决透明物体的渲染顺序问题
- ✅ 允许任意顺序渲染透明物体
- ✅ 不需要从后往前排序透明物体
- ✅ 支持复杂的透明场景

### 3.2 OIT 算法类型

| 算法 | 全称 | 特点 | 复杂度 | 内存占用 |
|------|--------|------|----------|----------|
| **PPLL** | Per-Pixel Linked List | 每像素存储链表 | 高 | 中 |
| **WBOIT** | Weighted Blended OIT | 加权混合，存储深度和颜色 | 中 | 高 |
| **AT** | Adaptive Transparency | 自适应透明度压缩 | 低 | 低 |

### 3.3 OIT 的渲染特性

- ✅ **影响整个场景的渲染方式**
  - 不是单个相机或单个材质的属性
  - 改变整个透明物体的渲染管线

- ✅ **需要在渲染管线中启用**
  - 不是后处理技术
  - 在渲染过程中实现

- ✅ **需要特殊的 Render Node Graph**
  - 使用自定义 render node graph
  - 可能需要额外的 GPU 资源（OIT buffers）

- ✅ **与现有渲染系统集成**
  - 需要与现有的材质、光照系统集成
  - 需要处理深度测试、混合等

---

## 4. 配置位置适用性分析

### 4.1 选项 A：CameraComponent

**优点：**
- ✅ 已有 `PipelineFlagBits` 和 `RenderingPipeline` 枚举
- ✅ MSAA_BIT 等渲染配置在这里
- ✅ 相机级别的配置，适合控制该相机的渲染方式

**缺点：**
- ❌ OIT 通常影响整个场景，而不仅仅是单个相机
- ❌ 如果有多个相机，需要为每个相机配置 OIT
- ❌ `PipelineFlagBits` 已有 13 个标志位，可能不够用
- ❌ OIT 不是相机的固有属性（如 FOV、投影类型）

**结论：** ❌ **不推荐**

---

### 4.2 选项 B：MaterialComponent

**优点：**
- ✅ 已有 `LightingFlagBits` 枚举
- ✅ 材质级别的配置

**缺点：**
- ❌ OIT 不是材质属性，而是渲染技术
- ❌ OIT 影响所有透明物体，而不是特定材质
- ❌ 不符合 MaterialComponentComponent 的设计意图
- ❌ 材质应该只描述表面的光学属性（颜色、粗糙度、金属度等）

**结论：** ❌ **不推荐**

---

### 4.3 选项 C：RenderConfigurationComponent

**优点：**
- ✅ 场景级别的渲染配置
- ✅ 影响整个场景的渲染方式
- ✅ 适合配置全局渲染技术
- ✅ 与 OIT 的全局特性匹配
- ✅ 已有 `SceneOITType` 枚举（PPLL、WBOIT、AT）
- ✅ 已有类似的场景配置（阴影类型、阴影质量）

**缺点：**
- 需要添加一个新的标志位来启用/禁用 OIT

**结论：** ✅ **强烈推荐**

---

### 4.4 选项 D：PostProcessConfiguration

**优点：**
- ✅ 已有 `PostProcessEnableFlagBits` 枚举
- ✅ 可以添加新的后处理标志

**缺点：**
- ❌ OIT 不是后处理技术
- ❌ OIT 在渲染过程中实现，不是渲染后的处理
- ❌ 后处理是在所有渲染完成后应用的效果（如 tonemap、bloom）
- ❌ 放在这里会误导 OIT 的性质

**结论：** ❌ **不推荐**

---

## 5. RenderConfigurationComponent 深入分析

### 5.1 现有结构

**文件位置：** `api/3d/ecs/components/render_configuration_component.h`

```cpp
enum SceneOITType : uint8_t {
    /* Per-Pixel Linked List. Blending transparent objects though order sorted by stored Linked lists. */
    PPLL = 0,
    /* Weighted Blended Order Independent Transprency. Blending transparent objects with tailored weight function. */
    WBOIT = 1,
    /* Adaptive Transparency. Blending transparent objects with compresses visibility function. */
    AT = 2,
};

enum SceneRenderingFlagBits : uint8_t {
    /* Create render node graphs automatically in RenderSystem. */
    CREATE_RNGS_BIT = (1 << 0),
};
```

**关键发现：**
- ✅ `SceneOITType` 枚举已经存在！
- ✅ 包含三种 OIT 算法：PPLL、WBOIT、AT
- ✅ 只需要添加一个启用标志

### 5.2 需要添加的内容

#### 5.2.1 在 SceneRenderingFlagBits 中添加标志

```cpp
enum SceneRenderingFlagBits : uint8_t {
    /* Create render node graphs automatically in RenderSystem. */
    CREATE_RNGS_BIT = (1 << 0),
    
    /* Enable Order Independent Transparency for the scene. */
    ENABLE_OIT_BIT = (1 << 1),  // 新增
};
```

#### 5.2.2 使用方式示例

```cpp
// 在场景实体上配置 OIT
auto renderConfigManager = GetManager<IRenderConfigurationComponentManager>(*ecs_);
auto sceneEntity = /* 获取场景实体 */;

if (auto configHandle = renderConfigManager->Write(sceneEntity); configHandle) {
    // 启用 OIT
    configHandle->renderingFlags = RenderConfigurationComponent::SceneRenderingFlagBits::ENABLE_OIT_BIT;
    
    // 设置 OIT 算法类型
    configHandle->OITType = RenderConfigurationComponent::SceneOITType::WBOIT;
    
    // 指定 OIT 渲染管线（可选）
    configHandle->customRenderNodeGraphFile = "assets://app/oit_rendernodegraph.json";
}
```

---

## 6. Render Data Store 的选择

### 6.1 可用的 Render Data Store

| Render Data Store | 作用 | 适用场景 |
|-----------------|------|----------|
| **RenderDataStoreDefaultCamera** | 相机配置 | 相机相关的渲染数据 |
| **RenderDataStoreDefaultMaterial** | 材质配置 | 材质相关的渲染数据 |
| **RenderDataStoreDefaultScene** | 场景配置 | 场景相关的渲染数据 |

### 6.2 推荐选择

**应该放在：`RenderDataStoreDefaultScene`**

**理由：**

1. **OIT 配置是场景级别的**
   - `RenderDataStoreDefaultScene` 专门用于场景配置
   - `RenderDataStoreDefaultCamera` 用于相机配置
   - `RenderDataStoreDefaultMaterial` 用于材质配置

2. **OIT 影响整个渲染管线**
   - 需要在渲染系统级别访问 OIT 配置
   - `RenderSystem` 可以通过 `IRenderDataStoreDefaultScene` 访问场景配置

3. **与现有架构一致**
   - 阴影配置（`shadowType`、`shadowQuality`）在场景配置中
   - OIT 配置应该与阴影配置在同一层级

---

## 7. 完整的数据流

```
用户设置 OIT 配置
   ↓
RenderConfigurationComponent (SceneRenderingFlagBits::ENABLE_OIT_BIT, SceneOITType::WBOIT)
   ↓
RenderDataStoreDefaultScene (存储场景配置)
   ↓
RenderSystem (读取场景配置)
   ↓
根据 OIT 标志选择渲染管线
   ↓
使用自定义 RenderNodeGraph (OIT 渲染管线)
   ↓
渲染透明物体（使用 OIT 算法）
   ↓
最终输出到屏幕
```

---

## 8. 最终建议

### 8.1 配置位置

**推荐位置：`RenderConfigurationComponent`**

**文件：** `api/3d/ecs/components/render_configuration_component.h`

### 8.2 需要添加的内容

#### 8.2.1 在 SceneRenderingFlagBits 枚举中添加

```cpp
enum SceneRenderingFlagBits : uint8_t {
    /* Create render node graphs automatically in RenderSystem. */
    CREATE_RNGS_BIT = (1 << 0),
    
    /* Enable Order Independent Transparency for the scene. */
    ENABLE_OIT_BIT = (1 << 1),
};
```

#### 8.2.2 已有的 SceneOITType 枚举（无需修改）

```cpp
enum SceneOITType : uint8_t {
    PPLL = 0,   // Per-Pixel Linked List
    WBOIT = 1,  // Weighted Blended OIT
    AT = 2,     // Adaptive Transparency
};
```

### 8.3 Render Data Store

**推荐：`RenderDataStoreDefaultScene`**

### 8.4 使用示例

```cpp
// 创建场景实体
auto sceneEntity = ecs_->GetEntityManager().Create();

// 创建 RenderConfigurationComponent
auto renderConfigManager = GetManager<IRenderConfigurationComponentManager>(*ecs_);
renderConfigManager->Create(sceneEntity);

// 配置 OIT
if (auto configHandle = renderConfigManager->Write(sceneEntity); configHandle) {
    // 启用 OIT
    configHandle->renderingFlags = 
        RenderConfigurationComponent::SceneRenderingFlagBits::ENABLE_OIT_BIT;
    
    // 设置 OIT 算法类型
    configHandle->OITType = 
        RenderConfigurationComponent::SceneOITType::WBOIT;
    
    // 指定 OIT 渲染管线（可选）
    configHandle->customRenderNodeGraphFile = 
        "assets://app/oit_rendernodegraph.json";
}

// 禁用 OIT
if (auto configHandle = renderConfigManager->Write(sceneEntity); configHandle) {
    configHandle->renderingFlags = 0;
    configHandle->OITType = RenderConfigurationComponent::SceneOITType::PPLL;
}
```

---

## 9. 优势总结

### 9.1 架构优势

| 优势 | 说明 |
|--------|------|
| ✅ **符合现有架构设计** | 与阴影配置（shadowType、shadowQuality）在同一层级 |
| ✅ **场景级别的配置** | 影响整个场景的渲染方式，符合 OIT 的特性 |
| ✅ **便于统一管理** | RenderSystem 可以统一访问和管理场景配置 |
| ✅ **支持多种 OIT 算法** | 已有 SceneOITType 枚举，支持 PPLL、WBOIT、AT |
| ✅ **易于扩展** | 可以添加 OIT 相关的配置参数（如 buffer 大小） |
| ✅ **与 OIT 示例一致** | OIT 示例使用自定义 render node graph，符合场景配置模式 |

### 9.2 避免的问题

| 避免的问题 | 说明 |
|-------------|------|
| ❌ 避免相机级别配置 | OIT 影响整个场景，不是单个相机 |
| ❌ 避免材质级别配置 | OIT 不是材质属性，而是渲染技术 |
| ❌ 避免后处理配置 | OIT 不是后处理技术，是渲染技术 |
| ❌ 避免配置分散 | 统一在场景配置中，便于管理 |

---

## 10. 实现步骤

### 10.1 修改 RenderConfigurationComponent

1. 打开文件：`api/3d/ecs/components/render_configuration_component.h`
2. 在 `SceneRenderingFlagBits` 枚举中添加 `ENABLE_OIT_BIT`
3. 确认 `SceneOITType` 枚举存在（已存在）

### 10.2 修改 RenderSystem（如果需要）

1. 打开文件：`src/ecs/systems/render_system.h`
2. 在渲染管线选择逻辑中添加 OIT 支持
3. 根据 `ENABLE_OIT_BIT` 标志选择 OIT 渲染管线

### 10.3 创建 OIT Render Node Graph（如果需要）

1. 创建文件：`assets/app/oit_rendernodegraph.json`
2. 参考 `samples/multiplatform/oit/assets/app/rendernodegraphs/baseline.rng`
3. 配置 OIT 相关的渲染节点

### 10.4 测试

1. 创建测试场景
2. 启用 OIT 配置
3. 验证 OIT 渲染正确
4. 测试不同的 OIT 算法（PPLL、WBOIT、AT）

---

## 11. 参考代码

| 文件 | 说明 |
|------|------|
| `api/3d/ecs/components/render_configuration_component.h` | RenderConfigurationComponent 定义 |
| `api/3d/render/intf_render_data_store_default_scene.h` | IRenderDataStoreDefaultScene 接口 |
| `src/ecs/systems/render_system.h` | RenderSystem 实现 |
| `samples/multiplatform/oit/src/oit.cpp` | OIT 示例实现 |
| `samples/multiplatform/oit/assets/app/rendernodegraphs/baseline.rng` | OIT Render Node Graph 示例 |

---

## 12. 总结

### 最终推荐方案

**配置位置：** `RenderConfigurationComponent`

**需要添加：**
1. 在 `SceneRenderingFlagBits` 枚举中添加 `ENABLE_OIT_BIT = (1 << 1)`
2. 使用已有的 `SceneOITType` 枚举（PPLL、WBOIT、AT）

**Render Data Store：** `RenderDataStoreDefaultScene`

**数据流：**
```
RenderConfigurationComponent → RenderDataStoreDefaultScene → RenderSystem → 渲染管线
```

**关键优势：**
- ✅ 符合现有架构设计
- ✅ 场景级别的配置，符合 OIT 的全局特性
- ✅ 与阴影配置在同一层级
- ✅ 便于在 RenderSystem 中统一管理
- ✅ 支持多种 OIT 算法
