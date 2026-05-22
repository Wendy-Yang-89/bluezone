# drawBuffers配置错误详解

## 背景知识

在OpenGL中，FBO（Framebuffer Object）的颜色附件（Color Attachment）是渲染输出的目标槽位，以`GL_COLOR_ATTACHMENT0`、`GL_COLOR_ATTACHMENT1`...依次编号。`glDrawBuffers`函数将片元着色器的输出变量（`fragColor[0]`、`fragColor[1]`...）映射到这些附件槽位，决定了每个shader output写入哪个attachment point。两者之间存在严格的对应关系要求：shader输出`color[i]`应绑定到`GL_COLOR_ATTACHMENTi`，这对于`glBlitFramebuffer`、`glClearBufferfv`、`glInvalidateFramebuffer`等按attachment位置操作的GL命令至关重要。在MSAA resolve流程中，resolve操作依赖颜色FBO与解析FBO之间attachment位置的一一匹配，位置错位将导致数据写入错误的目标。

## 问题核心

在`GenerateSubPassFBO`和`GenerateResolveFBO`函数中，使用计数器（`colorAttachmentCount`或`resolveAttachmentCount`）而非循环索引（`idx`）来设置GL attachment位置，导致当存在空图像时，attachment编号被压缩，进而破坏了按位置索引操作的GL命令与实际绑定图像之间的对应关系。

## 代码分析

### GenerateSubPassFBO（`node_context_pool_manager_gles.cpp:422`，bug at line 440）

```cpp
for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
    const uint32_t ci = sb.colorAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + colorAttachmentCount;  // ← 使用计数器
        const uint32_t original = imageMap[ci];
        if (original == EMPTY_ATTACHMENT) {
            BindToFbo(drawBuffers[idx], images[ci], ...);
        } else {
            BindToFboMultisampled(drawBuffers[idx], images[original], images[ci], ...);
        }
        ++colorAttachmentCount;
    } else {
        drawBuffers[idx] = GL_NONE;
    }
}
```

> 注意：两个绑定路径（`BindToFbo`和`BindToFboMultisampled`）均使用`drawBuffers[idx]`作为attachment位置，因此修复时两者同时生效。

### GenerateResolveFBO（`node_context_pool_manager_gles.cpp:495`，bug at line 530）

```cpp
for (uint32_t idx = 0; idx < sb.resolveAttachmentCount; ++idx) {
    const uint32_t ci = sb.resolveAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + rp.resolveAttachmentCount;  // ← 使用计数器
        BindToFbo(drawBuffers[idx], images[ci], ...);
        ++rp.resolveAttachmentCount;
    } else {
        drawBuffers[idx] = GL_NONE;
    }
}
```

### 附加上下文：MapColorAttachments / UpdateSubpassAttachments

`MapColorAttachments`（`node_context_pool_manager_gles.cpp:594`）在`GL_EXT_multisampled_render_to_texture`扩展激活时，会对附件索引进行重映射，修改`resolveAttachmentIndices`的内容。这决定了FBO生成阶段哪些`images[ci]`为空（null），从而影响计数器的递增模式。

## 实际影响分析

### glBlitFramebuffer并非受影响路径

当前代码的MSAA resolve逻辑分为两种情况：

- **单附件resolve**（`resolveAttachmentCount <= 1`）：仅从当前read buffer（ATT0）blit，无`glReadBuffer`调用，只有ATT0参与blit。
- **多附件resolve**（`resolveAttachmentCount > 1`）：使用`ResolveMSAAMultiColor`，为每个attachment单独创建临时FBO进行blit，完全绕过预构建的FBO布局。

因此，drawBuffers的计数器bug **不会**导致`glBlitFramebuffer`期间的attachment错位问题。先前对Case 1和Case 2的分析中关于blit映射错误的描述属于过度推断。

### 真正受影响的路径

#### 1. InvalidateColor（关键影响）

`InvalidateColor`函数（`render_backend_gles.cpp:1624`）使用循环索引`ci`构建invalidate列表：

