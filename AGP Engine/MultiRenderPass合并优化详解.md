# MultiRenderPass合并优化详解

## 背景与问题引入

### RenderPass与Subpass概念

**RenderPass（渲染通道）** 是Vulkan渲染架构的核心概念，定义一次完整渲染操作的结构：

- **Attachments**：渲染使用的图像资源（颜色、深度、模板）
- **Subpasses**：RenderPass内的渲染阶段划分
- **Load/Store Operations**：Attachment的生命周期管理

RenderPass使GPU能够优化渲染流程，减少不必要的内存访问。

### Subpass的优势

**Subpass** 是RenderPass内的渲染阶段，具有以下特性：

- 同一RenderPass内的多个Subpass可共享Attachments
- Subpass间通过Input Attachment传递数据，无需显式拷贝
- Tile-Based GPU可保持数据在片上内存，避免写回系统内存

Subpass切换比RenderPass切换更高效：

| 操作 | API调用 | GPU开销 |
|------|--------|--------|
| RenderPass切换 | `vkCmdBeginRenderPass` + `vkCmdEndRenderPass` | 较高（需重建状态） |
| Subpass切换 | `vkCmdNextSubpass` | 较低（状态延续） |

### 多RenderPass的性能问题

传统渲染流程可能包含多个独立RenderPass：

```
传统流程：
RenderPass 0 (几何渲染) → RenderPass 1 (光照计算) → RenderPass 2 (后处理)
每次切换：vkCmdBeginRenderPass → vkCmdEndRenderPass（重复调用）
```

性能开销：
- 多次GPU状态切换
- Attachment内容需在RenderPass间传递（显式拷贝）
- 无法利用Tile-Based GPU的片上内存优化

### 合并优化的目标

**MultiRenderPass合并优化** 将多个独立RenderPass合并为单个RenderPass：

```
优化流程：
RenderPass（合并后）：
  Subpass 0: 几何渲染
  Subpass 1: 光照计算
  Subpass 2: 后处理
单次调用：vkCmdBeginRenderPass → vkCmdNextSubpass → vkCmdEndRenderPass
```

优化效果：
- 减少API调用次数
- Attachment在Subpass间共享，无需显式拷贝
- 充分利用Tile-Based GPU优化

### 本文档解决的问题

本文档详细分析 `UpdateMultiRenderCommandListRenderPasses` 函数的实现：

- RenderPass合并的具体算法
- Attachment Load/Store操作的整合规则
- Subpass映射和状态同步机制

---

## 核心概念

### RenderPassDesc

**RenderPassDesc** 是RenderPass的描述结构：

| 字段 | 类型 | 作用 |
|------|------|------|
| `attachmentCount` | uint32 | Attachment数量 |
| `attachments` | array | Attachment描述数组 |
| `subpassCount` | uint32 | Subpass数量 |
| `subpasses` | array | Subpass描述数组 |

RenderPassDesc定义渲染操作的完整结构。

### AttachmentDescription

**AttachmentDescription** 定义单个Attachment的属性：

| 字段 | 作用 |
|------|------|
| `format` | 图像格式（如RGBA8、DEPTH24） |
| `sampleCount` | MSAA采样数 |
| `loadOp` | 开始时的操作（LOAD/CLEAR/DONT_CARE） |
| `storeOp` | 结束时的操作（STORE/DONT_CARE） |
| `initialLayout` | 开始时的图像布局 |
| `finalLayout` | 结束时的图像布局 |

LoadOp/StoreOp决定Attachment的生命周期管理。

### SubpassDescription

**SubpassDescription** 定义Subpass的输入输出：

| 字段 | 作用 |
|------|------|
| `colorAttachmentIndices` | 颜色输出Attachment索引 |
| `depthAttachmentIndex` | 深度Attachment索引 |
| `resolveAttachmentIndices` | 解析目标Attachment索引 |
| `inputAttachmentIndices` | 输入Attachment索引 |

Subpass通过索引引用RenderPass的Attachments。

### MultiRenderPassStore

**MultiRenderPassStore** 是LumeRender的多RenderPass容器：

