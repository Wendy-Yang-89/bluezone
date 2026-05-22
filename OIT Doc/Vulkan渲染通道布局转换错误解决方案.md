# Vulkan 渲染通道布局转换错误解决方案

## 背景

在 Vulkan 中，图像布局（Image Layout）描述了 GPU 内存中图像数据的排列方式，不同的使用场景（深度写入、着色器采样、颜色输出等）要求不同的内存布局以获得最佳性能。与 OpenGL 自动管理布局转换不同，Vulkan 要求开发者显式声明每个渲染通道附件的初始布局和最终布局，由驱动在通道边界插入隐式转换屏障。

VUID-vkCmdBeginRenderPass-initialLayout-00900 验证错误即源于此机制：渲染通道描述中的 `initialLayout` 必须与图像当前的实际布局一致，否则验证层将报错。深度附件尤其容易触发此错误，因为同一深度图像常在不同渲染通道中交替用作深度模板附件（需 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`）和输入附件（需 `DEPTH_STENCIL_READ_ONLY_OPTIMAL`），若通道间缺少正确的布局转换，即产生布局不匹配。

## 错误信息

```
VUID-vkCmdBeginRenderPass-initialLayout-00900: 
pCreateInfo->pAttachments[0] 初始布局: VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL
附件当前布局: VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL
```

## 问题分析

### 场景描述
1. **第一个渲染通道**：深度附件作为**深度模板附件**（读写）
   - 布局：`VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL`

2. **第二个渲染通道**：同一个深度附件作为**输入附件**（只读）
   - 初始布局：`VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL`
   - 当前布局：`VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL`（来自第一个渲染通道）

3. **问题**：两个渲染通道之间缺少布局转换屏障

---

## 解决方案

### 方案 1：匹配前一个渲染通道的最终布局（推荐）

确保第一个渲染通道的最终布局与第二个渲染通道的初始布局一致。

**原理**：Vulkan 在渲染通道结束时会自动插入一个隐式转换屏障，将附件从当前布局转换到 `finalLayout` 指定的布局。因此，将第一个渲染通道的 `finalLayout` 设为 `DEPTH_STENCIL_READ_ONLY_OPTIMAL`，通道结束时驱动会自动完成布局转换，后续通道的 `initialLayout` 即可匹配。

#### 检查渲染节点配置

在渲染节点中，深度附件的最终布局通常由引擎自动管理。检查以下配置：

```cpp
// 在 ProcessDepthAttachments 中（render_command_list.cpp:1154）
subpassResourceStates.layouts[attachmentIndex] = CORE_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;
```

#### 修改渲染通道描述

如果深度附件在后续渲染通道中作为输入附件使用，设置正确的最终布局：

```cpp
// 在渲染节点中
RenderPassDesc::AttachmentDesc depthDesc = {
    .loadOp = CORE_ATTACHMENT_LOAD_OP_CLEAR,
    .storeOp = CORE_ATTACHMENT_STORE_OP_DONT_CARE,
    .stencilLoadOp = CORE_ATTACHMENT_LOAD_OP_DONT_CARE,
    .stencilStoreOp = CORE_ATTACHMENT_STORE_OP_DONT_CARE,
    .initialLayout = CORE_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
    .finalLayout = CORE_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL,  // 设置为只读布局
};
```

---

### 方案 2：使用 UNDEFINED 初始布局

如果不需要保留深度缓冲区内容，使用 `VK_IMAGE_LAYOUT_UNDEFINED`：

```cpp
RenderPassDesc::AttachmentDesc depthDesc = {
    .initialLayout = CORE_IMAGE_LAYOUT_UNDEFINED,  // 不检查当前布局
    .finalLayout = CORE_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
};
```

**警告**：`UNDEFINED` 布局会**销毁图像中的原有内容**。仅当后续操作会清除（`LOAD_OP_CLEAR`）附件，或明确不需要之前的深度数据时，方可安全使用。若依赖 `LOAD_OP_LOAD` 加载先前内容，则不可使用此方案。

---

### 方案 3：添加显式布局转换屏障（Lume 引擎推荐方案）

在两个渲染通道之间添加显式布局转换屏障。这是 Lume 引擎中最正确的方案，因为渲染图应负责管理通道间的屏障，而非依赖隐式转换。

使用引擎 API `CustomImageBarrier`（声明于 `submodules/LumeRender/api/render/nodecontext/intf_render_command_list.h:265`）：

```cpp
// 在第一个渲染通道结束后、第二个渲染通道开始前
const ImageResourceBarrier srcBarrier = {
    .accessFlags = CORE_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT,
    .pipelineStageFlags = CORE_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT,
    .imageLayout = CORE_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
};
const ImageResourceBarrier dstBarrier = {
    .accessFlags = CORE_ACCESS_SHADER_READ_BIT,
    .pipelineStageFlags = CORE_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
    .imageLayout = CORE_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL,
};
CustomImageBarrier(depthImageHandle, srcBarrier, dstBarrier, imageSubresourceRange);
```

---

### 方案 4：禁用深度附件输入（权宜之计）

如果不需要深度附件作为输入，移除输入附件引用：

```cpp
// 错误：深度附件同时用作深度和输入
subpassDesc.depthAttachmentIndex = 0;
subpassDesc.inputAttachmentIndices[0] = 0;  // 冲突

