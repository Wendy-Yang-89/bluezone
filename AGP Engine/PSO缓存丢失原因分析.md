# PSO缓存丢失原因分析

## 背景与问题引入

### PSO缓存的作用

**PSO缓存** 是渲染引擎优化性能的核心机制：

- **避免重复创建**：相同配置的PSO复用，减少编译开销
- **降低首帧延迟**：首次创建后缓存，后续渲染快速获取
- **减少GPU驱动负担**：减少Pipeline编译请求

PSO创建涉及Shader编译、状态配置、驱动验证，开销较大。缓存机制对渲染性能至关重要。

### 问题现象

在LumeRender中，切换RenderNodeGraph（如从普通渲染切换到WBOIT）时，观察到：

- 首帧渲染耗时显著增加
- PSO需要重新创建而非复用已有缓存
- 切换后再切回，缓存仍未保留

此现象导致频繁切换场景时性能下降，用户体验受影响。

### 问题重要性

PSO缓存丢失的影响：

| 影响维度 | 具体表现 |
|---------|---------|
| **首帧延迟** | 切换后首帧渲染耗时增加数百毫秒 |
| **用户体验** | 场景切换时出现卡顿或黑屏闪烁 |
| **资源浪费** | 相同PSO重复创建，GPU编译资源浪费 |
| **调试困难** | 难以区分是缓存失效还是配置错误 |

理解缓存丢失的根本原因，有助于评估性能影响和设计解决方案。

### 本文档解决的问题

本文档深入分析LumeRender框架中PSO缓存丢失的技术原因：

- PSO缓存的数据结构和作用域
- RenderNodeGraph销毁流程对缓存的影响
- Vulkan RenderPass兼容性限制
- 架构设计理念与权衡

---

## 核心概念

### RenderNodeGraph

**RenderNodeGraph** 是LumeRender的渲染流程定义，采用DAG（有向无环图）结构：

- 定义渲染节点（RenderNode）的执行顺序
- 配置渲染资源（Attachment、Shader、Material）
- 组织渲染Pass和Subpass

不同渲染模式对应不同RenderNodeGraph：
- **普通渲染**：单Color Attachment，标准Forward渲染
- **WBOIT**：双Color Attachment（accumulation + revealage），透明物体排序无关渲染

切换渲染模式即切换RenderNodeGraph实例。

### RenderNodeContextData

**RenderNodeContextData** 是RenderNode的运行时上下文数据容器：

| 成员 | 类型 | 作用 |
|------|------|------|
| `renderCommandList` | RenderCommandList | 渲染命令队列 |
| `renderBarrierList` | RenderBarrierList | 资源屏障管理 |
| `nodeContextPsoMgr` | NodeContextPsoManager | **PSO创建和缓存管理** |
| `nodeContextPoolMgr` | NodeContextPoolManager | GPU资源池管理 |

关键：`nodeContextPsoMgr`存储PSO缓存，与RenderNodeContextData强绑定。

### NodeContextPsoManager

**NodeContextPsoManager** 是PSO生命周期管理器：

- **创建PSO**：根据Shader、GraphicsState等参数创建Pipeline
- **缓存PSO**：存储已创建的PSO，通过哈希Key查找
- **销毁PSO**：RenderNodeGraph销毁时清理所有PSO

缓存数据结构：

```
GraphicsPipelineStateCache:
  ├── hashToHandle: unordered_map<uint64_t, RenderHandle>  // 哈希→PSO句柄映射
  ├── psoCreationData: vector<GraphicsPipelineStateCreationData>  // 创建参数
  └── pipelineStateObjects: unordered_map<uint64_t, PsoData>  // PSO对象（PsoData含pso+shaderHandle）
```

### PSO缓存的哈希Key

PSO缓存通过哈希Key识别唯一配置：

| 平台 | 哈希计算方式 | 包含参数 |
|------|------------|---------|
| **Vulkan** | `Hash(handle.id, psoStateHash)` | Shader + GraphicsState + **RenderPass状态** |
| **GL/GLES** | `handle.id` | 仅Shader句柄 |

