# Shader变体继承机制详解

## 背景与问题引入

### Shader变体概念

**Shader变体（Shader Variant）** 是同一Shader的不同配置版本：

- 支持同一Shader适应不同渲染场景
- 避免为每种场景创建独立Shader文件
- 通过参数组合实现功能复用

典型变体场景：
- 不同材质类型（Opaque/Translucent）
- 不同渲染特性（AlphaTest/DoubleSided）
- 不同平台优化（Mobile/Desktop）

### 变体继承的需求

复杂渲染场景需要Shader变体的继承和组合：

| 需求 | 传统方案问题 |
|------|-------------|
| **变体共享** | 每个Shader独立配置所有变体，重复定义 |
| **功能扩展** | 新增变体需修改基础Shader配置 |
| **跨Shader组合** | 无法将变体添加到其他Shader |

继承机制允许变体从基础Shader继承或跨Shader共享，简化配置管理。

### 两种继承机制

LumeRender提供两种变体继承机制：

| 机制 | 字段 | 作用 |
|------|------|------|
| **自身继承** | `ownBaseShaderHandle` | 指向自身的基础Shader，建立内部变体树 |
| **外部添加** | `addBaseShaderHandle` | 指向外部Shader，将自身作为变体添加 |

两种机制配合使用，实现灵活的变体组合。

### 本文档解决的问题

本文档详细对比两种继承机制的定义、用途和查找优先级：

- 字段含义和数据类型
- 使用场景和功能差异
- `GetShaderHandle` 中的查找逻辑

---

## 核心概念

### BaseShaderHandle

**BaseShaderHandle** 是Shader变体的继承链接：

- 指向一个基础Shader的RenderHandle
- 用于变体查找时的回溯匹配
- 支持多级继承链

BaseShaderHandle建立变体与基础Shader的关联关系。

### ownBaseShaderHandle

**ownBaseShaderHandle** 指向Shader自身的基础版本：

```
Shader_A (基础版)
  ├── ownBaseShaderHandle → Shader_A (指向自身)
  ├── Variant_1
  └── Variant_2

Shader_B (扩展版，继承Shader_A)
  ├── ownBaseShaderHandle → Shader_A (指向外部基础)
  └── Variant_3
```

用途：
- 同一Shader家族的变体关联
- 变体查找时回溯到基础Shader

### addBaseShaderHandle

**addBaseShaderHandle** 将当前Shader作为变体添加到外部Shader：

```
Shader_C (独立Shader)
  ├── addBaseShaderHandle → Shader_A
  └── 作为Shader_A的变体被查找

查找Shader_A的变体时，会包含Shader_C
```

用途：
- 跨Shader的变体共享
- 无需修改基础Shader配置即可添加变体

### 查找优先级

`GetShaderHandle` 查找变体的顺序：

1. **直接匹配**：检查Shader自身的RenderSlot映射
2. **ownBaseShaderHandle回溯**：查找自身继承链
3. **addBaseShaderHandle扩展**：查找外部添加的变体

优先级：`ownBaseShaderHandle` > `addBaseShaderHandle`

### 变体查找流程

```
GetShaderHandle 变体查找流程:

┌──────────────────────────────────────────────────┐
│ 输入: ShaderHandle + RenderSlotId                │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 1: 直接匹配                                  │
├──────────────────────────────────────────────────┤
│ 检查Shader自身的RenderSlot映射                    │
│ if (shader.renderSlotId == targetRenderSlotId)   │
│   └─► 返回: Shader自身句柄                        │
│                                                  │
│ 未匹配则继续                                      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 2: ownBaseShaderHandle回溯                  │
├──────────────────────────────────────────────────┤
│ if (ownBaseShaderHandle有效)                     │
│   └─► GetBaseShaderMatchedSlotHandle()           │
│   └─► 查找自身继承链的RenderSlot匹配               │
│   └─► 找到匹配 → 返回: 变体句柄                    │
│                                                  │
│ 未匹配则继续                                      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 3: addBaseShaderHandle扩展                  │
├──────────────────────────────────────────────────┤
│ if (addBaseShaderHandle有效)                     │
│   └─► GetBaseShaderMatchedSlotHandle()           │
│   └─► 查找外部添加的变体RenderSlot匹配             │
│   └─► 找到匹配 → 返回: 外部变体句柄                │
│                                                  │
│ 未匹配则继续                                      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ 返回: 空句柄 (未找到匹配变体)                      │
└──────────────────────────────────────────────────┘
```