```cpp
// render_backend_gles.cpp:1624
for (uint32_t ci = 0; ci < sb.colorAttachmentCount; ++ci) {
    attachments[numAttachments++] = GL_COLOR_ATTACHMENT0 + ci;  // ← 使用ci（即idx）
}
```

此函数按索引顺序生成`GL_COLOR_ATTACHMENT0 + ci`，假设第i个颜色附件绑定在`GL_COLOR_ATTACHMENTi`。但当前代码使用计数器分配位置，FBO中实际布局是压缩的：

| idx | ci | images状态 | 计数器 | FBO中实际位置 | InvalidateColor目标 | 是否匹配 |
|-----|-----|-----------|--------|-------------|-------------------|---------|
| 0 | 1 | 有效 | 0→1 | ATT0 | ATT0 | 匹配 |
| 1 | 2 | 空 | 1（不变） | 无 | ATT1 | **错位** |
| 2 | 3 | 有效 | 1→2 | ATT1 | ATT2 | **错位** |

InvalidateColor尝试invalidate ATT1和ATT2，但FBO中仅有ATT0和ATT1有绑定。ATT2不存在于FBO中（invalidate无效），ATT1（含有效图像）未被invalidate（可能影响性能优化），且ATT0本应保留却被正确命中仅因恰好对齐。

> 修复drawBuffers bug后，FBO布局与`GL_COLOR_ATTACHMENT0 + ci`一致，`InvalidateColor`也将自动正确。

#### 2. HandleColorAttachments / glClearBufferfv

```cpp
glClearBufferfv(GL_COLOR, drawBuffers[idx] - GL_COLOR_ATTACHMENT0, ...);
```

此处`drawBuffers[idx]`指向计数器分配的压缩位置，而图像确实绑定在该压缩位置上，因此clear操作实际上命中了正确的attachment。**此路径不受影响。**

#### 3. Shader输出映射

```cpp
glDrawBuffers(count, drawBuffers);
```

`drawBuffers[idx]`将shader输出`idx`映射到`GL_COLOR_ATTACHMENT0 + 计数器值`，而图像确实绑定在该位置。Shader写入目标是正确的。**此路径不受影响。**

## 具体案例

### 案例1：颜色附件有空图像

**配置：**
- `colorAttachmentIndices = [1, 2, 3]`
- `resolveAttachmentIndices = [4, 5, 6]`
- `images[1]` = 有效（color0，acc_msaa）
- `images[2]` = **空/null**
- `images[3]` = 有效（color2，rev_msaa）
- `images[4]` = 有效（resolve0）
- `images[5]` = 有效（resolve1）
- `images[6]` = 有效（resolve2，rev）

**颜色FBO构建（当前代码）：**

| idx | ci | 状态 | 计数器 | drawBuffers[idx] | 绑定位置 | 图像 |
|-----|-----|------|--------|-----------------|---------|------|
| 0 | 1 | 有效 | 0→1 | ATT0 | ATT0 | images[1] (color0) |
| 1 | 2 | 空 | 1（不变） | GL_NONE | 无 | 无 |
| 2 | 3 | 有效 | 1→2 | ATT1 | ATT1 | images[3] (color2) |

颜色FBO布局：
```
GL_COLOR_ATTACHMENT0 → images[1] = color0 (acc_msaa)
GL_COLOR_ATTACHMENT1 → images[3] = color2 (rev_msaa)
```

**InvalidateColor影响：**

| Invalidate目标 | FBO中该位置 | 结果 |
|---------------|-----------|------|
| ATT0 (ci=0) | color0 | 正确invalidate |
| ATT1 (ci=1) | color2 | **本应跳过空槽，实际invalidate了color2** |
| ATT2 (ci=2) | 无绑定 | invalidate无效（不存在） |

**解析FBO构建（当前代码）：**

