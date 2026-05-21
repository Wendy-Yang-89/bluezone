# GL后端Subpass模拟机制详解

## 背景与问题引入

### RenderPass概念

**RenderPass** 是Vulkan渲染架构的核心概念，定义一次完整渲染操作的结构：

- **Attachments**：渲染使用的图像资源（颜色、深度等）
- **Subpasses**：渲染的阶段划分
- **Dependencies**：Subpass间的执行顺序和数据依赖

RenderPass使GPU能够优化渲染流程，减少不必要的内存访问。

### Subpass概念

**Subpass** 是RenderPass内的渲染阶段，具有以下特性：

- 同一RenderPass内的多个Subpass可共享Attachments
- Subpass间数据传递通过Input Attachment实现，无需显式拷贝
- GPU可在Tile-Based架构下保持数据在片上内存，避免写回系统内存

**典型应用：延迟渲染**

```
RenderPass: Deferred Rendering
  Subpass 0: G-Buffer Pass
    输出: depth, normal, albedo, specular (写入Attachments)
  
  Subpass 1: Lighting Pass
    输入: depth, normal, albedo, specular (Input Attachment引用)
    输出: final color
```

此架构下，G-Buffer数据无需写回系统内存，直接在片上供Lighting Pass使用。

### Attachment类型

**Attachment** 是RenderPass使用的图像资源：

| 类型 | 功能 | Vulkan特性 |
|------|------|-----------|
| **Color Attachment** | 存储颜色输出 | 可多个（MRT） |
| **Depth Attachment** | 存储深度值 | 用于深度测试 |
| **Stencil Attachment** | 存储模板值 | 用于模板测试 |
| **Input Attachment** | Subpass间数据传递 | 仅在Subpass内引用，零拷贝 |

Input Attachment是Vulkan特有的Subpass数据传递机制。

### Vulkan与OpenGL ES的差异

| 特性 | Vulkan | OpenGL ES |
|------|--------|-----------|
| **Subpass支持** | 内建，同一RenderPass内共享资源 | 无此概念 |
| **Input Attachment** | `subpassInput`类型，直接引用 | 需绑定为普通纹理 |
| **Attachment共享** | RenderPass内自动共享 | 需重新绑定FBO |
| **Tile内存优化** | 可保持数据在片上内存 | 无法利用此优化 |

**核心问题：OpenGL ES无Subpass概念，LumeRender需模拟实现Vulkan的Subpass架构。**

### GL模拟方案

LumeRender以Vulkan为设计基准，采用Subpass架构。GL后端需模拟实现：

- 每个Subpass创建独立FBO
- 重新绑定相同Attachments到新FBO
- Input Attachment绑定为普通纹理供Shader采样

**性能影响：**
- 额外FBO绑定开销
- 无法利用Tile-Based GPU的片上内存优化
- Input Attachment访问需纹理采样，而非零拷贝引用

---

## 核心概念

### FBO（Framebuffer Object）

**FBO** 是OpenGL ES的渲染目标容器，包含：

- **Color Attachments**：颜色输出缓冲（GL_COLOR_ATTACHMENT0~N）
- **Depth Attachment**：深度缓冲（GL_DEPTH_ATTACHMENT）
- **Stencil Attachment**：模板缓冲（GL_STENCIL_ATTACHMENT）

渲染前绑定FBO，GPU输出写入FBO的Attachments。

### GL模拟中的FBO-Subpass映射

GL后端模拟Subpass时：

- **每个Subpass对应一个独立FBO**
- Subpass切换时绑定新FBO
- 多个Subpass使用相同图像时，各FBO指向同一Attachment图像

```
Subpass 0:
  FBO_0 → Attachments: [depth_tex, color_tex_0, color_tex_1]

Subpass 1:
  FBO_1 → Attachments: [depth_tex, color_tex_0, color_tex_1]
  // 相同图像，不同FBO句柄
```

### Input Attachment模拟

Vulkan的Input Attachment允许Shader直接引用当前RenderPass内的Attachment：

```glsl
// Vulkan Shader
layout(input_attachment_index = 0, set = 0, binding = 0) uniform subpassInput inDepth;
float depth = subpassLoad(inDepth).r;
```

GL后端模拟方式：将Attachment绑定为普通纹理：