Vulkan平台的哈希包含RenderPass配置，因为Vulkan要求PSO与RenderPass兼容。

### RenderPass兼容性

**RenderPass兼容性** 是Vulkan的核心限制：

Vulkan规范要求Graphics Pipeline必须与创建时的RenderPass兼容。兼容条件包括：
- Attachment数量相同
- Attachment格式相同
- 采样数（Sample Count）相同

WBOIT与普通渲染的RenderPass配置不同：

| 渲染模式 | Color Attachments | 格式 | Sample Count |
|---------|------------------|------|--------------|
| 普通渲染 | 1个 | RGBA8/RGBA16F | 1x或4x |
| WBOIT | 2个（acc+rev） | RGBA16F + R16F | 1x或4x |

由于RenderPass不兼容，相同Shader在不同渲染模式下需要不同的PSO。

### PSO缓存丢失流程

```
切换RenderNodeGraph时PSO缓存丢失流程:

┌──────────────────────────────────────────────────┐
│ 初始状态: 普通渲染RenderNodeGraph                 │
├──────────────────────────────────────────────────┤
│ RenderNodeGraphNodeStore                         │
│   └─ RenderNodeContextData[0]                    │
│        └─ NodeContextPsoManager                  │
│             └─ GraphicsPipelineStateCache        │ 
│                  └─ hashToHandle (PSO缓存)       │
│                                                  │
│   └─ RenderNodeContextData[1]                    │
│        └─ NodeContextPsoManager                  │
│             └─ GraphicsPipelineStateCache        │
│                  └─ hashToHandle (PSO缓存)       │
└──────────────────────────────────────────────────┘
                      │
                      │ 用户切换到WBOIT
                      ▼
┌────────────────────────────────────────────────────┐
│ 步骤1: 销毁旧RenderNodeGraph                        │
├────────────────────────────────────────────────────┤
│ RenderNodeGraphManager::PendingDestroy()           │
│   └─ move(renderNodeContextData)                   │
│       └─► 移动到pendingRenderNodeGraphDestructions_ │
│   └─ nodeGraphData_[index] = nullptr               │
│   └─ nodeGraphHandles_[index] = {}                 │
│                                                    │
│ PSO缓存被移动到销毁队列                              │
└────────────────────────────────────────────────────┘
                      │
                      │ 等待N帧
                      ▼
┌──────────────────────────────────────────────────┐
│ 步骤2: 延迟销毁                                   │
├──────────────────────────────────────────────────┤
│ HandlePendingAllocations()                       │
│   └─ 检查frameIndex是否超时                       │
│   └─ erase(pendingRenderNodeGraphDestructions_)  │
│                                                  │
│ RenderNodeContextData析构                        │
│   └─► NodeContextPsoManager析构                  │
│   └─► GraphicsPipelineStateCache析构             │
│   └─► hashToHandle销毁 (PSO缓存永久消失)          │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ 步骤3: 创建新RenderNodeGraph                      │
├──────────────────────────────────────────────────┤
│ RenderNodeGraphManager::Create()                 │
│   └─ 创建新的RenderNodeGraphNodeStore             │
│   └─ 创建新的renderNodeContextData数组            │
│   └─ 创建新的NodeContextPsoManager (空缓存)       │
│                                                  │
│ PSO缓存为空, 需要重新创建                          │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ 步骤4: 首次渲染                                   │
├──────────────────────────────────────────────────┤
│ RenderNode::InitNode()                           │
│   └─► GetGraphicsPsoHandle()                     │
│   └─► hashToHandle.find(hash)                    │
│       └─► 失败 (空缓存)                           │
│   └─► 创建新PSO并缓存                             │
│                                                  │
│ 首帧耗时增加 (PSO重新创建)                         │
└──────────────────────────────────────────────────┘
```

---

## 一、PSO缓存机制详解

### 1.1 PSO缓存的数据结构层次