| idx | ci | 状态 | 计数器 | drawBuffers[idx] | 绑定位置 | 图像 |
|-----|-----|------|--------|-----------------|---------|------|
| 0 | 4 | 有效 | 0→1 | ATT0 | ATT0 | images[4] (resolve0) |
| 1 | 5 | 有效 | 1→2 | ATT1 | ATT1 | images[5] (resolve1) |
| 2 | 6 | 有效 | 2→3 | ATT2 | ATT2 | images[6] (resolve2) |

> 注意：resolve FBO在本例中全有效，计数器与idx一致，布局正确。但与颜色FBO的布局不对称：颜色FBO在ATT1放了color2，而解析FBO在ATT1放了resolve1。

---

### 案例2：解析附件有空图像

**配置：**
- `colorAttachmentIndices = [1, 2, 3]`
- `resolveAttachmentIndices = [4, 5, 6]`
- `images[1]` = 有效（color0）
- `images[2]` = 有效（color1）
- `images[3]` = 有效（color2）
- `images[4]` = 有效（resolve0）
- `images[5]` = **空/null**
- `images[6]` = 有效（resolve2）

**颜色FBO构建（当前代码）：**

| idx | ci | 计数器 | 绑定位置 | 图像 |
|-----|-----|--------|---------|------|
| 0 | 1 | 0→1 | ATT0 | images[1] (color0) |
| 1 | 2 | 1→2 | ATT1 | images[2] (color1) |
| 2 | 3 | 2→3 | ATT2 | images[3] (color2) |

**解析FBO构建（当前代码）：**

| idx | ci | 状态 | 计数器 | drawBuffers[idx] | 绑定位置 | 图像 |
|-----|-----|------|--------|-----------------|---------|------|
| 0 | 4 | 有效 | 0→1 | ATT0 | ATT0 | images[4] (resolve0) |
| 1 | 5 | **空** | 1（不变） | GL_NONE | 无 | 无 |
| 2 | 6 | 有效 | 1→2 | ATT1 | ATT1 | images[6] (resolve2) |

解析FBO布局：
```
GL_COLOR_ATTACHMENT0 → resolve0 (images[4])
GL_COLOR_ATTACHMENT1 → resolve2 (images[6])  ← 压缩到ATT1
```

> 同样，此处的InvalidateColor对解析FBO也存在相同的错位问题。

---

### 案例3：WBOIT正常情况（无空图像）— 无问题

**配置：**
- `colorAttachmentIndices = [1, 2]`
- `resolveAttachmentIndices = [3, 4]`
- 所有图像均有效

**颜色FBO：**

| idx | ci | 计数器 | 绑定位置 |
|-----|-----|--------|---------|
| 0 | 1 | 0→1 | ATT0 → acc_msaa |
| 1 | 2 | 1→2 | ATT1 → rev_msaa |

**解析FBO：**

| idx | ci | 计数器 | 绑定位置 |
|-----|-----|--------|---------|
| 0 | 3 | 0→1 | ATT0 → acc |
| 1 | 4 | 1→2 | ATT1 → rev |

**结论：** 所有图像有效时，计数器与idx等价，无问题。

---

## 为什么会发生这个问题？

### 关键理解点

1. **计数器只在有效图像时增加**
   - 遇到空图像时，计数器保持不变
   - 后续有效图像的GL attachment位置被"压缩"到更小编号

2. **按位置索引的GL操作假设连续编号**
   - `InvalidateColor`（`render_backend_gles.cpp:1624`）按`ci`生成`GL_COLOR_ATTACHMENT0 + ci`
   - 假设第i个颜色附件在ATTi，但压缩布局破坏了此假设

3. **计数器与索引的差异在空图像处累积**
   - 仅当所有图像均有效时，计数器值与循环索引一致
   - 任何空图像都会使后续位置的计数器滞后于索引

## 正确代码示例

### GenerateSubPassFBO