```glsl
// GL Shader（模拟）
uniform sampler2D inDepth;  // 绑定为纹理
float depth = texture(inDepth, uv).r;
```

**差异：纹理采样需要UV坐标，而subpassLoad自动使用当前像素位置。**

---

## 概述

### Input Attachment的处理

**Input Attachment** 是Vulkan特有的概念：读取当前RenderPass中其他Subpass输出的数据。

在GL中模拟：
- 将Color Attachment绑定为**纹理（Texture）**
- Shader通过 `sampler2D` 读取，而非Vulkan的 `subpassInput`

```glsl
// Vulkan Shader:
layout(input_attachment_index = 0) subpassInput inColor;

// GL Shader（模拟）:
uniform sampler2D inColor;  // 绑定为纹理
```

---

## 概述

本文档分析LumeRender GL后端的FBO管理和Subpass处理机制，包括FBO创建、attachment绑定、以及Subpass切换流程。

---

## 一、Subpass概念

### 1.1 Vulkan Subpass vs GL Backend

| 特性 | Vulkan | GL Backend |
|------|--------|------------|
| Subpass概念 | RenderPass内定义，共享资源 | 每个Subpass创建独立FBO |
| Attachment共享 | 可在同一RenderPass内共享 | 需要通过FBO重新绑定 |
| Input Attachment | 直接引用同一RenderPass的attachment | 需要绑定为纹理 |

### 1.2 WBOIT Render Node Graph示例

```json
{
    "attachments": [
        { "name": "depth" },      // attachment索引0
        { "name": "output" },     // attachment索引1
        { "name": "acc" },        // attachment索引2 (OIT accumulation)
        { "name": "rev" }         // attachment索引3 (OIT revealage)
    ],
    "subpassIndex": 2,
    "subpassCount": 3,
    "subpass": {
        "depthAttachmentIndex": 0,
        "colorAttachmentIndices": [ 2, 3 ]  // WBOIT输出到acc和rev
    }
}
```

---

## 二、FBO创建流程

### 2.1 GenerateSubPassFBO函数

```cpp
LowlevelFramebufferGL::Fbo GenerateSubPassFBO(...)
{
    // 1. 创建FBO
    GLuint fbo;
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);

    // 2. 绑定Depth Attachment
    if (sb.depthAttachmentIndex < images.size()) {
        BindToFbo(GL_DEPTH_ATTACHMENT, images[sb.depthAttachmentIndex], ...);
    }

    // 3. 绑定Color Attachments
    for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
        const uint32_t ci = sb.colorAttachmentIndices[idx];
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;  // 映射到连续的attachment
        BindToFbo(drawBuffers[idx], images[ci], ...);
    }

    // 4. 设置DrawBuffers
    glDrawBuffers(sb.colorAttachmentCount, drawBuffers);

    // 5. 验证FBO
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        PLUGIN_LOG_E("Failed to create subpass FBO");
        return { 0, 0 };
    }

    return { fbo, resolveFbo };
}
```

**关键文件：** `node_context_pool_manager_gles.cpp:422-488`

---

### 2.2 IsDefaultAttachment检查

```cpp
bool IsDefaultAttachment(array_view<const BindImage> images, const RenderPassSubpassDesc& sb)
{
    // 只有colorAttachmentCount == 1时才检查
    if (sb.colorAttachmentCount == 1) {
        if (const auto* color = images[sb.colorAttachmentIndices[0]].image) {
            const auto& plat = static_cast<const GpuImagePlatformDataGL&>(color->GetPlatformData());
            // image=0, renderBuffer=0 表示backbuffer
            if ((plat.image == 0) && (plat.renderBuffer == 0)) {
                return true;
            }
        }
    }
    return false;
}
```

**注意：** 如果返回true，会使用fbo=0（backbuffer），可能导致渲染到错误的target。

---

## 三、Subpass切换流程

### 3.1 DoSubPass函数

```cpp
void RenderBackendGLES::DoSubPass(uint32_t subPass)
{
    const auto& sb = activeRenderPass_.subpasses[subPass];

    // 1. 检查是否使用backbuffer
    if (!currentFrameBuffer_->fbos[subPass].fbo && (sb.colorAttachmentCount == 1U)) {
        auto color = rpd.attachmentHandles[sb.colorAttachmentIndices[0]];
        device_.Activate(color);  // 激活backbuffer
    }

    // 2. 绑定FBO
    device_.BindFrameBuffer(currentFrameBuffer_->fbos[subPass].fbo);

    // 3. 处理Attachment Clear
    if (!attachmentCleared_[index]) {
        HandleDepthAttachment(...);
        HandleColorAttachments(...);
        attachmentCleared_[index] = true;
    }
}
```

