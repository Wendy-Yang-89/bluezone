# GL后端MSAA WBOIT Resolve问题详解

## 背景

MSAA Resolve是将多采样帧缓冲区降采样为常规帧缓冲区的过程。Vulkan通过子流程的解析附件在渲染流程结束时隐式完成；OpenGL ES则需要显式调用`glBlitFramebuffer`或使用`GL_EXT_multisampled_render_to_texture2`扩展。WBOIT管线对此尤为敏感——它同时使用两个颜色附件：累加缓冲区（accumulation，`r16g16b16a16_sfloat`）和揭示度缓冲区（revealage，`r16_unorm`），任一附件解析失败均会导致透明物体渲染错误。

## WBOIT与MSAA的关联

WBOIT管线的`core3d_rng_cam_scene_hdrp_msaa_wboit.rng`配置如下：

| 附件 | 格式 | 说明 |
|------|------|------|
| `acc_msaa` | `r16g16b16a16_sfloat` | 累加缓冲区（MSAA） |
| `rev_msaa` | `r16_unorm` | 揭示度缓冲区（MSAA） |
| `acc` | `r16g16b16a16_sfloat` | 累加解析目标 |
| `rev` | `r16_unorm` | 揭示度解析目标 |

子流程配置：`colorAttachmentIndices: [1, 2]`，`resolveAttachmentIndices: [3, 4]`。

此配置在Vulkan后端工作正常，问题仅出现在GL后端。

## 问题描述

GL后端WBOIT管线中，`r16_unorm`格式的揭示度缓冲区在MSAA解析前后内容不一致。

## 问题分析

### 1. drawBuffers索引错误（影响空图像场景）

**位置：** `node_context_pool_manager_gles.cpp:440`、`node_context_pool_manager_gles.cpp:530`

当附件中存在空图像（null image）时，计数器与循环索引产生偏移，导致FBO颜色附件位置被压缩。详见 `Potential Issues/FBO颜色附件位置映射错误详解.md`。

**对WBOIT的影响**：标准WBOIT配置中所有颜色和解析图像均有效，计数器与索引一致，此bug不触发。仅当WBOIT管线中存在空附件时才受影响。

### 2. MSAA Resolve路径分析

**位置：** `render_backend_gles.cpp:1705`（`ResolveMSAA`）

引擎已实现两种resolve路径：

| 条件 | 路径 | 行号 | 机制 |
|------|------|------|------|
| `resolveAttachmentCount <= 1` | 单附件blit | 1726-1728 | 使用预构建FBO，单次`glBlitFramebuffer` |
| `resolveAttachmentCount > 1` | 多附件逐个blit | 调用`ResolveMSAAMultiColor`（:1647） | 创建临时FBO对，逐附件绑定到ATT0后blit |

代码注释（第1733-1734行）已明确说明：
> glBlitFramebuffer only resolves the currently selected read/draw color buffer pair, so multi-color-attachment resolves must walk the attachments and blit them one at a time.

**`ResolveMSAAMultiColor`（:1647）的实现**：

```cpp
// 创建临时FBO对，每个附件单独绑定到ATT0后blit
for (uint32_t idx = 0U; idx < currentSubPass.resolveAttachmentCount; ++idx) {
    // 将src color[idx]绑定到临时READ_FBO的ATT0
    glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, ..., srcPlat.image, 0);
    // 将dst resolve[idx]绑定到临时DRAW_FBO的ATT0
    glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, ..., dstPlat.image, 0);
    // 单附件blit — 此时ATT0即目标，无需glReadBuffer
    glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
}
```

**对WBOIT的影响**：WBOIT有2个解析附件（`resolveAttachmentCount > 1`），走`ResolveMSAAMultiColor`路径。该路径创建独立临时FBO，逐附件绑定到`GL_COLOR_ATTACHMENT0`后blit，**不依赖**预构建FBO的布局（不受drawBuffers bug影响）。resolve路径本身正确。

### 3. 格式回退问题（最可能的WBOIT根因）

**位置：** `device_gles.cpp:572-573`

```cpp
// 当GL_EXT_texture_norm16不可用时，r16_unorm回退到半精度浮点:
{ BASE_FORMAT_R16_UNORM, GL_RED, GL_R16F, GL_HALF_FLOAT, 2, { false, 0, 0, 0 },
    { GL_RED, GL_GREEN, GL_BLUE, GL_ALPHA } },
```

`r16_unorm`在缺少`GL_EXT_texture_norm16`扩展时映射到`GL_R16F` + `GL_HALF_FLOAT`。源和目标使用相同回退格式，格式不匹配的可能性较低，但shader输出`float`与纹理期望`half_float`的解释差异仍可能导致精度损失。

### 4. Vulkan与GL对比