---

## 定义

### ownBaseShaderHandle
- **类型**: `RenderHandle`
- **注释**: link to own uri for all variants
- **含义**: 链接到所有变体的自己的URI
- **指向**: 指向着色器自身的基础着色器

### addBaseShaderHandle
- **类型**: `RenderHandle`
- **注释**: link to separate base shader where it will add its variant
- **含义**: 链接到单独的基础着色器，其中将添加其变体
- **指向**: 指向一个外部的基础着色器

## 功能区别

### ownBaseShaderHandle
- 用于同一着色器的不同变体之间的关联
- 表示当前着色器是某个基础着色器的变体
- 建立着色器自身的变体体系
- 通常用于着色器继承关系中的"父-子"关系

### addBaseShaderHandle
- 当前着色器作为变体添加到这个基础着色器中
- 表示当前着色器要作为变体附加到另一个基础着色器
- 支持着色器变体的组合和扩展
- 用于跨着色器的变体共享机制

## 查找优先级

在 `ShaderManager::GetShaderHandle` 函数中，查找顺序为：

```cpp
// shader_manager.cpp:1026-1045
// 1. 首先尝试 ownBaseShaderHandle
if (RenderHandleUtil::IsValid(ownBaseShaderHandle)) {
    slotHandle = GetBaseShaderMatchedSlotHandle(
        hashToShaderVariant_, clientData, ownBaseShaderHandle, renderSlotId);
}

// 2. 如果未找到，再尝试 addBaseShaderHandle
if ((!slotHandle) && (RenderHandleUtil::IsValid(addBaseShaderHandle))) {
    slotHandle = GetBaseShaderMatchedSlotHandle(
        hashToShaderVariant_, clientData, addBaseShaderHandle, renderSlotId);
}
```

**优先级**: `ownBaseShaderHandle` > `addBaseShaderHandle`

## 使用场景

### ownBaseShaderHandle 典型场景
- 着色器变体继承：基础着色器 → 特定功能变体
- 着色器特化：通用着色器 → 优化版本
- 条件编译变体：同一着色器的不同配置版本

### addBaseShaderHandle 典型场景
- 着色器模块化：功能模块作为变体添加到基础着色器
- 着色器组合：多个功能组合到一个基础着色器
- 插件式着色器系统：动态添加功能变体

## 数据结构位置

这两个字段在以下数据结构中定义：

### ComputeMappings::Data（`shader_manager.h:293-304`）
```cpp
struct ComputeMappings {
    struct Data {
        RenderHandleReference rhr;
        RenderHandle ownBaseShaderHandle; // link to own uri for all variants
        RenderHandle addBaseShaderHandle; // link to separate base shader where it will add its variant
        uint32_t renderSlotId { INVALID_SM_INDEX };
        uint32_t pipelineLayoutIndex { INVALID_SM_INDEX };
        uint32_t reflectionPipelineLayoutIndex { INVALID_SM_INDEX };
        uint32_t categoryId { INVALID_SM_INDEX };
        uint64_t frameIndex { 0 };
    };
};
```

### GraphicsMappings::Data（`shader_manager.h:309-324`）
```cpp
struct GraphicsMappings {
    struct Data {
        RenderHandleReference rhr;
        RenderHandle ownBaseShaderHandle; // link to own uri for all variants
        RenderHandle addBaseShaderHandle; // link to separate base shader where it will add its variant
        uint32_t renderSlotId { INVALID_SM_INDEX };
        uint32_t pipelineLayoutIndex { INVALID_SM_INDEX };
        uint32_t reflectionPipelineLayoutIndex { INVALID_SM_INDEX };
        uint32_t vertexInputDeclarationIndex { INVALID_SM_INDEX };
        uint32_t graphicsStateIndex { INVALID_SM_INDEX };
        // ...
    };
};
```

## 设计意图

这种双基础着色器句柄的设计支持：