**关键文件：** `render_backend_gles.cpp:1395-1460`

---

### 3.2 FBO切换时的潜在问题

**问题1：FBO创建失败**
- `VerifyFBO()`返回false
- 返回`{ 0, 0 }`
- `BindFrameBuffer(0)`绑定到backbuffer

**问题2：Attachment Clear状态**
- `attachmentCleared_[index]`只记录是否cleared过
- 后续subpass不会再clear
- 如果FBO重建，depth/color内容可能错误

**问题3：Depth Attachment共享**
- 每个subpass使用独立FBO
- 但depth attachment应该共享
- 需要确保正确绑定同一depth texture

---

## 四、Color Attachment映射

### 4.1 Shader输出到FBO Attachment

| Shader输出 | Location | DrawBuffers映射 | 绑定的Image |
|-----------|----------|-----------------|-------------|
| accumulation | 0 | GL_COLOR_ATTACHMENT0 | images[2] (acc) |
| revealage | 1 | GL_COLOR_ATTACHMENT1 | images[3] (rev) |

**关键：** `colorAttachmentIndices`数组指定实际使用的attachment，`drawBuffers`映射到连续的GL attachment点。

### 4.2 代码实现

```cpp
for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
    const uint32_t ci = sb.colorAttachmentIndices[idx];  // 实际attachment索引
    drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;        // GL连续映射
    BindToFbo(drawBuffers[idx], images[ci], ...);
}
```

---

## 五、常见问题排查

### 5.1 渲染输出到错误的Target

**症状：** RenderDoc显示渲染到backbuffer而非OIT targets

**排查步骤：**
1. 检查`currentFrameBuffer_->fbos[subPass].fbo`是否为有效值（非0）
2. 检查`IsDefaultAttachment()`是否错误返回true
3. 检查`GenerateSubPassFBO()`是否成功

### 5.2 Depth内容错误

**症状：** 渲染后depth buffer值错误（如变成0）

**排查步骤：**
1. 检查每个subpass的depth attachment绑定是否正确
2. 检查depth clear状态（只cleared一次）
3. 检查是否有subpass使用了不同的FBO但共享同一depth

### 5.3 FBO验证失败

**症状：** `glCheckFramebufferStatus() != GL_FRAMEBUFFER_COMPLETE`

**常见原因：**
- Attachment格式不兼容
- Attachment尺寸不匹配
- Attachment未正确初始化

---

## 六、Depth处理特殊场景

### 6.1 天空盒Depth Write问题

**天空盒Shader State配置：**
```json
"depthStencilState": {
    "enableDepthTest": true,
    "enableDepthWrite": false,  // 不写入depth
    "depthCompareOp": "less_or_equal"
}
```

**问题：** 如果天空盒渲染时FBO的depth attachment不正确，可能导致depth值被破坏。

### 6.2 Subpass间Depth共享

**正确方式：**
- 所有subpass绑定同一depth texture
- 只有第一个subpass clear depth
- 后续subpass保持depth内容

**错误方式：**
- 每个subpass创建新depth attachment
- 导致depth内容丢失或不连续

---

## 七、关键文件索引

| 文件 | 功能 | 关键函数 |
|------|------|---------|
| `node_context_pool_manager_gles.cpp` | FBO管理 | `GenerateSubPassFBO()`, `ProcessSubPass()`, `IsDefaultAttachment()` |
| `render_backend_gles.cpp` | Subpass执行 | `DoSubPass()`, `BindFrameBuffer()` |
| `render_node_util.cpp` | RenderPass创建 | `CreateRenderPass()` |

---

## 八、实践经验

1. **多Subpass场景**：确保每个subpass的FBO正确创建，depth attachment共享
2. **OIT渲染**：WBOIT需要2个color output，确保`colorAttachmentIndices`正确映射
3. **调试FBO**：使用`glCheckFramebufferStatus()`验证，检查所有attachment绑定
4. **Intel GPU**：注意驱动可能对某些attachment组合不支持