```
RenderNodeGraphNodeStore
    ├─ vector<RenderNodeData>               // RenderNode实例
    │   ├─ unique_ptr<IRenderNode> node     // RenderNode对象
    │   └─ unique_ptr<RenderNodeGraphInputs> inputData
    │
    └─ vector<RenderNodeContextData>        // RenderNode上下文数据
        ├─ unique_ptr<RenderCommandList> renderCommandList
        ├─ unique_ptr<RenderBarrierList> renderBarrierList
        ├─ unique_ptr<RenderNodeContextManager> renderNodeContextManager
        ├─ unique_ptr<NodeContextPsoManager> nodeContextPsoMgr  ← PSO管理器
        │   ├─ ComputePipelineStateCache computePipelineStateCache_     // 计算PSO缓存
        │   │   ├─ vector<ComputePipelineStateCreationData> psoCreationData
        │   │   ├─ vector<unique_ptr<ComputePipelineStateObject>> pipelineStateObjects
        │   │   └─ unordered_map<uint64_t, RenderHandle> hashToHandle    ← 缓存映射
        │   │
        │   └─ GraphicsPipelineStateCache graphicsPipelineStateCache_    // 图形PSO缓存
        │       ├─ vector<GraphicsPipelineStateCreationData> psoCreationData
        │       ├─ unordered_map<uint64_t, PsoData> pipelineStateObjects  // PsoData含pso+shaderHandle
        │       └─ unordered_map<uint64_t, RenderHandle> hashToHandle    ← 缓存映射
        │
        ├─ unique_ptr<NodeContextDescriptorSetManager> nodeContextDescriptorSetMgr
        └─ unique_ptr<NodeContextPoolManager> nodeContextPoolMgr
```

**关键代码位置**：
- `render_node_graph_node_store.h:78-98` - RenderNodeContextData定义
- `node_context_pso_manager.h:115-166` - PipelineStateCache定义
- `renderer.cpp:164` - NodeContextPsoManager创建

---

### 1.2 PSO缓存的核心机制

**缓存Key（哈希）生成**：

```cpp
// node_context_pso_manager.cpp:62-77
uint64_t HashComputeShader(const RenderHandle shaderHandle,
                           const ShaderSpecializationConstantDataView& shaderSpecialization)
{
    return Hash(shaderHandle.id, shaderSpecialization);
}

uint64_t HashGraphicsShader(const RenderHandle shaderHandle,
                            const RenderHandle graphicsStateHandle,
                            const array_view<const DynamicStateEnum> dynamicStates,
                            const ShaderSpecializationConstantDataView& shaderSpecialization,
                            const uint64_t customGraphicsStateHash)
{
    uint64_t hash = 0;
    for (const auto& ref : dynamicStates) {
        HashCombine(hash, static_cast<uint64_t>(ref));
    }
    return Hash(hash, shaderHandle.id, graphicsStateHandle.id,
                shaderSpecialization, customGraphicsStateHash);
}
```

**缓存查找流程**：

```cpp
// node_context_pso_manager.cpp:262-337
RenderHandle NodeContextPsoManager::GetGraphicsPsoHandleImpl(...)
{
    auto& cache = graphicsPipelineStateCache_;
    const uint64_t hash = HashGraphicsShader(shader, graphicsState,
                                              dynamicStates, shaderSpecialization, cGfxHash);

    const auto iter = cache.hashToHandle.find(hash);
    const bool needsNewPso = (iter == cache.hashToHandle.cend());

    if (needsNewPso) {
        // 创建新PSO并缓存
        psoHandle = RenderHandleUtil::CreateHandle(...);
        cache.hashToHandle[hash] = psoHandle;
        cache.psoCreationData.push_back(move(psoCreationData));
    } else {
        // 从缓存获取
        psoHandle = iter->second;
    }

    return psoHandle;
}
```

---

### 1.3 PSO缓存的作用域

**作用域范围**：

| 组件 | 作用域 | 所属对象 |
|------|--------|----------|
| `NodeContextPsoManager` | **每个RenderNode实例** | `RenderNodeContextData` |
| `GraphicsPipelineStateCache` | NodeContextPsoManager实例 | 成员变量 |
| `hashToHandle`（缓存映射） | NodeContextPsoManager实例 | 成员变量 |
| `pipelineStateObjects` | NodeContextPsoManager实例 | 成员变量 |

