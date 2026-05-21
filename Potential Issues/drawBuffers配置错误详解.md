# drawBuffers配置错误详解

## 问题核心

在`GenerateSubPassFBO`和`GenerateResolveFBO`函数中，使用计数器（`colorAttachmentCount`或`resolveAttachmentCount`）而非循环索引（`idx`）来设置GL attachment位置，导致当存在空图像时，颜色附件和解析附件之间的映射关系被破坏。

## 代码分析

### GenerateSubPassFBO（第440行）

```cpp
for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
    const uint32_t ci = sb.colorAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + colorAttachmentCount;  // ← 使用计数器
        BindToFbo(drawBuffers[idx], images[ci], ...);
        ++colorAttachmentCount;  // ← 只有有效图像时才增加
    } else {
        drawBuffers[idx] = GL_NONE;
        // 计数器不增加！
    }
}
```

### GenerateResolveFBO（第530行）

```cpp
for (uint32_t idx = 0; idx < sb.resolveAttachmentCount; ++idx) {
    const uint32_t ci = sb.resolveAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + rp.resolveAttachmentCount;  // ← 使用计数器
        BindToFbo(drawBuffers[idx], images[ci], ...);
        ++rp.resolveAttachmentCount;  // ← 只有有效图像时才增加
    } else {
        drawBuffers[idx] = GL_NONE;
        // 计数器不增加！
    }
}
```

## 具体案例

### 案例1：颜色附件有空图像，解析附件全部有效

**配置：**
- `colorAttachmentIndices = [1, 2, 3]`（索引对应images数组）
- `resolveAttachmentIndices = [4, 5, 6]`（索引对应images数组）
- `images[1]` = 有效（color0，acc_msaa）
- `images[2]` = **空/null**（color1，某些条件下跳过）
- `images[3]` = 有效（color2，rev_msaa）
- `images[4]` = 有效（resolve0，acc）
- `images[5]` = 有效（resolve1）
- `images[6]` = 有效（resolve2，rev）

**颜色FBO构建过程（GenerateSubPassFBO）：**

| 循环idx | ci（附件索引） | images[ci]状态 | 计数器值 | drawBuffers[idx] | 绑定位置 | 实际绑定的图像 |
|---------|---------------|---------------|---------|-----------------|---------|--------------|
| 0 | 1 | 有效 | 0→1 | GL_COLOR_ATTACHMENT0 + 0 = **ATT0** | ATT0 | images[1] (color0) |
| 1 | 2 | **空/null** | 1（不变） | **GL_NONE** | 无 | 无（跳过） |
| 2 | 3 | 有效 | 1→2 | GL_COLOR_ATTACHMENT0 + 1 = **ATT1** | ATT1 | images[3] (color2) |

**颜色FBO最终布局：**
```
GL_COLOR_ATTACHMENT0 → images[1] = color0 (acc_msaa)
GL_COLOR_ATTACHMENT1 → images[3] = color2 (rev_msaa)
GL_COLOR_ATTACHMENT2 → 无（未绑定）
```

**解析FBO构建过程（GenerateResolveFBO）：**

| 循环idx | ci（附件索引） | images[ci]状态 | 计数器值 | drawBuffers[idx] | 绑定位置 | 实际绑定的图像 |
|---------|---------------|---------------|---------|-----------------|---------|--------------|
| 0 | 4 | 有效 | 0→1 | GL_COLOR_ATTACHMENT0 + 0 = **ATT0** | ATT0 | images[4] (resolve0) |
| 1 | 5 | 有效 | 1→2 | GL_COLOR_ATTACHMENT0 + 1 = **ATT1** | ATT1 | images[5] (resolve1) |
| 2 | 6 | 有效 | 2→3 | GL_COLOR_ATTACHMENT0 + 2 = **ATT2** | ATT2 | images[6] (resolve2) |