1. **灵活的变体管理**: 既可以建立自己的变体体系，也可以参与其他着色器的变体体系
2. **着色器复用**: 通过 addBaseShaderHandle 可以将功能变体复用到多个基础着色器
3. **层次化着色器架构**: 支持复杂的着色器继承和组合关系
4. **查找优化**: 通过优先级机制确保最相关的变体被优先找到

## 示例说明

### 示例1: ownBaseShaderHandle
```
BasicShader (基础着色器)
    ├── ownBaseShader = "BasicShader" (自动设置为自身URI)
    └── 变体: LightingVariant
            ├── ownBaseShader = "BasicShader" (自动设置为自身URI)
            └── 变体: ShadowVariant
                    └── ownBaseShader = "BasicShader" (自动设置为自身URI)
```

### 示例2: addBaseShaderHandle
```
PostProcessBase (后处理基础着色器)
    ├── 变体: BloomEffect (通过 addBaseShaderHandle)
    └── 变体: ToneMapping (通过 addBaseShaderHandle)

BloomEffect
    └── addBaseShaderHandle = PostProcessBase

ToneMapping
    └── addBaseShaderHandle = PostProcessBase
```

## 实际Shader示例分析

### 示例3：core3d_dm_fw系列Shader（实际代码）

在Lume3D中，Forward渲染Shader使用了ownBaseShaderHandle机制：

**Shader层次结构**：
```
core3d_dm_fw.shader (基础Forward Shader，包含所有变体)
    ├── Variant: OPAQUE_FW
    │   ├── ownBaseShader = "3dshaders://shader/core3d_dm_fw.shader" (自动设置)
    │   └── renderSlot = CORE3D_RS_DM_FW_OPAQUE
    │
    ├── Variant: TRANSLUCENT_FW_LLOIT
    │   ├── ownBaseShader = "3dshaders://shader/core3d_dm_fw.shader" (自动设置)
    │   └── renderSlot = CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT
    │
    └── Variant: TRANSLUCENT_FW_WBOIT
        ├── ownBaseShader = "3dshaders://shader/core3d_dm_fw.shader" (自动设置)
        └── renderSlot = CORE3D_RS_DM_FW_TRANSLUCENT_WBOIT
```

注意：所有变体都在同一个 `core3d_dm_fw.shader` 文件中定义。
`ownBaseShader` 由 `shader_data_loader.cpp` 在加载时自动设置为该shader的URI（line 162），
而非通过JSON字段配置。

**Shader资源文件位置**：
- 主Shader文件: `assets/3d/shaders/shader/core3d_dm_fw.shader`
- Fragment SPV: `assets/3d/shaders/shader/core3d_dm_fw.frag.spv`
- LLOIT Fragment SPV: `assets/3d/shaders/shader/core3d_dm_fw_lloit.frag.spv`
- WBOIT Fragment SPV: `assets/3d/shaders/shader/core3d_dm_fw_wboit.frag.spv`
- LLOIT PipelineLayout: `assets/3d/pipelinelayouts/core3d_dm_fw_lloit.shaderpl`

**代码路径分析**（ShaderManager）：

```cpp
// shader_manager.cpp:1027-1035 (Compute Shader查找逻辑)
if (handleType == RenderHandleType::COMPUTE_SHADER_STATE_OBJECT) {
    if (RenderHandleUtil::IsValid(ownBaseShaderHandle)) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, computeShaderMappings_.clientData,
            ownBaseShaderHandle, renderSlotId);
    }
    if ((!slotHandle) && (RenderHandleUtil::IsValid(addBaseShaderHandle))) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, computeShaderMappings_.clientData,
            addBaseShaderHandle, renderSlotId);
    }
}
```

**工作流程**：

1. **Shader加载阶段** (`ShaderLoader::CreateGraphicsShader`)：
   - 加载 `core3d_dm_fw.shader`
   - 解析Shader JSON中的所有变体（包括LLOIT和WBOIT变体）
   - 每个变体的 `ownBaseShader` 自动设置为当前shader的URI
   - 如果JSON中指定了 `baseShader`，则设置 `addBaseShader`
   - 建立 baseShaderHandle + renderSlotId → ShaderHandle 的哈希映射