```cpp
struct MultiRenderPassStore {
    vector<RenderCommandBeginRenderPass*> renderPasses;  // 待合并的RenderPass列表
};
```

此结构存储需要合并的多个RenderPass命令，供优化函数处理。

---

## 一、背景概念

### 1.1 RenderPass结构

**RenderPass（渲染通道）** 是图形渲染中的一个核心概念，代表一次完整的渲染操作周期。

**RenderPass组成元素：**

| 元素 | 说明 |
|------|------|
| **Attachments** | 渲染目标图像（颜色、深度、模板） |
| **Subpasses** | RenderPass内的渲染阶段 |
| **Load/Store Operations** | Attachment生命周期管理 |

**Attachment生命周期操作：**

| 操作 | 选项 | 说明 |
|------|------|------|
| **LoadOp** | LOAD/CLEAR/DONT_CARE | RenderPass开始时如何处理Attachment |
| **StoreOp** | STORE/DONT_CARE | RenderPass结束时如何处理Attachment |

---

### 1.2 Subpass优势

**Subpass（子通道）** 是RenderPass内的渲染阶段，允许多个渲染步骤共享同一个RenderPass。

**典型应用：延迟渲染**

| Subpass | 输入 | 输出 | 说明 |
|---------|------|------|------|
| Subpass 0 | 无 | Albedo, Normal, Depth | G-Buffer生成 |
| Subpass 1 | G-Buffer | 最终颜色 | 光照计算（InputAttachment引用） |
| Subpass 2 | 最终颜色 | 后处理结果 | 后处理效果 |

**Subpass性能优势：**
- 减少RenderPass切换开销
- InputAttachment复用，无需额外带宽
- Tile-Based GPU可保持数据在片上内存

---

### 1.3 MultiRenderPass优化机制

**MultiRenderPass（多渲染通道）** 是LumeRender的优化机制，将多个独立RenderPass合并为统一的RenderPass。

**传统流程（多RenderPass）：**

| 步骤 | RenderPass | API调用 |
|------|-----------|--------|
| 1 | 几何渲染 | vkCmdBeginRenderPass → vkCmdEndRenderPass |
| 2 | 光照计算 | vkCmdBeginRenderPass → vkCmdEndRenderPass |
| 3 | 后处理 | vkCmdBeginRenderPass → vkCmdEndRenderPass |

**优化流程（合并RenderPass）：**

| 步骤 | Subpass | API调用 |
|------|---------|--------|
| 1 | 几何渲染 | vkCmdBeginRenderPass（单次） |
| 2 | 光照计算 | vkCmdNextSubpass |
| 3 | 后处理 | vkCmdNextSubpass → vkCmdEndRenderPass |

---

## 二、函数作用

### 2.1 核心目的

`UpdateMultiRenderCommandListRenderPasses` 函数负责：

1. **合并多个 RenderPass** → 形成统一的 RenderPass 描述
2. **同步资源状态** → 所有 RenderPass 共享相同的附件状态视图
3. **Subpass 合并优化** → 减少 Vulkan API 调用次数
4. **整合 Load/Store 操作** → 从第一个取 Load，从最后一个取 Store

---

### 2.2 函数签名

```cpp
void UpdateMultiRenderCommandListRenderPasses(
    Device& device,                       // 设备对象（用于判断后端类型）
    RenderGraph::MultiRenderPassStore& store  // 多渲染通道存储结构
);
```

**MultiRenderPassStore 结构：**

```cpp
struct MultiRenderPassStore {
    vector<RenderCommandBeginRenderPass*> renderPasses;  // 多个 RenderPass 命令
};
```

---

## 三、函数执行流程详解

### 3.1 初始化和验证 (276-287)

```cpp
const auto renderPassCount = (uint32_t)store.renderPasses.size();
PLUGIN_ASSERT(renderPassCount > 1);  // 必须有多个 RenderPass 才需要合并

RenderCommandBeginRenderPass* firstRenderPass = store.renderPasses[0];
PLUGIN_ASSERT(firstRenderPass);
PLUGIN_ASSERT(firstRenderPass->subpasses.size() >= renderPassCount);  // 子通道数量足够

const RenderCommandBeginRenderPass* lastRenderPass = store.renderPasses[renderPassCount - 1];
PLUGIN_ASSERT(lastRenderPass);

const uint32_t attachmentCount = firstRenderPass->renderPassDesc.attachmentCount;
```