**解析FBO最终布局：**
```
GL_COLOR_ATTACHMENT0 → images[4] = resolve0 (acc)
GL_COLOR_ATTACHMENT1 → images[5] = resolve1
GL_COLOR_ATTACHMENT2 → images[6] = resolve2 (rev)
```

**glBlitFramebuffer执行时的映射：**

当调用`glBlitFramebuffer(..., GL_COLOR_BUFFER_BIT, GL_NEAREST)`：

| GL Attachment | 颜色FBO内容 | 解析FBO目标 | 结果 |
|---------------|------------|-------------|------|
| ATT0 | color0 (images[1]) | resolve0 (images[4]) | color0 → resolve0 ✓ **正确** |
| ATT1 | color2 (images[3]) | resolve1 (images[5]) | color2 → resolve1 ✗ **错误！** |
| ATT2 | 无（颜色FBO无此附件） | resolve2 (images[6]) | 无内容 → resolve2 ✗ **解析失败** |

**预期正确的映射关系：**
- colorAttachmentIndices[0]=1 对应 resolveAttachmentIndices[0]=4（color0 → resolve0）
- colorAttachmentIndices[1]=2 对应 resolveAttachmentIndices[1]=5（color1 → resolve1，但color1是空）
- colorAttachmentIndices[2]=3 对应 resolveAttachmentIndices[2]=6（color2 → resolve2）

**实际发生的错误映射：**
- color0 → resolve0 ✓（正确）
- color2 → resolve1 ✗（错误！应该color2 → resolve2）
- resolve2没有收到任何数据 ✗（错误！应该收到color2的数据）

---

### 案例2：解析附件有空图像，颜色附件全部有效

**配置：**
- `colorAttachmentIndices = [1, 2, 3]`
- `resolveAttachmentIndices = [4, 5, 6]`
- `images[1]` = 有效（color0）
- `images[2]` = 有效（color1）
- `images[3]` = 有效（color2）
- `images[4]` = 有效（resolve0）
- `images[5]` = **空/null**（resolve1）
- `images[6]` = 有效（resolve2）

**颜色FBO构建：**

| idx | ci | 状态 | 计数器 | drawBuffers | 绑定 |
|-----|-----|------|--------|-------------|------|
| 0 | 1 | 有效 | 0→1 | ATT0 | images[1] |
| 1 | 2 | 有效 | 1→2 | ATT1 | images[2] |
| 2 | 3 | 有效 | 2→3 | ATT2 | images[3] |

颜色FBO布局：
```
ATT0 → color0 (images[1])
ATT1 → color1 (images[2])
ATT2 → color2 (images[3])
```

**解析FBO构建：**

| idx | ci | 状态 | 计数器 | drawBuffers | 绑定 |
|-----|-----|------|--------|-------------|------|
| 0 | 4 | 有效 | 0→1 | ATT0 | images[4] |
| 1 | 5 | **空** | 1（不变） | GL_NONE | 无 |
| 2 | 6 | 有效 | 1→2 | **ATT1** | images[6] ← 问题！应该绑到ATT2 |

解析FBO布局：
```
ATT0 → resolve0 (images[4])
ATT1 → resolve2 (images[6]) ← 错误位置！应该是ATT2
ATT2 → 无（未绑定）
```

**glBlitFramebuffer映射：**

| GL Attachment | 颜色FBO内容 | 解析FBO目标 | 结果 |
|---------------|------------|-------------|------|
| ATT0 | color0 | resolve0 | color0 → resolve0 ✓ |
| ATT1 | color1 | resolve2 | color1 → resolve2 ✗ **错误！** |
| ATT2 | color2 | 无 | color2无处解析 ✗ **数据丢失！** |

**预期映射：**
- color0 → resolve0 ✓
- color1 → resolve1（空，跳过）✓
- color2 → resolve2 ✓

**实际映射：**
- color0 → resolve0 ✓
- color1 → resolve2 ✗（错误！）
- color2 → 无目标 ✗（数据丢失）

---

### 案例3：WBOIT正常情况（无空图像）- 无问题

