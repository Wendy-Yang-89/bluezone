# GL后端FBO与Subpass处理详解

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