**关键结论**：
- ❌ **不是全局缓存** - PSO缓存不是存储在Device或ShaderManager中
- ❌ **不是RenderNodeGraph级别缓存** - 不是存储在RenderNodeGraphNodeStore中
- ✅ **是RenderNode级别缓存** - 每个RenderNode实例有独立的PSO缓存

---

## 二、RenderNodeGraph销毁流程分析

### 2.1 销毁触发时机

```cpp
// render_node_graph_manager.cpp:387-421
void RenderNodeGraphManager::PendingDestroy(const RenderHandle handle)
{
    const uint32_t index = RenderHandleUtil::GetIndexPart(handle);
    // ...

    // 销毁所有数据，但保留RenderNodeContextData（包含command buffers和PSO缓存）
    // 将RenderNodeContextData添加到销毁队列
    pendingRenderNodeGraphDestructions_.push_back(PendingRenderNodeGraphDestruction {
        device_.GetFrameCount(),
        move(nodeGraphData_[index]->renderNodeContextData)  // ← PSO缓存在这里被移动
    });

    nodeGraphData_[index] = nullptr;  // 清空节点存储
    nodeGraphHandles_[index] = {};    // 清空handle
}
```

---

### 2.2 延迟销毁机制

```cpp
// render_node_graph_manager.cpp:276-334
void RenderNodeGraphManager::HandlePendingAllocations()
{
    const uint64_t minAge = static_cast<uint64_t>(device_.GetCommandBufferingCount()) + 1;
    const uint64_t ageLimit = (device_.GetFrameCount() < minAge) ? 0 : (device_.GetFrameCount() - minAge);

    // 多帧延迟销毁（等待GPU使用完成）
    if (!pendingRenderNodeGraphDestructions_.empty()) {
        const auto oldResources = std::partition(
            pendingRenderNodeGraphDestructions_.begin(),
            pendingRenderNodeGraphDestructions_.end(),
            [ageLimit](const auto& destructionQueue) {
                return destructionQueue.frameIndex >= ageLimit;
            });

        // 销毁超时的资源（包括PSO缓存）
        pendingRenderNodeGraphDestructions_.erase(oldResources,
                                                   pendingRenderNodeGraphDestructions_.end());
    }
}
```

**销毁时序**：
1. **第0帧**：调用`PendingDestroy()`，`renderNodeContextData`被移动到销毁队列
2. **第N帧**（N = commandBufferingCount + 1）：延迟销毁机制确保GPU已完成使用
3. **第N+1帧**：`HandlePendingAllocations()`真正销毁`renderNodeContextData`
4. **销毁时**：`NodeContextPsoManager`及其所有PSO缓存被销毁

---

### 2.3 数据流分析

```
切换RenderNodeGraph时的数据流：

步骤1：销毁旧RenderNodeGraph
    ↓ RenderNodeGraphManager::Destroy()
    ↓ RenderNodeGraphManager::PendingDestroy()
    ↓ move(nodeGraphData_[index]->renderNodeContextData)
    ↓ renderNodeContextData被移动到pendingRenderNodeGraphDestructions_
    ↓
    ↓ [延迟N帧等待GPU完成]
    ↓
    ↓ RenderNodeGraphManager::HandlePendingAllocations()
    ↓ pendingRenderNodeGraphDestructions_.erase()
    ↓ RenderNodeContextData析构
    ↓ NodeContextPsoManager析构
    ↓ GraphicsPipelineStateCache析构
    ↓ hashToHandle、pipelineStateObjects销毁 ← PSO缓存消失 ✗

步骤2：创建新RenderNodeGraph
    ↓ RenderNodeGraphManager::Create()
    ↓ RenderNodeGraphManager::PendingCreate()
    ↓ 创建新的RenderNodeGraphNodeStore
    ↓ 创建新的renderNodeContextData数组
    ↓ 创建新的NodeContextPsoManager（空缓存）
    ↓ renderer::InitializeRenderNodeContextData()
    ↓ nodeContextData.nodeContextPsoMgr = make_unique<NodeContextPsoManager>()
    ↓
    ↓ [渲染循环]
    ↓
    ↓ RenderNode::InitNode()
    ↓ INodeContextPsoManager::GetGraphicsPsoHandle()
    ↓ hashToHandle.find(hash) → 失败（空缓存）
    ↓ 创建新PSO并缓存 ← 重新创建 ✓
```