2. **Shader查询阶段** (`ShaderManager::GetShaderHandle`)：
   - 查询 `CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT` RenderSlot
   - 首先尝试直接匹配（renderSlotId相同则直接返回）
   - 否则尝试 `ownBaseShaderHandle` → 查找 `core3d_dm_fw` 的变体
   - 如果找到匹配的变体（LLOIT），返回ShaderHandle
   - 如果未找到，尝试 `addBaseShaderHandle`（备用）

3. **渲染阶段** (`RenderNodeDefaultMaterialRenderSlot`)：
   - 根据RenderSlot查询ShaderHandle
   - 通过 `GetGraphicsPsoHandle` 获取PSO
   - 使用LLOIT Shader进行透明物体渲染

---

## 代码路径详解

### ShaderManager中的关键函数

**文件位置**：`submodules\LumeRender\src\device\shader_manager.cpp`

#### 1. GetShaderHandle（查找Shader）

```cpp
// shader_manager.cpp:981-1048
RenderHandleReference ShaderManager::GetShaderHandle(
    const RenderHandle& handle, const uint32_t renderSlotId) const
{
    const RenderHandleType handleType = RenderHandleUtil::GetHandleType(handle);
    if ((handleType != RenderHandleType::COMPUTE_SHADER_STATE_OBJECT) &&
        (handleType != RenderHandleType::SHADER_STATE_OBJECT)) {
        return {}; // early out
    }

    const uint32_t index = RenderHandleUtil::GetIndexPart(handle);
    RenderHandle ownBaseShaderHandle;
    RenderHandle addBaseShaderHandle;
    // check first for own validity and possible base shader handle
    if ((handleType == RenderHandleType::COMPUTE_SHADER_STATE_OBJECT) &&
        (index < static_cast<uint32_t>(computeShaderMappings_.clientData.size()))) {
        const auto& ref = computeShaderMappings_.clientData[index];
        if (ref.renderSlotId == renderSlotId) {
            return ref.rhr; // early out
        }
        ownBaseShaderHandle = ref.ownBaseShaderHandle;
        addBaseShaderHandle = ref.addBaseShaderHandle;
    } else if ((handleType == RenderHandleType::SHADER_STATE_OBJECT) &&
               (index < static_cast<uint32_t>(shaderMappings_.clientData.size()))) {
        const auto& ref = shaderMappings_.clientData[index];
        if (ref.renderSlotId == renderSlotId) {
            return ref.rhr; // early out
        }
        ownBaseShaderHandle = ref.ownBaseShaderHandle;
        addBaseShaderHandle = ref.addBaseShaderHandle;
    }
    // try to find a match through base shader variant
    // ... (lambda GetBaseShaderMatchedSlotHandle, see below)
    return slotHandle;
}
```

**关键点**：
- 查找优先级：`ownBaseShaderHandle` > `addBaseShaderHandle`
- 通过RenderSlot ID匹配具体的Shader变体

#### 2. GetBaseShaderMatchedSlotHandle（匹配RenderSlot）

此函数为 `GetShaderHandle` 内的lambda（`shader_manager.cpp:1011-1024`）：

```cpp
auto GetBaseShaderMatchedSlotHandle = [](const auto& hashToShaderVariant, const auto& clData,
                                          const RenderHandle baseShaderHandle, const uint32_t renderSlotId) {
    PLUGIN_ASSERT(RenderHandleUtil::IsValid(baseShaderHandle));

    RenderHandleReference rhr;
    const uint64_t hash = HashHandleAndSlot(baseShaderHandle, renderSlotId);
    if (const auto iter = hashToShaderVariant.find(hash); iter != hashToShaderVariant.cend()) {
        const uint32_t arrayIndex = RenderHandleUtil::GetIndexPart(iter->second);
        if (arrayIndex < clData.size() && (clData[arrayIndex].renderSlotId == renderSlotId)) {
            rhr = clData[arrayIndex].rhr;
        }
    }
    return rhr;
};
```

**关键点：**
- 使用 `HashHandleAndSlot` 计算baseShaderHandle与renderSlotId的哈希
- 在 `hashToShaderVariant` 哈希表中查找（非遍历，O(1)查找）
- 验证找到的索引和renderSlotId是否匹配

---

## 实际应用场景详解

### 场景1：OIT Shader切换（WBOIT vs LLOIT）

**场景描述**：
- 游戏支持两种OIT算法：WBOIT和LLOIT
- 用户可以在运行时切换OIT类型
- 需要动态加载不同的Shader变体

