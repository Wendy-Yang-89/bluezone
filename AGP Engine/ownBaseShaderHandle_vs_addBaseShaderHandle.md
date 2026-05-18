# ownBaseShaderHandle 与 addBaseShaderHandle 的区别

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

### ComputeMappings::Data
```cpp
struct ComputeMappings {
    struct Data {
        RenderHandleReference rhr;
        RenderHandle ownBaseShaderHandle; // link to own uri for all variants
        RenderHandle addBaseShaderHandle; // link to separate base shader where it will add its variant
        uint32_t renderSlotId { INVALID_SM_INDEX };
        // ... 其他字段
    };
};
```

### GraphicsMappings::Data
```cpp
struct GraphicsMappings {
    struct Data {
        RenderHandleReference rhr;
        RenderHandle ownBaseShaderHandle; // link to own uri for all variants
        RenderHandle addBaseShaderHandle; // link to separate base shader where it will add its variant
        uint32_t renderSlotId { INVALID_SM_INDEX };
        // ... 其他字段
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
    ├── ownBaseShaderHandle = null
    └── 变体: LightingVariant
            ├── ownBaseShaderHandle = BasicShader
            └── 变体: ShadowVariant
                    └── ownBaseShaderHandle = BasicShader
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
core3d_dm_fw.shader (基础Forward Shader)
    ├── ownBaseShaderHandle = null (自己是基础)
    └── 变体: core3d_dm_fw_lloit.shader
            ├── ownBaseShaderHandle = core3d_dm_fw
            └── 渲染透明物体 (LLOIT算法)
    
    └── 变体: core3d_dm_fw_wboit.shader
            ├── ownBaseShaderHandle = core3d_dm_fw  
            └── 渲染透明物体 (WBOIT算法)
```

**Shader资源文件位置**：
- 基础Shader: `assets/3d/shaders/shader/core3d_dm_fw.frag`
- LLOIT变体: `assets/3d/shaders/shader/core3d_dm_fw_lloit.frag`
- WBOIT变体: `assets/3d/shaders/shader/core3d_dm_fw_wboit.frag`
- PipelineLayout: `assets/3d/pipelinelayouts/core3d_dm_fw_lloit.shaderpl`

**代码路径分析**（ShaderManager）：

```cpp
// shader_manager.cpp:1028-1030
// GetShaderHandle查找逻辑
if (RenderHandleUtil::IsValid(ownBaseShaderHandle)) {
    slotHandle = GetBaseShaderMatchedSlotHandle(
        hashToShaderVariant_, computeShaderMappings_.clientData, 
        ownBaseShaderHandle, renderSlotId);
}
```

**工作流程**：

1. **Shader加载阶段** (`ShaderManager::LoadShader`)：
   - 加载 `core3d_dm_fw_lloit.shader`
   - 解析Shader JSON配置，获取 `ownBaseShaderHandle` 引用
   - 建立 ShaderHandle → BaseShaderHandle 的映射关系

2. **Shader查询阶段** (`ShaderManager::GetShaderHandle`)：
   - 查询 `CORE3D_RS_DM_FW_TRANSLUCENT` RenderSlot
   - 首先尝试 `ownBaseShaderHandle` → 查找 `core3d_dm_fw`
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
// shader_manager.cpp:990-1008
RenderHandle ShaderManager::GetShaderHandle(
    const string_view shaderPath, const uint32_t renderSlotId)
{
    RenderHandle ownBaseShaderHandle;
    RenderHandle addBaseShaderHandle;
    
    // 获取shader的ownBaseShaderHandle
    if (auto ref = shaderUriToShader.find(shaderPath)) {
        ownBaseShaderHandle = ref.ownBaseShaderHandle;
        addBaseShaderHandle = ref.addBaseShaderHandle;
    }
    
    // 首先尝试ownBaseShaderHandle
    if (RenderHandleUtil::IsValid(ownBaseShaderHandle)) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, clientData, 
            ownBaseShaderHandle, renderSlotId);
    }
    
    // 如果未找到，尝试addBaseShaderHandle
    if (!slotHandle && RenderHandleUtil::IsValid(addBaseShaderHandle)) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, clientData, 
            addBaseShaderHandle, renderSlotId);
    }
    
    return slotHandle;
}
```

**关键点**：
- 查找优先级：`ownBaseShaderHandle` > `addBaseShaderHandle`
- 通过RenderSlot ID匹配具体的Shader变体

#### 2. GetBaseShaderMatchedSlotHandle（匹配RenderSlot）

```cpp
// shader_manager.cpp:665-684
RenderHandle ShaderManager::GetBaseShaderMatchedSlotHandle(
    const unordered_map<uint64_t, ShaderVariantData>& hashToShaderVariant,
    const ShaderVariantClientData& clientData,
    const RenderHandle baseShaderHandle,
    const uint32_t renderSlotId)
{
    // 根据baseShaderHandle查找所有变体
    for (const auto& variant : hashToShaderVariant) {
        if (variant.second.baseShaderHandle == baseShaderHandle) {
            // 检查RenderSlot是否匹配
            if (variant.second.renderSlotId == renderSlotId) {
                return variant.second.shaderHandle;
            }
        }
    }
    return {}; // 未找到
}
```

**关键点**：
- 遍历所有Shader变体
- 查找匹配baseShaderHandle和renderSlotId的变体
- 返回具体的ShaderHandle

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
    ├── ownBaseShaderHandle = null
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
            "ownBaseShaderHandle": "3dshaders://shader/core3d_dm_fw.shader", // ← 关键配置
            "renderSlot": "CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT"
        }
    ]
}
```

**关键字段**：
- `ownBaseShaderHandle`: 指向基础Shader的URI
- `renderSlot`: Shader变体关联的RenderSlot ID

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
unordered_map<uint64_t, ShaderVariantData> hashToShaderVariant;

struct ShaderVariantData {
    RenderHandle shaderHandle;
    RenderHandle baseShaderHandle; // ownBaseShaderHandle或addBaseShaderHandle
    uint32_t renderSlotId;
    ShaderSpecializationConstantData specialization;
};
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
| `shader_manager.cpp:990-1008` | GetShaderHandle查找逻辑 |
| `shader_manager.cpp:665-684` | GetBaseShaderMatchedSlotHandle匹配逻辑 |
| `shader_manager.cpp:1028-1030` | ownBaseShaderHandle优先查找 |
| `assets/3d/shaders/shader/core3d_dm_fw_lloit.frag` | LLOIT Shader源码 |
| `assets/3d/pipelinelayouts/core3d_dm_fw_lloit.shaderpl` | LLOIT PipelineLayout配置 |
| `api/render/device/intf_shader_manager.h` | ShaderManager接口定义 |

---

**文档版本**: 1.1  
**更新日期**: 2026-05-15  
**作者**: Claude Analysis  
**状态**: 已补充Shader示例和代码路径