---

## 三、为什么无法保留PSO缓存的根本原因

### 3.1 技术限制：PSO缓存与RenderNodeContextData强绑定

**问题核心**：

```cpp
// render_node_graph_node_store.h:89
struct RenderNodeContextData {
    unique_ptr<NodeContextPsoManager> nodeContextPsoMgr;  // PSO管理器是成员变量
};
```

**分析**：
- PSO缓存存储在`NodeContextPsoManager`的成员变量中
- `NodeContextPsoManager`是`RenderNodeContextData`的成员变量
- `RenderNodeContextData`是`RenderNodeGraphNodeStore`的成员变量
- **整个对象树是强绑定关系，无法分离PSO缓存**

**没有API可以提取缓存**：
- ❌ 没有接口可以导出PSO缓存
- ❌ 没有接口可以转移PSO缓存到其他对象
- ❌ 没有接口可以在销毁前保留PSO缓存

---

### 3.2 Vulkan RenderPass兼容性限制

**核心代码**：

```cpp
// node_context_pso_manager.cpp:444-445
const uint64_t hash = (device_.GetBackendType() == DeviceBackendType::VULKAN)
    ? Hash(handle.id, psoStateHash)  // ← Vulkan需要包含RenderPass状态
    : handle.id;                      // ← GL/GLES只需要shader handle
```

**psoStateHash包含的信息**：
- RenderPassDesc（attachment formats、load/store ops）
- RenderPassSubpassDesc（attachment引用、subpass配置）
- Sample count（MSAA配置）
- Subpass index

---

**Vulkan规范要求**：

根据Vulkan规范：
> Graphics pipelines must be created with a compatible render pass object.
> A render pass is compatible with a pipeline if:
> - The render pass has the same number of attachments
> - Each attachment has the same format
> - The sample count matches

**WBOIT vs 普通渲染的RenderPass差异**：

| 渲染模式 | Color Attachment数量 | Depth Attachment | Sample Count | Format |
|---------|---------------------|-----------------|-------------|--------|
| **普通渲染** | 1个 | 1个 | MSAA或不MSAA | RGBA8/RGBA16F |
| **WBOIT** | 2个（accumulation + revealage） | 1个 | MSAA或不MSAA | RGBA16F + R16F |

**结论**：
- 即使相同的shader、相同的graphicsState、相同的pipelineLayout
- 由于RenderPass配置不同，需要创建不同的PSO
- **全局缓存无法解决Vulkan的RenderPass兼容性问题**

---

**GL/GLES的特殊情况**：

```cpp
// node_context_pso_manager.cpp:445
const uint64_t hash = handle.id;  // GL/GLES只需要shader handle
```

GL/GLES不需要在PSO创建时指定RenderPass，因此理论上可以全局缓存。但现有框架为了保持跨平台一致性，仍然选择了RenderNode级别的缓存设计。

---

### 3.3 设计理念：RenderNode级别的缓存

**设计证据**：

```cpp
// intf_render_node.h:74-80
/** Sequential, called once after render graph has been initialized.
 * Anything can be done here, including gpu resource creation.
 * Note: InitNode can get called multiple times during runtime. The node must
 * invalidate any changed state/ handles and assume it starts from scratch.
 * @param renderNodeContextMgr Provides access to needed managers.
 */
virtual void InitNode(IRenderNodeContextManager& renderNodeContextMgr) = 0;
```