**作用：**
- 获取第一个和最后一个 RenderPass（用于提取 Load/Store 操作）
- 验证数据结构完整性
- 获取附件数量（用于后续循环）

---

### 3.2 同步资源状态 (293-307)

```cpp
// 将每个 RenderPass 的资源状态同步到所有其他 RenderPass
for (uint32_t fromRpIdx = 0; fromRpIdx < renderPassCount; ++fromRpIdx) {
    const auto& fromRenderPass = *(store.renderPasses[fromRpIdx]);
    const uint32_t fromRpSubpassStartIndex = fromRenderPass.subpassStartIndex;
    const auto& fromRpSubpassResourceStates = fromRenderPass.subpassResourceStates[fromRpSubpassStartIndex];

    for (uint32_t toRpIdx = 0; toRpIdx < renderPassCount; ++toRpIdx) {
        if (fromRpIdx != toRpIdx) {
            auto& toRenderPass = *(store.renderPasses[toRpIdx]);
            auto& toRpSubpassResourceStates = toRenderPass.subpassResourceStates[fromRpSubpassStartIndex];

            for (uint32_t idx = 0; idx < attachmentCount; ++idx) {
                toRpSubpassResourceStates.states[idx] = fromRpSubpassResourceStates.states[idx];
                toRpSubpassResourceStates.layouts[idx] = fromRpSubpassResourceStates.layouts[idx];
            }
        }
    }
}
```

**为什么需要同步？**

```
问题：每个 RenderPass 可能独立创建，各自维护资源状态视图
├── RenderPass 0 认为附件 A 在 layout X
├── RenderPass 1 认为附件 A 在 layout Y
└── 状态不一致会导致 Vulkan 验证错误或渲染问题

解决：同步所有 RenderPass 的资源状态视图
├── 所有 RenderPass 共享相同的 resourceStates
└── 确保 Vulkan 状态跟踪正确
```

**同步示意图：**

```
同步前：
RenderPass 0: { layout[0]=COLOR_ATTACHMENT, state[0]=READ_WRITE }
RenderPass 1: { layout[0]=SHADER_READ_ONLY, state[0]=READ }
RenderPass 2: { layout[0]=TRANSFER_SRC, state[0]=READ }

同步后：
RenderPass 0: { layout[0]=COLOR_ATTACHMENT, state[0]=READ_WRITE }
RenderPass 1: { layout[0]=COLOR_ATTACHMENT, state[0]=READ_WRITE }  ← 同步
RenderPass 2: { layout[0]=COLOR_ATTACHMENT, state[0]=READ_WRITE }  ← 同步
```

---

### 3.3 合并附件 Load/Store 操作 (309-317)

```cpp
// 从第一个取 LoadOp，从最后一个取 StoreOp
for (uint32_t idx = 0; idx < firstRenderPass->renderPassDesc.attachmentCount; ++idx) {
    firstRenderPass->renderPassDesc.attachments[idx].storeOp =
        lastRenderPass->renderPassDesc.attachments[idx].storeOp;
    firstRenderPass->renderPassDesc.attachments[idx].stencilStoreOp =
        lastRenderPass->renderPassDesc.attachments[idx].stencilStoreOp;

    firstRenderPass->imageLayouts.attachmentFinalLayouts[idx] =
        lastRenderPass->imageLayouts.attachmentFinalLayouts[idx];
}
```

**为什么从第一个取 Load，从最后一个取 Store？**