**Shader层次**：
```
core3d_dm_fw (基础Forward Shader)
    ├── core3d_dm_fw_wboit (WBOIT变体)
    │   └── ownBaseShaderHandle = core3d_dm_fw
    │   └── renderSlotId = CORE3D_RS_DM_FW_TRANSLUCENT_WBOIT
    │
    └── core3d_dm_fw_lloit (LLOIT变体)
        └── ownBaseShaderHandle = core3d_dm_fw
        └── renderSlotId = CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT
```

**切换流程**：

```cpp
// 1. 用户设置OIT类型
renderConfig->OITType = SceneOITType::WBOIT;

// 2. RenderSystem根据OIT类型选择RenderNodeGraph
if (OITType == WBOIT) {
    renderNodeGraph = CreateRenderNodeGraph("wboit.rng");
} else if (OITType == LLOIT) {
    renderNodeGraph = CreateRenderNodeGraph("lloit.rng");
}

// 3. RenderNode查询Shader
string_view shaderPath = "3dshaders://shader/core3d_dm_fw_wboit";
uint32_t renderSlotId = CORE3D_RS_DM_FW_TRANSLUCENT_WBOIT;
RenderHandle shaderHandle = shaderMgr.GetShaderHandle(shaderPath, renderSlotId);

// 4. ShaderManager查找流程
// Step1: 查找 shaderPath → ownBaseShaderHandle (core3d_dm_fw)
// Step2: 根据 baseShaderHandle + renderSlotId 匹配变体
// Step3: 返回 core3d_dm_fw_wboit shaderHandle
```

### 场景2：材质多RenderSlot渲染

**场景描述**：
- 一个材质需要在多个RenderSlot中渲染（如Opaque + Depth）
- 同一个Shader需要支持多个RenderSlot配置

**Shader配置**：
```
core3d_dm_fw.shader
    ├── ownBaseShader = "3dshaders://shader/core3d_dm_fw.shader" (自动设置)
    ├── RenderSlot配置:
    │   ├── CORE3D_RS_DM_FW_OPAQUE (opaque渲染)
    │   ├── CORE3D_RS_DM_DEPTH (深度预渲染)
    │   └── CORE3D_RS_DM_FW_TRANSLUCENT (透明渲染)
```

**查找流程**：

```cpp
// 材质在多个Slot渲染
for (auto& slot : materialRenderSlots) {
    uint32_t renderSlotId = slot.renderSlotId;

    // ShaderManager根据不同RenderSlot返回不同Shader变体
    RenderHandle shaderHandle = shaderMgr.GetShaderHandle(
        "core3d_dm_fw", renderSlotId);

    // RenderSlot: OPAQUE → 返回 opaque变体ShaderHandle
    // RenderSlot: DEPTH → 返回 depth变体ShaderHandle
    // RenderSlot: TRANSLUCENT → 返回 translucent变体ShaderHandle
}
```

---

## 配置示例

### Shader JSON配置（示例）

```json
{
    "compatibility_info": {
        "version": "22.00",
        "type": "shader"
    },
    "shaders": [
        {
            "displayName": "Forward LLOIT",
            "variantName": "LLOIT",
            "vert": "3dshaders://shader/core3d_dm_fw.vert.spv",
            "frag": "3dshaders://shader/core3d_dm_fw_lloit.frag.spv",
            "baseShader": "3dshaders://shader/other_base.shader",  // ← addBaseShader（外部基础Shader）
            "renderSlot": "CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT"
        }
    ]
}
```

**关键字段**：
- `baseShader`: 指向外部基础Shader的URI，映射到代码中的 `addBaseShader` 字段
  （注意：`ownBaseShader` 不通过JSON配置，而是在加载时自动设置为当前shader的URI）
- `renderSlot`: Shader变体关联的RenderSlot名称

### PipelineLayout配置（shaderpl）