**设计意图**：
- ✅ 明确要求每次初始化"invalidate any changed state/handles"
- ✅ 明确要求"assume it starts from scratch"
- ✅ 支持动态RenderNodeGraph切换场景
- ✅ 避免跨RenderNodeGraph的状态污染

---

**为什么选择RenderNode级别缓存？**

| 设计考虑 | 原因 |
|---------|------|
| **RenderPass兼容性** | 每个RenderNodeGraph有独立的RenderPass配置，避免兼容性问题 |
| **状态管理简化** | 无需处理跨RenderNodeGraph的缓存同步和失效 |
| **内存管理清晰** | RenderNodeGraph销毁时所有资源一起清理，避免内存泄漏 |
| **动态RenderNodeGraph支持** | 支持运行时动态创建/销毁RenderNodeGraph |

---

**设计的缺点**：

| 问题 | 影响 |
|------|------|
| **切换时PSO缓存丢失** | 切换RenderNodeGraph时需要重新创建PSO（性能开销） |
| **无法共享PSO** | 相同shader在不同RenderNodeGraph中无法共享PSO缓存 |
| **内存重复** | 相同PSO可能在不同RenderNode中重复创建 |

---

## 四、架构设计限制总结

### 4.1 现有框架的三大限制

| 限制类型 | 具体限制 | 影响 |
|---------|---------|------|
| **数据结构限制** | PSO缓存存储在`RenderNodeContextData`中 | RenderNodeGraph销毁时缓存必然消失 |
| **API限制** | 没有接口可以提取、转移或保留PSO缓存 | 无法在销毁前保留缓存 |
| **平台限制** | Vulkan要求PSO匹配RenderPass | 即使相同shader也需要不同PSO |

---

### 4.2 无法缓存的根本原因

**直接回答**：

在现有框架下，切换RenderNodeGraph时PSO缓存无法保留的根本原因是：

**1. 技术实现限制**
- PSO缓存是`RenderNodeContextData`的子对象，销毁RenderNodeGraph时整个对象树被销毁
- 没有API或机制可以分离、提取、转移PSO缓存

**2. Vulkan平台限制**
- Vulkan要求PSO必须与RenderPass兼容
- WBOIT和普通渲染的RenderPass配置不同（attachment数量、格式）
- 即使相同的shader，在不同RenderNodeGraph中需要不同的PSO

**3. 设计理念限制**
- RenderNode接口设计要求每次初始化"starts from scratch"
- 架构设计假定RenderNodeGraph切换时清除所有状态
- 为了简化状态管理和内存管理

---

### 4.3 为什么设计上选择销毁而不是保留？

**设计权衡分析**：

| 选择销毁的优点 | 选择保留的缺点 |
|---------------|---------------|
| ✅ 避免RenderPass兼容性问题 | ❌ 需要处理跨RenderNodeGraph的缓存同步 |
| ✅ 简化状态管理 | ❌ 需要处理缓存失效和更新 |
| ✅ 内存管理清晰 | ❌ 需要引用计数或GC机制 |
| ✅ 支持动态RenderNodeGraph | ❌ 状态污染风险增加 |

**设计选择结论**：
- 现有框架选择了**简单、清晰、安全的设计**
- 牺牲了PSO缓存共享的性能优势
- 适合动态RenderNodeGraph场景

---

## 五、对比：不同平台的差异

### 5.1 Vulkan vs GL/GLES的PSO缓存机制

| 平台 | PSO缓存Key | RenderPass依赖 | 全局缓存可行性 |
|------|-----------|---------------|---------------|
| **Vulkan** | `Hash(handle.id, psoStateHash)` | **强依赖** | ❌ 困难（需要RenderPass兼容机制） |
| **GL/GLES** | `handle.id` | **无依赖** | ✅ 可行（理论上可以全局缓存） |

---

### 5.2 为什么GL/GLES也不全局缓存？

已在3.2节分析，GL/GLES的PSO哈希仅需`handle.id`（无RenderPass依赖），理论上可全局缓存。现有框架为保持跨平台一致性（统一状态管理、统一生命周期、简化维护），仍选择RenderNode级别缓存。