```
合并后的 RenderPass 生命周期：
┌───────────────────────────────────────────────────────┐
│ 合并后的 RenderPass                                    │
│                                                       │
│ 开始 ───────────────────────────────────────────── 结束│
│  │                                                 │  │
│  │ LoadOp（来自 RenderPass 0）                      │  │
│  │ ├── 保留/清空附件初始内容                         │  │
│  │                                                 │  │
│  │ Subpass 0, 1, 2... 执行渲染                      │  │
│  │                                                 │  │
│  │ StoreOp（来自最后一个 RenderPass）                │  │
│  │ ├── 保存/丢弃附件最终内容                         │  │
│  │                                                  │  │
│  │ FinalLayout（来自最后一个 RenderPass）            │  │
│  └── 附件在 RenderPass 结束后的布局                     │
└───────────────────────────────────────────────────────┘
```

**实际例子：**

```
原始配置：
├── RenderPass 0:
│   ├── LoadOp = CLEAR（清空颜色缓冲）
│   ├── StoreOp = DONT_CARE（不需要保存）
│   └── FinalLayout = COLOR_ATTACHMENT_OPTIMAL
│
├── RenderPass 1:
│   ├── LoadOp = LOAD（保留内容）
│   ├── StoreOp = DONT_CARE
│   └── FinalLayout = COLOR_ATTACHMENT_OPTIMAL
│
├── RenderPass 2（最后一个）:
│   ├── LoadOp = LOAD
│   ├── StoreOp = STORE（需要保存最终结果）
│   └── FinalLayout = SHADER_READ_ONLY_OPTIMAL（供后续读取）

合并后配置：
├── LoadOp = CLEAR（来自 RenderPass 0）
├── StoreOp = STORE（来自 RenderPass 2）
└── FinalLayout = SHADER_READ_ONLY_OPTIMAL（来自 RenderPass 2）
```

---

### 3.4 收集子通道到第一个 RenderPass (319-337)

```cpp
bool mergeSubpasses = false;
for (uint32_t idx = 1; idx < renderPassCount; ++idx) {
    if ((idx < store.renderPasses.size()) && (idx < store.renderPasses[idx]->subpasses.size())) {
        firstRenderPass->subpasses[idx] = store.renderPasses[idx]->subpasses[idx];

        if (firstRenderPass->subpasses[idx].subpassFlags & SubpassFlagBits::CORE_SUBPASS_MERGE_BIT) {
            mergeSubpasses = true;  // 标记需要合并优化
        }
    }
}

// 注意：目前仅在 Vulkan 中使用子通道合并
if (device.GetBackendType() != DeviceBackendType::VULKAN) {
    mergeSubpasses = false;
}
```

**Subpass 收集过程：**

```
原始分布：
├── RenderPass 0: subpasses[0] = { geometry rendering }
├── RenderPass 1: subpasses[1] = { lighting calculation }
├── RenderPass 2: subpasses[2] = { post-processing }

收集到第一个：
├── firstRenderPass->subpasses[0] = { geometry }
├── firstRenderPass->subpasses[1] = { lighting }  ← 从 RenderPass 1 复制
├── firstRenderPass->subpasses[2] = { post-processing }  ← 从 RenderPass 2 复制
```

**CORE_SUBPASS_MERGE_BIT 标志：**
- 表示该 Subpass 可以与前一个 Subpass 合并
- 合并后减少 `vkCmdNextSubpass()` 调用
- 仅 Vulkan 后端支持

---

### 3.5 Subpass 合并优化 (339-406)

```cpp
uint32_t subpassCount = renderPassCount;
if (mergeSubpasses) {
    PLUGIN_ASSERT(renderPassCount > 1U);

    // 从后向前合并
    const uint32_t finalSubpass = renderPassCount - 1U;
    uint32_t mergeCount = 0U;

    for (uint32_t idx = finalSubpass; idx > 0U; --idx) {
        if (firstRenderPass->subpasses[idx].subpassFlags & SubpassFlagBits::CORE_SUBPASS_MERGE_BIT) {
            uint32_t prevSubpassIdx = idx - 1U;
            auto& currSubpass = firstRenderPass->subpasses[idx];
            auto& prevSubpass = firstRenderPass->subpasses[prevSubpassIdx];

            // 检查合并条件
            if (currSubpass.inputAttachmentCount != prevSubpass.inputAttachmentCount) {
                // 不能合并：InputAttachment 数量不同
                currSubpass.subpassFlags &= ~SubpassFlagBits::CORE_SUBPASS_MERGE_BIT;
                continue;
            }

            if (prevSubpass.resolveAttachmentCount > currSubpass.resolveAttachmentCount) {
                // 不能合并：ResolveAttachment 数量不兼容
                currSubpass.subpassFlags &= ~SubpassFlagBits::CORE_SUBPASS_MERGE_BIT;
                continue;
            }

            mergeCount++;
            // 执行合并...
        }
    }

    subpassCount = subpassCount - mergeCount;
    firstRenderPass->renderPassDesc.subpassCount = subpassCount;
}
```

