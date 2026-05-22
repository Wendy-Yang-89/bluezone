# GL后端MSAA WBOIT Resolve问题分析与修复方案

## 背景

MSAA Resolve是将多采样帧缓冲区（multisampled framebuffer）降采样为常规帧缓冲区的过程。Vulkan通过子流程（subpass）的解析附件（resolve attachment）在渲染流程结束时隐式完成，解析是渲染流程结构的一部分，而非独立操作；OpenGL ES则需要显式调用`glBlitFramebuffer`或使用`GL_EXT_multisampled_render_to_texture2`扩展。WBOIT管线对此尤为敏感——它同时使用两个颜色附件：累加缓冲区（accumulation，`r16g16b16a16_sfloat`）和揭示度缓冲区（revealage，`r16_unorm`），任一附件解析失败均会导致透明物体渲染错误。

## WBOIT与MSAA的关联

WBOIT管线的`core3d_rng_cam_scene_hdrp_msaa_wboit.rng`配置如下：

| 附件 | 格式 | 说明 |
|------|------|------|
| `acc_msaa` | `r16g16b16a16_sfloat` | 累加缓冲区（MSAA） |
| `rev_msaa` | `r16_unorm` | 揭示度缓冲区（MSAA） |
| `acc` | `r16g16b16a16_sfloat` | 累加解析目标 |
| `rev` | `r16_unorm` | 揭示度解析目标 |

子流程配置：`colorAttachmentIndices: [1, 2]`，`resolveAttachmentIndices: [3, 4]`。

累加缓冲区需要MSAA以保证透明物体边缘的抗锯齿质量；揭示度缓冲区使用`r16_unorm`格式——正是该格式在GL后端触发了下述bug。此配置在Vulkan后端工作正常，问题仅出现在GL后端。

## 问题描述

GL后端WBOIT管线中，`r16_unorm`格式的目标纹理在MSAA解析前后内容不一致。

## 根本原因分析

### 1. drawBuffers索引错误（高优先级）

**位置：** `node_context_pool_manager_gles.cpp:530`、`GenerateSubPassFBO`第440行

当前代码使用递增计数器构造`drawBuffers`索引，当附件中存在空图像（null image）时，计数器与实际附件位置产生偏移，导致错误的附件映射。

```cpp
// 当前代码（BUG）:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + rp.resolveAttachmentCount;
```

```cpp
// 修复后:
if (images[ci].image) {
    drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;
    BindToFbo(GL_COLOR_ATTACHMENT0 + idx, images[ci], ...);
    ++rp.resolveAttachmentCount;
} else {
    drawBuffers[idx] = GL_NONE;
}
```

**示例场景：** 颜色附件`[有效, 空, 有效]`，解析附件`[有效, 有效, 有效]`

- 颜色FBO：`GL_COLOR_ATTACHMENT0`→color[0]，`GL_COLOR_ATTACHMENT1`→color[2]（跳过空附件后压缩）
- 解析FBO：`GL_COLOR_ATTACHMENT0`→resolve[0]，`GL_COLOR_ATTACHMENT1`→resolve[1]，`GL_COLOR_ATTACHMENT2`→resolve[2]
- `glBlitFramebuffer`：color[2] → resolve[1] **错误**（应为 color[2] → resolve[2]）

**关键观察：** `InvalidateColor`函数（`render_backend_gles.cpp:1624`）使用`GL_COLOR_ATTACHMENT0 + ci`（循环索引），与`GenerateSubPassFBO`/`GenerateResolveFBO`的计数器方法不一致。但在当前计数器布局下，FBO实际附件位置是压缩的，`InvalidateColor`的索引式定位同样会错位——只有在修复计数器为`idx`后，两者才能同时正确。详见 `Potential Issues/drawBuffers配置错误详解.md`。

### 2. glBlitFramebuffer多附件行为（关键问题）

**位置：** `render_backend_gles.cpp:1666-1668`

根据GLES规范，`glBlitFramebuffer`使用`GL_COLOR_BUFFER_BIT`时，**只传输当前读取缓冲区**（默认`GL_COLOR_ATTACHMENT0`），不会自动解析所有颜色附件。

```cpp
// 当前代码（BUG）— 期望一次调用解析所有附件，实际只解析ATTACHMENT0:
glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, mask, GL_NEAREST);
```

代码第1661行注释已标注："NOTE: ARM recommends NOT to use glBlitFramebuffer here"。ARM Mali驱动在MSAA解析场景下对`glBlitFramebuffer`存在已知兼容性问题。

### 3. 格式回退问题

**位置：** `device_gles.cpp:572-573`

```cpp
// 当GL_EXT_texture_norm16不可用时，r16_unorm回退到半精度浮点:
{ BASE_FORMAT_R16_UNORM, GL_RED, GL_R16F, GL_HALF_FLOAT, 2, { false, 0, 0, 0 }, ... }
```

`r16_unorm`在缺少`GL_EXT_texture_norm16`扩展时映射到`GL_R16F` + `GL_HALF_FLOAT`。源和目标使用相同回退格式，源/目标间格式不匹配的可能性较低，但shader输出`float`与纹理期望`half_float`的解释差异仍可能导致精度损失。

### 4. Vulkan与GL对比