---

## 六、总结

### 6.1 核心结论

**在现有LumeRender框架下，切换RenderNodeGraph时PSO缓存无法保留的根本原因**：

| 原因 | 详细说明 |
|------|---------|
| **数据结构限制** | PSO缓存存储在`RenderNodeContextData`中，销毁RenderNodeGraph时一起销毁，无法分离 |
| **API限制** | 没有接口可以提取、转移或保留PSO缓存，无法在销毁前保留 |
| **Vulkan限制** | Vulkan要求PSO匹配RenderPass，不同的RenderNodeGraph（WBOIT vs 普通）需要不同的PSO |
| **设计理念** | RenderNode接口要求每次初始化"starts from scratch"，设计上假定切换时清除所有状态 |

---

### 6.2 如果要支持PSO缓存保留，需要什么？

**架构重构需求**：

| 需求 | 说明 |
|------|------|
| **全局PSO缓存池** | 将PSO缓存提升到Device或ShaderManager级别 |
| **RenderPass兼容机制** | 实现Vulkan的RenderPass兼容性检查或使用Pipeline Cache API |
| **缓存Key扩展** | 缓存Key需要包含RenderPass配置信息 |
| **引用计数管理** | 实现PSO的引用计数，避免过早销毁 |
| **状态失效机制** | 实现跨RenderNodeGraph的缓存失效通知 |

---

### 6.3 现有框架的设计选择总结

**设计哲学**：
- **简单优于复杂** - RenderNode级别缓存比全局缓存简单
- **清晰优于优化** - 生命周期管理清晰，避免状态污染
- **安全优于性能** - 避免RenderPass兼容性问题，避免内存泄漏

**适用场景**：
- ✅ 动态RenderNodeGraph创建/销毁
- ✅ 运行时切换渲染模式
- ✅ 多RenderNodeGraph并存

**不适用场景**：
- ❌ 高频繁切换RenderNodeGraph（性能开销大）
- ❌ 需要共享PSO的场景（内存浪费）

---

## 附录

### A. 关键代码位置索引

| 代码位置 | 功能 |
|---------|------|
| `render_node_graph_node_store.h:78-98` | RenderNodeContextData定义 |
| `node_context_pso_manager.h:115-166` | PipelineStateCache定义 |
| `node_context_pso_manager.cpp:62-77` | 哈希函数 |
| `node_context_pso_manager.cpp:262-337` | GetGraphicsPsoHandleImpl缓存查找 |
| `node_context_pso_manager.cpp:444-445` | Vulkan vs GL/GLES差异 |
| `render_node_graph_manager.cpp:387-421` | PendingDestroy销毁流程 |
| `render_node_graph_manager.cpp:276-334` | HandlePendingAllocations延迟销毁 |
| `renderer.cpp:130-186` | InitializeRenderNodeContextData初始化 |
| `intf_render_node.h:74-80` | InitNode设计说明 |

---

### B. 相关文档

- `Material与RenderSlot关联机制详解.md` - RenderSlot选择机制
- `InjectRenderNodes_解析文档.md` - RenderNode注入机制
- `OIT配置位置分析.md` - OIT配置管理
- `OIT_System_PRD.md` - OIT系统设计

---

### C. 术语表

| 术语 | 说明 |
|------|------|
| **PSO** | Pipeline State Object - 渲染管线状态对象 |
| **RenderNodeGraph** | 渲染节点图 - 定义渲染流程的DAG |
| **RenderNode** | 渲染节点 - 执行具体渲染任务的节点 |
| **RenderNodeContextData** | 渲染节点上下文数据 - 包含PSO管理器等 |
| **NodeContextPsoManager** | PSO管理器 - 创建和缓存PSO |
| **RenderPass** | 渲染Pass - Vulkan中的渲染过程定义 |
| **hashToHandle** | 哈希到Handle的映射 - PSO缓存的核心数据结构 |

---

**文档版本**: 1.0
**创建日期**: 2026-05-15
**作者**: Claude Analysis
**状态**: 完成