```json
{
    "compatibility_info": {
        "version": "22.00",
        "type": "shaderpl"
    },
    "shaderState": {
        "shader": "3dshaders://shader/core3d_dm_fw_lloit.shader",
        "graphicsState": "3dshaders://graphicsstate/gs_default_translucent.json",
        "vertexInputDeclaration": "3dshaders://vertexinputdeclaration/default_vid.json"
    },
    "pipelineLayout": {
        "descriptorSetLayouts": [
            {
                "set": 0,
                "bindings": [
                    { "binding": 0, "descriptorType": "uniform_buffer", "shaderStageFlags": "vertex" }
                ]
            }
        ]
    }
}
```

---

## 性能优化考虑

### 1. Shader查找优化

**优化策略**：
- `ownBaseShaderHandle` 优先查找（命中率更高）
- 使用 `hashToShaderVariant` 哈希表加速查找
- RenderSlot ID作为快速过滤条件

**数据结构**：
```cpp
// hashToShaderVariant_ 的类型（shader_manager.h:354）
BASE_NS::unordered_map<uint64_t, RenderHandle> hashToShaderVariant_;

// key = HashHandleAndSlot(baseShaderHandle, renderSlotId)
// value = 匹配的ShaderVariant的RenderHandle（类型为SHADER_STATE_OBJECT或COMPUTE_SHADER_STATE_OBJECT）
// 通过该Handle的index可索引到computeShaderMappings_.clientData或shaderMappings_.clientData
// 获取对应Data中的rhr、renderSlotId等信息
```

### 2. Shader缓存策略

**缓存层级**：
- **ShaderHandle缓存**: RenderNode级别的PSO缓存
- **BaseShaderHandle缓存**: ShaderManager级别的变体缓存
- **RenderSlot映射缓存**: 预计算RenderSlot→ShaderHandle映射

---

## 总结对比表

| 对比维度 | ownBaseShaderHandle | addBaseShaderHandle |
|---------|---------------------|--------------------|
| **定义** | Shader自身的基础Shader句柄 | 添加变体到外部基础Shader的句柄 |
| **语义** | "我是谁的变体" | "我将添加为谁的变体" |
| **方向** | 从子Shader指向父Shader | 从子Shader指向父Shader（组合） |
| **优先级** | **高**（优先查找） | **低**（备用查找） |
| **典型场景** | Shader继承体系（如LLOIT继承Forward） | Shader组合体系（如后处理模块） |
| **示例** | core3d_dm_fw_lloit → core3d_dm_fw | BloomEffect → PostProcessBase |
| **查找流程** | 在ownBaseShaderHandle的变体列表中查找 | 在addBaseShaderHandle的变体列表中查找 |
| **数据流向** | 子Shader → ownBaseShaderHandle → 变体列表 → 匹配RenderSlot | 子Shader → addBaseShaderHandle → 变体列表 → 匹配RenderSlot |

---

## 常见错误与调试

### 错误1：Shader变体未找到

**错误日志**：
```
RENDER_VALIDATION: Shader variant not found for renderSlot: CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT
```

**排查步骤**：
1. 检查Shader JSON配置中是否设置了 `ownBaseShaderHandle`
2. 检查基础Shader是否存在且正确加载
3. 检查RenderSlot ID是否与Shader配置匹配
4. 检查ShaderManager日志中的加载信息

### 错误2：BaseShaderHandle无效

**错误日志**：
```
RENDER_VALIDATION: Invalid ownBaseShaderHandle for shader: core3d_dm_fw_lloit
```

**排查步骤**：
1. 检查Shader URI是否正确（如 "3dshaders://shader/core3d_dm_fw.shader"）
2. 检查基础Shader是否在ShaderManager中注册
3. 检查Shader加载顺序（基础Shader应先加载）

---

## 相关文件索引

| 文件路径 | 功能 |
|---------|------|
| `shader_manager.cpp:981-1048` | GetShaderHandle查找逻辑 |
| `shader_manager.cpp:1011-1024` | GetBaseShaderMatchedSlotHandle lambda |
| `shader_manager.cpp:1026-1045` | ownBaseShaderHandle优先查找 |
| `shader_manager.h:293-304` | ComputeMappings::Data 定义 |
| `shader_manager.h:309-324` | GraphicsMappings::Data 定义 |
| `api/render/device/intf_shader_manager.h:236-239` | ownBaseShader/addBaseShader 字段 |

---

**文档版本**: 1.1
**更新日期**: 2026-05-15
**作者**: Claude Analysis
**状态**: 已补充Shader示例和代码路径