**配置：**
- `colorAttachmentIndices = [1, 2]`
- `resolveAttachmentIndices = [3, 4]`
- 所有图像都有效

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

**映射：**
- ATT0: acc_msaa → acc ✓
- ATT1: rev_msaa → rev ✓

**结论：** 当所有图像都有效时，无问题。

---

## 为什么会发生这个问题？

### 关键理解点

1. **计数器只在有效图像时增加**
   - 遇到空图像时，计数器保持不变
   - 导致后续有效图像的GL attachment位置被"压缩"

2. **颜色附件和解析附件独立构建**
   - 两者的空图像模式可能不同
   - 导致两者的attachment布局不一致

3. **glBlitFramebuffer按GL attachment位置匹配**
   - GL_COLOR_ATTACHMENT0 → GL_COLOR_ATTACHMENT0
   - GL_COLOR_ATTACHMENT1 → GL_COLOR_ATTACHMENT1
   - 不考虑原始的attachmentIndices对应关系

### 正确做法

应该使用`idx`（循环索引）而非计数器，确保：
- `colorAttachmentIndices[i]` 绑定到 `GL_COLOR_ATTACHMENTi`
- `resolveAttachmentIndices[i]` 绑定到 `GL_COLOR_ATTACHMENTi`

这样glBlitFramebuffer的映射才能保持正确的对应关系。

## 正确代码示例

```cpp
// GenerateSubPassFBO - 正确版本
for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
    const uint32_t ci = sb.colorAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;  // ← 使用idx
        BindToFbo(GL_COLOR_ATTACHMENT0 + idx, images[ci], ...);  // ← 使用idx
        ++colorAttachmentCount;
    } else {
        drawBuffers[idx] = GL_NONE;
    }
}

// GenerateResolveFBO - 正确版本
for (uint32_t idx = 0; idx < sb.resolveAttachmentCount; ++idx) {
    const uint32_t ci = sb.resolveAttachmentIndices[idx];
    if (images[ci].image) {
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + idx;  // ← 使用idx
        BindToFbo(GL_COLOR_ATTACHMENT0 + idx, images[ci], ...);  // ← 使用idx
        ++rp.resolveAttachmentCount;
    } else {
        drawBuffers[idx] = GL_NONE;
    }
}
```

## 使用正确代码后的案例1结果

**颜色FBO（正确版本）：**

| idx | ci | 状态 | 绑定位置 | 绑定图像 |
|-----|-----|------|---------|---------|
| 0 | 1 | 有效 | ATT0 | images[1] (color0) |
| 1 | 2 | 空 | 无 | 无 |
| 2 | 3 | 有效 | ATT2 | images[3] (color2) |

**解析FBO（正确版本）：**

| idx | ci | 状态 | 绑定位置 | 绑定图像 |
|-----|-----|------|---------|---------|
| 0 | 4 | 有效 | ATT0 | images[4] (resolve0) |
| 1 | 5 | 有效 | ATT1 | images[5] (resolve1) |
| 2 | 6 | 有效 | ATT2 | images[6] (resolve2) |

**glBlitFramebuffer映射（正确版本）：**

| GL Attachment | 颜色FBO | 解析FBO | 结果 |
|---------------|---------|---------|------|
| ATT0 | color0 | resolve0 | color0 → resolve0 ✓ |
| ATT1 | 无 | resolve1 | 无内容复制（正确跳过） |
| ATT2 | color2 | resolve2 | color2 → resolve2 ✓ |

**结论：** 使用idx后，映射关系正确恢复。

## 总结

| 情况 | 当前代码（计数器） | 正确代码（idx） |
|------|-------------------|----------------|
| 无空图像 | 正常工作 | 正常工作 |
| 颜色有空，解析无空 | 错误映射 | 正确映射 |
| 解析有空，颜色无空 | 数据丢失 | 正确跳过 |
| 两者空位置不同 | 严重错误 | 正确处理 |

核心修复：将第440行和第530行的计数器替换为循环索引idx。