| 方面 | Vulkan | OpenGL ES |
|------|--------|-----------|
| **解析机制** | 子流程解析附件自动解析（隐式），解析是渲染流程结构的一部分 | 显式`glBlitFramebuffer`或`GL_EXT_multisampled_render_to_texture2` |
| **解析时机** | 子流程结束时自动执行 | 手动在EndRenderPass时执行 |
| **格式验证** | 渲染流程创建时验证层检查 | 仅运行时FBO完整性检查 |
| **深度解析** | `VK_KHR_depth_stencil_resolve`扩展 | `GL_EXT_multisampled_render_to_texture2` + `allowDepthResolve`配置 |
| **多颜色附件** | `VkSubpassDescription`中`colorAttachments`与`resolveAttachments`一一对应的并行数组，驱动同时处理所有映射 | `GenerateResolveFBO`中逐个迭代，但单次`glBlitFramebuffer`只处理一个读取缓冲区 |
| **帧缓冲设置** | 单一帧缓冲包含所有附件 | 分离FBO：主FBO + 解析FBO |
| **错误处理** | 验证层早期捕获 | `glCheckFramebufferStatus`运行时检查；可能静默失败 |

**Vulkan正确流程：**
```cpp
subpass.colorAttachments = [color0, color1, color2]
subpass.resolveAttachments = [resolve0, resolve1, resolve2]
// 驱动在子流程结束时自动执行 color[i] -> resolve[i]
```

**GL问题流程：**
- 创建独立的解析FBO
- 单次`glBlitFramebuffer`调用
- GL规范不保证一次调用处理多附件解析

## 修复方案

### 修复1：drawBuffers索引修正

**文件：** `node_context_pool_manager_gles.cpp`

**修改1（第530行 — GenerateResolveFBO）：**
```cpp
// 当前代码（BUG）:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + rp.resolveAttachmentCount;
BindToFbo(drawBuffers[idx], images[ci], ...);
++rp.resolveAttachmentCount;

// 修复后:
if (images[ci].image) {
    drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;
    BindToFbo(GL_COLOR_ATTACHMENT0 + idx, images[ci], framebuffer.width, framebuffer.height, views, (idx > 0));
    ++rp.resolveAttachmentCount;
} else {
    drawBuffers[idx] = GL_NONE;
}
```

**修改2（第440行 — GenerateSubPassFBO）：**
```cpp
// 当前代码（BUG）:
drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + colorAttachmentCount;
BindToFbo(...);
++colorAttachmentCount;

// 修复后:
if (images[ci].image) {
    drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;
    BindToFbo(GL_COLOR_ATTACHMENT0 + idx, images[ci], ...);
    ++colorAttachmentCount;
} else {
    drawBuffers[idx] = GL_NONE;
}
```

### 修复2：逐附件MSAA解析

**文件：** `render_backend_gles.cpp`

**函数：** `ResolveMSAA`（第1647-1706行）

```cpp
uint32_t RenderBackendGLES::ResolveMSAA(const RenderPassDesc& rpd, const RenderPassSubpassDesc& currentSubPass)
{
    if (scissorEnabled_) {
        glDisable(GL_SCISSOR_TEST);
        scissorEnabled_ = false;
    }

    if (!currentSubPass.viewMask) {
        device_.BindReadFrameBuffer(currentFrameBuffer_->fbos[currentSubPass_].fbo);
        device_.BindWriteFrameBuffer(currentFrameBuffer_->fbos[currentSubPass_].resolve);

        // 修复后：显式逐附件解析
        for (uint32_t idx = 0; idx < currentSubPass.resolveAttachmentCount; ++idx) {
            glReadBuffer(GL_COLOR_ATTACHMENT0 + idx);
            glBlitFramebuffer(0, 0, width, height, 0, 0, width, height,
                              GL_COLOR_BUFFER_BIT, GL_NEAREST);
        }

        if (currentSubPass.depthResolveAttachmentCount > 0) {
            glBlitFramebuffer(0, 0, width, height, 0, 0, width, height,
                              GL_DEPTH_BUFFER_BIT, GL_NEAREST);
        }
    } else {
        // ... 现有viewMask处理逻辑 ...
    }
    return GL_READ_FRAMEBUFFER;
}
```

**替代方案：** 性能敏感场景优先使用`GL_EXT_multisampled_render_to_texture2`路径。

### 修复3：格式验证增强

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

| 优先级 | 修复阶段 | 预期影响 |
|--------|----------|----------|
| 1 | 修复1（drawBuffers修正） | 高 — 修复错误的附件映射 |
| 2 | 修复2（逐附件解析） | 关键 — 使多附件解析正常工作 |
| 3 | 修复3（验证增强） | 中等 — 早期捕获格式错误 |

## 实施建议

### 测试验证

| 测试项 | 目的 | 风险级别 | 缓解措施 |
|--------|------|----------|----------|
| 混合空附件渲染流程 | 验证drawBuffers索引修正 | 低 — 简单逻辑修改 | 现有测试覆盖 |
| 强制`GL_EXT_texture_norm16`不可用 | 验证格式回退路径 | 低 — 仅诊断，无功能影响 | 无 |
| 多附件WBOIT场景 | 验证acc和rev均正确解析 | 中等 — 改变解析行为 | 多种附件配置测试 |
| ARM Mali GPU | 验证替代解析方法兼容性 | 中等 — Mali驱动已知问题 | `GL_EXT_multisampled_render_to_texture2`路径 |

### 需修改的文件

| 文件 | 行号 | 修改内容 |
|------|------|----------|
| `node_context_pool_manager_gles.cpp` | 530, 440 | 修复drawBuffers索引 |
| `render_backend_gles.cpp` | 1662-1706 | 实现逐附件解析 |
| `device_gles.cpp` | （可选） | 添加格式验证日志 |

## 参考资料

- OpenGL ES 3.0规范：`glBlitFramebuffer`行为
- ARM Mali最佳实践：避免使用`glBlitFramebuffer`进行MSAA解析
- Vulkan规范：子流程解析附件要求