| 方面 | Vulkan | OpenGL ES |
|------|--------|-----------|
| **解析机制** | 子流程解析附件自动解析（隐式） | 显式`glBlitFramebuffer`或`GL_EXT_multisampled_render_to_texture2` |
| **解析时机** | 子流程结束时自动执行 | 手动在EndRenderPass时执行 |
| **格式验证** | 渲染流程创建时验证层检查 | 仅运行时FBO完整性检查 |
| **深度解析** | `VK_KHR_depth_stencil_resolve`扩展 | `GL_EXT_multisampled_render_to_texture2` + `allowDepthResolve`配置 |
| **多颜色附件** | `VkSubpassDescription`中`colorAttachments`与`resolveAttachments`一一对应，驱动同时处理 | `ResolveMSAAMultiColor`逐附件创建临时FBO对，逐个blit |
| **帧缓冲设置** | 单一帧缓冲包含所有附件 | 分离FBO：主FBO + 解析FBO |
| **错误处理** | 验证层早期捕获 | `glCheckFramebufferStatus`运行时检查；可能静默失败 |

**Vulkan正确流程：**
```cpp
subpass.colorAttachments = [color0, color1]
subpass.resolveAttachments = [resolve0, resolve1]
// 驱动在子流程结束时自动执行 color[i] -> resolve[i]
```

**GL正确流程（当前代码已实现）：**
```cpp
// resolveAttachmentCount > 1 时
ResolveMSAAMultiColor(rpd, currentSubPass);
// 内部：逐附件创建临时FBO对，绑定到ATT0后blit

// 随后单独处理深度
if (depthResolveAttachmentCount > 0)
    glBlitFramebuffer(..., GL_DEPTH_BUFFER_BIT, GL_NEAREST);
```

## 修复方案

### 修复1：drawBuffers索引修正（影响空图像场景）

**文件：** `node_context_pool_manager_gles.cpp`

**修改1（第440行 — GenerateSubPassFBO）：**
```cpp
// 当前代码（BUG）:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + colorAttachmentCount;

// 修复后:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;
```

**修改2（第530行 — GenerateResolveFBO）：**
```cpp
// 当前代码（BUG）:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + rp.resolveAttachmentCount;

// 修复后:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;
```

> 注意：`colorAttachmentCount`和`rp.resolveAttachmentCount`修复后仍保留递增逻辑，因为它们在其他上下文中有实际用途，只是不应再决定attachment位置。详见 `Potential Issues/FBO颜色附件位置映射错误详解.md`。

### 修复2：格式验证增强

**文件：** `node_context_pool_manager_gles.cpp` 或 `render_backend_gles.cpp`

```cpp
// 解析前验证格式兼容性
for (uint32_t idx = 0; idx < currentSubPass.resolveAttachmentCount; ++idx) {
    const uint32_t colorIdx = currentSubPass.colorAttachmentIndices[idx];
    const uint32_t resolveIdx = currentSubPass.resolveAttachmentIndices[idx];

    const auto* srcImage = gpuResourceMgr_.GetImage(rpd.attachmentHandles[colorIdx]);
    const auto* dstImage = gpuResourceMgr_.GetImage(rpd.attachmentHandles[resolveIdx]);

    if (srcImage && dstImage) {
        if (srcImage->GetDesc().format != dstImage->GetDesc().format) {
            PLUGIN_LOG_W("MSAA解析格式不匹配：color[%u]=%u vs resolve[%u]=%u",
                         colorIdx, srcImage->GetDesc().format,
                         resolveIdx, dstImage->GetDesc().format);
        }
    }
}
```

## 实施优先级

| 优先级 | 修复阶段 | 预期影响 | 适用场景 |
|--------|----------|----------|----------|
| 1 | 修复1（drawBuffers修正） | 高 — 修复空图像时附件映射错位 | 存在空附件的渲染流程 |
| 2 | 修复2（格式验证） | 中等 — 早期捕获格式错误 | r16_unorm格式回退场景 |

## 实施建议

### 测试验证

| 测试项 | 目的 | 风险级别 |
|--------|------|----------|
| 混合空附件渲染流程 | 验证drawBuffers索引修正 | 低 |
| 强制`GL_EXT_texture_norm16`不可用 | 验证格式回退路径 | 低 |
| 多附件WBOIT场景 | 验证acc和rev均正确解析 | 中等 |
| ARM Mali GPU | 验证替代解析方法兼容性 | 中等 |

### 需修改的文件

| 文件 | 行号 | 修改内容 |
|------|------|----------|
| `node_context_pool_manager_gles.cpp` | 440, 530 | 修复drawBuffers索引 |
| `device_gles.cpp` | （可选） | 添加格式验证日志 |

## 参考资料

- OpenGL ES 3.0规范：`glBlitFramebuffer`行为
- ARM Mali最佳实践：避免使用`glBlitFramebuffer`进行MSAA解析（代码注释见`render_backend_gles.cpp:1719`）
- Vulkan规范：子流程解析附件要求