```cpp
for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
    const uint32_t ci = sb.colorAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;  // ← 使用idx
        const uint32_t original = imageMap[ci];
        if (original == EMPTY_ATTACHMENT) {
            BindToFbo(drawBuffers[idx], images[ci], ...);
        } else {
            BindToFboMultisampled(drawBuffers[idx], images[original], images[ci], ...);
        }
        ++colorAttachmentCount;  // ← 仍用于跟踪isStarted等参数，不决定attachment位置
    } else {
        drawBuffers[idx] = GL_NONE;
    }
}
```

### GenerateResolveFBO

```cpp
for (uint32_t idx = 0; idx < sb.resolveAttachmentCount; ++idx) {
    const uint32_t ci = sb.resolveAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;  // ← 使用idx
        BindToFbo(drawBuffers[idx], images[ci], ...);
        ++rp.resolveAttachmentCount;  // ← 仍用于跟踪，不决定attachment位置
    } else {
        drawBuffers[idx] = GL_NONE;
    }
}
```

> 注意：`colorAttachmentCount`和`rp.resolveAttachmentCount`修复后仍保留递增逻辑，因为它们在其他上下文（如`isStarted`参数判断）中有实际用途，只是不应再决定attachment位置。

## 修复后的案例1结果

**颜色FBO（修复后）：**

| idx | ci | 状态 | drawBuffers[idx] | 绑定位置 | 图像 |
|-----|-----|------|-----------------|---------|------|
| 0 | 1 | 有效 | ATT0 | ATT0 | images[1] (color0) |
| 1 | 2 | 空 | GL_NONE | 无 | 无 |
| 2 | 3 | 有效 | ATT2 | ATT2 | images[3] (color2) |

颜色FBO布局：
```
GL_COLOR_ATTACHMENT0 → color0 (images[1])
GL_COLOR_ATTACHMENT1 → 无（空槽）
GL_COLOR_ATTACHMENT2 → color2 (images[3])
```

**解析FBO（修复后）：**

| idx | ci | 状态 | drawBuffers[idx] | 绑定位置 | 图像 |
|-----|-----|------|-----------------|---------|------|
| 0 | 4 | 有效 | ATT0 | ATT0 | images[4] (resolve0) |
| 1 | 5 | 有效 | ATT1 | ATT1 | images[5] (resolve1) |
| 2 | 6 | 有效 | ATT2 | ATT2 | images[6] (resolve2) |

**InvalidateColor（修复后）：**

| Invalidate目标 | 颜色FBO该位置 | 结果 |
|---------------|-------------|------|
| ATT0 (ci=0) | color0 | 正确invalidate |
| ATT1 (ci=1) | 无绑定 | invalidate空槽（无害） |
| ATT2 (ci=2) | color2 | 正确invalidate |

**结论：** 修复后，FBO布局与`GL_COLOR_ATTACHMENT0 + ci`一致，`InvalidateColor`正确命中目标。同时，两个FBO中相同idx的attachment位置对齐。

## 总结

| 情况 | 当前代码（计数器） | 修复代码（idx） |
|------|-------------------|----------------|
| 无空图像 | 正常工作 | 正常工作 |
| 颜色有空图像 | InvalidateColor错位 | 正确处理 |
| 解析有空图像 | InvalidateColor错位 | 正确处理 |
| 两者空位置不同 | InvalidateColor严重错位 | 正确处理 |

### 交叉参考

- `InvalidateColor`实现位于`render_backend_gles.cpp:1624`，而非`node_context_pool_manager_gles.cpp`。在当前计数器布局下，`InvalidateColor`同样存在`ci`与FBO实际位置不一致的问题，仅在修复drawBuffers bug后方可正确工作。
- MSAA WBOIT Resolve相关分析另见OIT文档中对应章节，其中涉及`ResolveMSAAMultiColor`的临时FBO机制与本文分析的预构建FBO布局bug属于不同路径。

核心修复：将`node_context_pool_manager_gles.cpp:440`和`node_context_pool_manager_gles.cpp:530`处的计数器替换为循环索引`idx`，仅改变`drawBuffers[idx]`的赋值，`BindToFbo`/`BindToFboMultisampled`调用仍通过`drawBuffers[idx]`传参以保持可维护性。