**为什么从后向前合并？**

```
合并策略：从后向前
├── Subpass 2 → 检查是否可以与 Subpass 1 合并
├── Subpass 1 → 检查是否可以与 Subpass 0 合并
└── 合并后调整 subpassStartIndex

优势：
├── 避免索引混乱（合并后索引减少）
├── 保持前向兼容性
```

**合并条件检查：**

| 条件 | 说明 |
|------|------|
| InputAttachment 数量相同 | InputAttachment 用于 Subpass 间数据传递，数量不同不能合并 |
| ResolveAttachment 兼容 | Resolve 用于 MSAA 解析，需要确保兼容性 |
| CORE_SUBPASS_MERGE_BIT 标志 | 必须标记为可合并 |

**合并示意图：**

```
合并前（3个 Subpass）：
┌─────────────────────────────────────┐
│ RenderPass                          │
│ ├── Subpass 0: Geometry             │
│ ├── Subpass 1: Lighting [MERGE_BIT] │
│ ├── Subpass 2: PostProcess          │
└─────────────────────────────────────┘
执行：vkCmdNextSubpass() × 2

合并后（2个 Subpass）：
┌─────────────────────────────────────┐
│ RenderPass                          │
│ ├── Subpass 0: Geometry + Lighting  │ ← 合并
│ ├── Subpass 1: PostProcess          │
└─────────────────────────────────────┘
执行：vkCmdNextSubpass() × 1

性能提升：减少一次 vkCmdNextSubpass() 调用
```

---

### 3.6 同步到所有 RenderPass (408-429)

```cpp
for (uint32_t idx = 1; idx < renderPassCount; ++idx) {
    auto& currRenderPass = store.renderPasses[idx];
    const uint32_t subpassStartIndex = currRenderPass->subpassStartIndex;  // 保留

    currRenderPass->renderPassDesc = firstRenderPass->renderPassDesc;  // 复制描述

    if (mergeSubpasses && (currRenderPass->subpasses[idx].subpassFlags & SubpassFlagBits::CORE_SUBPASS_MERGE_BIT)) {
        // 合并情况下复制资源状态
        currRenderPass->subpassResourceStates[subpassStartIndex] =
            firstRenderPass->subpassResourceStates[subpassStartIndex];
    }

    currRenderPass->subpassStartIndex = subpassStartIndex;  // 恢复索引
    currRenderPass->subpasses = firstRenderPass->subpasses;
    currRenderPass->inputResourceStates = firstRenderPass->inputResourceStates;
    currRenderPass->imageLayouts = firstRenderPass->imageLayouts;
}
```

**为什么需要同步？**

```
目的：所有 RenderPass 使用相同的合并后配置
├── 渲染命令执行时，每个 RenderPass 需要知道完整的 RenderPass 结构
├── 但每个 RenderPass 的 subpassStartIndex 不同（指示它从哪个 Subpass 开始）
└── 其他配置（renderPassDesc, subpasses, layouts）必须一致

示例：
├── RenderPass 0: subpassStartIndex = 0, renderPassDesc = merged
├── RenderPass 1: subpassStartIndex = 1（或 0 如果合并）, renderPassDesc = merged
├── RenderPass 2: subpassStartIndex = 2（或 1 如果合并）, renderPassDesc = merged
```

---

## 四、完整流程图