// 正确：仅用作深度附件
subpassDesc.depthAttachmentIndex = 0;
// 不设置 inputAttachmentIndices
```

**注意**：此方案是规避而非修复——移除输入附件意味着着色器中无法读取深度值。若渲染逻辑依赖深度输入（如 SSAO、软粒子等），则不可使用此方案。

---

## 引擎渲染图的布局管理

Lume 引擎的渲染图（`render_graph.cpp`）负责在渲染通道之间自动插入布局转换屏障。当出现 VUID-vkCmdBeginRenderPass-initialLayout-00900 错误时，通常意味着自动屏障机制存在遗漏，原因一般为：

1. **渲染节点未正确声明深度附件的使用方式** — 若节点将深度附件声明为深度模板附件，但未声明其同时作为输入附件使用，渲染图无法感知后续通道需要只读布局，因而不会插入相应的转换屏障。

2. **渲染图的屏障插入逻辑存在间隙** — 渲染图在布局更新和屏障插入时，依赖各节点声明的附件状态。若节点声明的状态与实际使用不一致，屏障可能被跳过或以错误的源布局插入。

关键代码位置：

| 功能 | 文件 | 行号 |
|------|------|------|
| 附件布局状态更新 | `submodules/LumeRender/src/render_graph.cpp` | 1130-1162 |
| 渲染通道屏障插入 | `submodules/LumeRender/src/render_graph.cpp` | 1467-1481 |

其中布局更新逻辑（:1130-1162）根据附件描述和当前状态计算 `initialImageLayouts` 和 `finalImageLayouts`；屏障插入逻辑（:1467-1481）遍历子通道的附件引用，为每个附件生成 `CommandBarrier` 以完成布局转换。若节点的附件声明不完整，这两段逻辑均无法正确工作。

---

## 推荐修复策略

```
需要保留深度内容？
├─ 是 → 同一渲染通道内使用？
│       ├─ 是 → 方案4（深度+输入附件同时使用，subpass内自动同步）
│       └─ 否 → 方案3（显式屏障，或方案1设置finalLayout）
└─ 否 → 方案2（UNDEFINED布局）
```

**方案选择说明**：

| 条件 | 推荐方案 | 理由 |
|------|---------|------|
| 不同通道间需要保留深度且需读取 | 方案3 | 渲染图应管理屏障，显式屏障最可控 |
| 不同通道间需要保留深度但不需读取 | 方案1 | 利用 Vulkan 隐式转换，改动最小 |
| 同一通道内同时用作深度和输入 | 方案4 | subpass 内附件自动同步，无布局冲突 |
| 不需要保留深度内容 | 方案2 | 最简单，但会丢弃数据 |

---

## 代码位置

- 深度附件布局设置：`submodules/LumeRender/src/nodecontext/render_command_list.cpp:1154`
- 输入附件布局设置：`submodules/LumeRender/src/nodecontext/render_command_list.cpp:1063-1065`
- 布局更新函数：`submodules/LumeRender/src/render_graph.cpp:1130-1162`
- 屏障插入函数：`submodules/LumeRender/src/render_graph.cpp:1417-1481`
- 显式屏障 API：`submodules/LumeRender/api/render/nodecontext/intf_render_command_list.h:265`

---

## 调试步骤

1. **启用验证日志**：
   ```bash
   export VK_LAYER_PATH=/path/to/vulkan/layers
   export VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation
   ```

2. **检查渲染通道配置**：
   - 查看哪些渲染节点使用深度附件
   - 确认深度附件的使用顺序

3. **验证布局转换**：
   - 使用 RenderDoc 或 Vulkan 验证层查看布局转换
   - 确认每个渲染通道的初始/最终布局

---

## 常见布局转换

| 用途 | 初始布局 | 最终布局 |
|------|---------|---------|
| 深度写入 | `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` |
| 深度读取 | `DEPTH_STENCIL_READ_ONLY_OPTIMAL` | `DEPTH_STENCIL_READ_ONLY_OPTIMAL` |
| 写入后读取 | `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | `DEPTH_STENCIL_READ_ONLY_OPTIMAL` |
| 采样器使用 | `SHADER_READ_ONLY_OPTIMAL` | `SHADER_READ_ONLY_OPTIMAL` |