```plantuml
@startuml
title UpdateMultiRenderCommandListRenderPasses 流程

start

:获取 renderPassCount;
:获取 firstRenderPass 和 lastRenderPass;
:获取 attachmentCount;

partition "同步资源状态" {
    :遍历所有 RenderPass;
    :将每个 RenderPass 的资源状态;
    :同步到其他所有 RenderPass;
}

partition "合并 Load/Store 操作" {
    :从 firstRenderPass 取 LoadOp;
    :从 lastRenderPass 取 StoreOp;
    :从 lastRenderPass 取 FinalLayout;
}

partition "收集 Subpass" {
    :将所有 Subpass 收集到 firstRenderPass;
    :检查 CORE_SUBPASS_MERGE_BIT 标志;
    :如果非 Vulkan，禁用合并;
}

if (mergeSubpasses?) then (yes)
    partition "Subpass 合并优化" {
        :从后向前遍历;
        :检查合并条件;
        :InputAttachment 数量相同?;
        :ResolveAttachment 兼容?;
        :执行合并;
        :更新 subpassCount;
        :更新 subpassStartIndex;
    }
else (no)
endif

partition "同步到所有 RenderPass" {
    :将合并后的配置;
    :复制到所有 RenderPass;
    :保留各自的 subpassStartIndex;
}

stop

@enduml
```

---

## 五、性能优化效果

### 5.1 Vulkan API 调用减少

| 优化前 | 优化后 | 效果 |
|--------|--------|------|
| `vkCmdBeginRenderPass` × N | `vkCmdBeginRenderPass` × 1 | 减少 N-1 次 |
| `vkCmdEndRenderPass` × N | `vkCmdEndRenderPass` × 1 | 减少 N-1 次 |
| `vkCmdNextSubpass` × (N-1) | `vkCmdNextSubpass` × (合并后数量-1) | 进一步减少 |

### 5.2 内存带宽优化

```
Subpass InputAttachment 优势：
├── 同一 RenderPass 内的附件可直接作为 InputAttachment
├── 无需额外的内存带宽传输
├── GPU Tile Memory 可缓存附件数据
└── 对移动设备尤其重要
```

---

## 六、典型应用场景

### 6.1 延迟渲染

```
Subpass 0: G-Buffer 生成
├── 输出：Albedo, Normal, Depth, Material
└── 不需要输入

Subpass 1: 光照计算
├── 输入：Subpass 0 的 G-Buffer（作为 InputAttachment）
├── 输出：Lit Color
└── 可与 Subpass 0 合并（如果支持）

Subpass 2: 后处理
├── 输入：Subpass 1 的 Lit Color
└── 输出：最终结果
```

---

### 6.2 透明物体渲染

```
Subpass 0: 不透明物体
├── 输出：Opaque Color + Depth

Subpass 1: 透明物体（OIT）
├── 输入：Subpass 0 的 Depth
├── 输出：Transparent Color + A-Buffer
└── 不与 Subpass 0 合并（依赖 Depth）

Subpass 2: OIT 合成
├── 输入：Subpass 1 的 A-Buffer
└── 输出：最终透明结果
```

---

## 七、代码调用位置

**文件：** `submodules/LumeRender/src/render_graph.cpp:1028`

```cpp
void RenderGraph::Process()
{
    // ... 渲染图处理 ...

    if (stateCache.multiRenderPassStore.renderPasses.size() > 1) {
        UpdateMultiRenderCommandListRenderPasses(device_, stateCache.multiRenderPassStore);
    }

    // ... 后续处理 ...
}
```

---

## 八、版本历史

| 版本 | 日期 | 描述 |
|------|------|------|
| 1.0 | 2025-01-XX | 初始版本 |
| 1.1 | 2025-05-19 | 增加背景概念解释、流程图、应用场景 |

---

## 九、参考资料

| 文件 | 描述 |
|------|------|
| `src/render_graph.cpp` | RenderGraph 处理，调用此函数 |
| `api/render/device/intf_render_command_buffer.h` | RenderCommandBeginRenderPass 定义 |
| `api/render/device/intf_device.h` | DeviceBackendType 定义 |
| Vulkan Spec | RenderPass 和 Subpass 规范 |
