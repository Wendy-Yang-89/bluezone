# GL_ES_MSAA实现方式对比

## 背景与问题引入

### 走样现象（Aliasing）

在光栅化渲染中，几何边缘（尤其是斜线或曲线）呈现阶梯状像素块的现象称为**走样（Aliasing）**，俗称"锯齿"。

**产生原因：**
- 屏幕由离散像素网格组成
- 光栅化时像素中心点采样，结果为二元状态（完全覆盖或完全不覆盖）
- 边缘像素缺乏过渡色，呈现锐利阶梯状

### 抗锯齿技术

**抗锯齿（Anti-Aliasing，AA）** 通过对边缘像素计算中间色值，实现平滑过渡。常见技术包括：

| 技术 | 原理 | 性能开销 |
|------|------|---------|
| MSAA | 多重采样，仅对几何边缘抗锯齿 | 中等 |
| FXAA | 后处理，检测边缘并平滑 | 低 |
| TAA | 时域累积，利用历史帧信息 | 低-中 |
| SSAA | 超采样，全屏抗锯齿 | 高 |

### MSAA工作原理

MSAA（Multisample Anti-Aliasing）在每个像素内设置多个采样点（如2、4、8个），光栅化时：

1. **深度/覆盖率测试**：每个采样点独立判断是否被几何覆盖
2. **片元着色**：每个像素执行一次片元着色器（与采样数无关）
3. **颜色复制**：被覆盖的采样点复制相同颜色值
4. **解析（Resolve）**：将多采样数据平均为单采样输出

**示例：4x MSAA**
- 像素内4个采样点，3个被覆盖，1个未覆盖
- 解析后颜色 = 75% 物体色 + 25% 背景色

### MSAA解析（Resolve）

MSAA渲染生成多采样纹理（每个像素存储N个采样值），显示前需转换为单采样纹理：

- **输入**：MSAA纹理（N samples/pixel）
- **输出**：普通纹理（1 sample/pixel）
- **方法**：硬件自动平均或手动Shader计算

解析是MSAA流程的必要步骤。

### Framebuffer（FBO）

**Framebuffer Object** 是OpenGL的渲染目标容器，包含：

- **Color Attachment**：颜色输出缓冲，可多个（MRT）
- **Depth Attachment**：深度缓冲，用于深度测试
- **Stencil Attachment**：模板缓冲，用于遮罩测试

MSAA FBO使用多采样纹理或Renderbuffer作为Attachment。

### Tile-Based GPU架构

移动GPU（ARM Mali、Adreno等）采用Tile-Based渲染：

- 屏幕分割为小块（Tile，如32×32像素）
- Tile内渲染完成后写入系统内存
- **隐式解析优势**：Tile内可自动完成MSAA解析，无需额外显式解析步骤

此架构在移动平台广泛采用，MSAA解析效率显著高于桌面GPU。

### OpenGL ES的MSAA限制

OpenGL ES相比桌面OpenGL有以下限制：

- **不支持 `glReadBuffer`**：无法指定读取哪个Color Attachment
- **多附件解析复杂**：需逐个创建临时FBO进行Blit操作
- **依赖扩展**：高效隐式解析需 `GL_EXT_multisampled_render_to_texture2` 扩展

本文档针对上述限制，对比分析OpenGL ES中三种MSAA解析方案。

---

## 方法1：隐式解析（推荐）

### 扩展名称
- `GL_EXT_multisampled_render_to_texture2`
- `GL_OVR_multiview_multisampled_render_to_texture`

### 原理
直接将非MSAA纹理绑定为MSAA渲染目标，GPU在渲染过程中自动处理多采样和解析，无需显式调用解析命令。

### 核心函数

```cpp
// 纹理2D绑定（单层）
void glFramebufferTexture2DMultisampleEXT(
    GLenum target,           // GL_FRAMEBUFFER
    GLenum attachment,       // GL_COLOR_ATTACHMENT0
    GLenum textarget,        // GL_TEXTURE_2D
    GLuint texture,          // 纹理ID（非MSAA纹理）
    GLint level,             // mip level（通常为0）
    GLsizei samples          // 采样数（2/4/8）
);

// 多视图纹理绑定（array + multiview）
void glFramebufferTextureMultisampleMultiviewOVR(
    GLenum target,
    GLenum attachment,
    GLuint texture,
    GLint level,
    GLsizei samples,
    GLint baseViewIndex,
    GLsizei numViews
);

// Renderbuffer绑定
void glRenderbufferStorageMultisampleEXT(
    GLenum target,           // GL_RENDERBUFFER
    GLsizei samples,
    GLenum internalformat,
    GLsizei width,
    GLsizei height
);
```

### 使用条件

| 条件 | 要求 | 说明 |
|------|------|------|
| 扩展可用 | `GL_EXT_multisampled_render_to_texture2` | 检查 `device.HasExtension()` |
| Transient标志 | `CORE_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` | RNG中**手动配置** `transient_attachment` |
| Lazily内存 | `CORE_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT` | RNG中**手动配置** `lazily_allocated`（需配合Transient） |
| 非Input附件 | 不能有 `CORE_IMAGE_USAGE_INPUT_ATTACHMENT_BIT` | Vulkan限制：TRANSIENT不能用于Input |
| 非Backbuffer解析 | `IsDefaultResolve()` 返回false | 不能解析到默认帧缓冲 |

### RNG配置示例

```json
{
    "name": "acc",
    "format": "r16g16b16a16_sfloat",
    "usageFlags": "color_attachment | sampled",
    "memoryPropertyFlags": "device_local | lazily_allocated",
    "engineCreationFlags": "dynamic_barriers"
}
```

**关键：**
- `lazily_allocated` **需手动配合** `transient_attachment`，两者是设计最佳实践搭配
- `transient_attachment` 表示图像内容不持久化，`lazily_allocated` 表示内存不持久化
- 两者配合实现Tile-Based GPU的内存效率优化
- 不能有 `input_attachment` flag（Vulkan限制：TRANSIENT_ATTACHMENT不能用于Input Attachment）

### 代码路径（LumeRender）

```
FilterRenderPass() (line 837)
  ↓
检查 multisampledRenderToTexture_ (line 840)
  ↓
MapColorAttachments() - 建立color到resolve的映射 (line 863)
  ↓
翻转映射：imageMap[resolve] = color (line 871-878)
  ↓
GenerateSubPassFBO() (line 422)
  ↓
检查 imageMap[ci] 是否有映射 (line 438)
  ↓
BindToFboMultisampled() - 使用隐式解析绑定 (line 445-447)
  ↓
glFramebufferTexture2DMultisampleEXT() (line 388)
```

### 优势

1. **性能最优**：GPU自动处理，无额外开销
2. **代码简洁**：无需显式解析命令
3. **ARM推荐**：避免glBlitFramebuffer的已知问题
4. **内存效率**：可能使用Tile-Based渲染优化

### 缺点

1. 需要特定扩展支持
2. 不支持作为Input Attachment使用
3. 需要Transient标志

---

## 方法2：显式解析（glBlitFramebuffer）

### 原理
渲染结束后，使用glBlitFramebuffer将MSAA纹理/Renderbuffer的内容复制解析到非MSAA目标。

### 核心函数

```cpp
void glBlitFramebuffer(
    GLint srcX0, GLint srcY0,    // 源矩形左下
    GLint srcX1, GLint srcY1,    // 源矩形右上
    GLint dstX0, GLint dstY0,    // 目标矩形左下
    GLint dstX1, GLint dstY1,    // 目标矩形右上
    GLbitfield mask,             // GL_COLOR_BUFFER_BIT / GL_DEPTH_BUFFER_BIT
    GLenum filter                // GL_NEAREST（解析必须用此值）
);
```

### GLES限制

**重要：OpenGL ES不支持 `glReadBuffer` 函数！**

这意味着无法指定读取哪个颜色附件。GLES默认只读取 `GL_COLOR_ATTACHMENT0`。

### 多附件解析方案

由于GLES不支持glReadBuffer，多附件解析必须创建临时FBO，逐个绑定附件：

```cpp
GLuint frameBuffers[2];
glGenFramebuffers(2, frameBuffers);

for (uint32_t idx = 0; idx < resolveAttachmentCount; ++idx) {
    // 绑定到临时FBO的ATTACHMENT0
    glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                           srcType, srcTexture, 0);
    glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                           dstType, dstTexture, 0);

    // 执行单附件解析
    glBlitFramebuffer(0, 0, width, height, 0, 0, width, height,
                      GL_COLOR_BUFFER_BIT, GL_NEAREST);
}

glDeleteFramebuffers(2, frameBuffers);
```

### 绑定方式对比

| 绑定方式 | 函数 | 适用场景 |
|---------|------|---------|
| 纹理2D | `glFramebufferTexture2D(GL_x_FRAMEBUFFER, attachment, GL_TEXTURE_2D, texture, level)` | 2D纹理 |
| 纹理层 | `glFramebufferTextureLayer(GL_x_FRAMEBUFFER, attachment, texture, level, layer)` | Array纹理 |
| Renderbuffer | `glFramebufferRenderbuffer(GL_x_FRAMEBUFFER, attachment, GL_RENDERBUFFER, rb)` | Renderbuffer |

### 代码路径（LumeRender）

```
RenderCommandEndRenderPass()
  ↓
ResolveMSAA() (line 1631)
  ↓
检查 resolveAttachmentCount > 1
  ↓
创建临时FBO (line 1650-1653)
  ↓
逐个附件绑定到GL_COLOR_ATTACHMENT0 (line 1665-1666)
  ↓
glBlitFramebuffer() (line 1668-1671)
  ↓
删除临时FBO (line 1675)
```

### 优势

1. 无需特定扩展（核心功能）
2. 可用于任何纹理类型
3. 支持Input Attachment

### 缺点

1. **性能较差**：多次FBO切换和绑定
2. **ARM不推荐**：已知驱动问题
3. **多附件复杂**：需要逐个处理
4. **drawBuffers索引问题**：当前代码存在bug

---

## 方法3：Shader手动解析

### 原理
在Shader中读取MSAA纹理的每个sample，手动计算平均值。

### 扩展要求
`GL_EXT_texture_multisample`

### Shader代码

```glsl
#extension GL_EXT_texture_multisample : enable

uniform sampler2DMS msaaTexture;
uniform int uSamples;

vec4 manualResolve(vec2 uv, ivec2 size) {
    vec4 result = vec4(0.0);
    ivec2 coord = ivec2(uv * vec2(size));

    for (int i = 0; i < uSamples; ++i) {
        result += texelFetch(msaaTexture, coord, i);
    }

    return result / float(uSamples);
}
```

### 使用流程

1. 创建MSAA纹理（使用 `GL_TEXTURE_2D_MULTISAMPLE`）
2. 渲染到MSAA纹理
3. 创建单独的解析Pass
4. Shader读取MSAA纹理，输出解析结果

### 优势

1. 完全控制解析过程
2. 可实现自定义解析算法（非简单平均）
3. 无需glBlitFramebuffer

### 缺点

1. **性能很差**：每个像素多次采样
2. 需要额外扩展
3. 需要额外渲染Pass
4. 代码复杂度高

---

## 方法对比总结

| 方法 | 需要glFramebufferTexture2D | 需要glBlitFramebuffer | 需要扩展 | 性能 | 复杂度 |
|------|:-------------------------:|:--------------------:|:--------:|:----:|:------:|
| 隐式解析 | ❌ | ❌ | ✅ | ⭐⭐⭐⭐⭐ | 低 |
| 显式解析 | ✅ | ✅ | ❌ | ⭐⭐⭐ | 中 |
| Shader解析 | ❌ | ❌ | ✅ | ⭐ | 高 |

---

## WBOIT当前问题分析

### RNG配置检查

`core3d_rng_cam_scene_hdrp_msaa_wboit.rng`中：

| 目标 | memoryPropertyFlags | usageFlags | 预期触发隐式解析？ |
|------|---------------------|------------|------------------|
| acc_msaa | `device_local \| lazily_allocated` | `color_attachment \| sampled` | ✅ 应该 |
| rev_msaa | `device_local \| lazily_allocated` | `color_attachment \| sampled` | ✅ 应该 |
| acc | `device_local \| lazily_allocated` | `color_attachment \| sampled` | ✅ 应该 |
| rev | `device_local \| lazily_allocated` | `color_attachment \| sampled` | ✅ 应该 |

### 可能失败的原因

隐式解析启用需满足方法1"使用条件"中的全部要求。关键检查点（均在 `node_context_pool_manager_gles.cpp` 中）：

| 检查点 | 位置 | 条件 |
|--------|------|------|
| 扩展可用 | `FilterRenderPass` (line 840) | `multisampledRenderToTexture_` 为true |
| 多视图兼容 | line 843-846 | `multiViewMultisampledRenderToTexture_` 或 `viewMask == 0` |
| 非backbuffer | line 861 | `IsDefaultResolve()` 返回false |
| isTrans标志 | `BindToFboMultisampled` (line 352, 365, 383) | `usageFlags & CORE_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` |
| 非Input Attachment | `MapColorAttachments` (line 603-614) | 无 `CORE_IMAGE_USAGE_INPUT_ATTACHMENT_BIT` |

---

## 最佳实践建议

### 优先使用隐式解析

1. **RNG配置**
   ```json
   {
       "memoryPropertyFlags": "device_local | lazily_allocated",
       "usageFlags": "color_attachment | sampled"  // 无input_attachment
   }
   ```

2. **运行时检查**
   - 验证 `GL_EXT_multisampled_render_to_texture2` 扩展可用
   - 验证 `multisampledRenderToTexture_` 标志为true
   - 验证 `imageMap` 映射正确建立

### 回退到显式解析

当隐式解析不可用时：
1. 使用临时FBO逐附件解析
2. 修复drawBuffers索引bug（使用idx而非计数器）
3. 注意ARM性能警告

---

## 相关文件

| 文件 | 关键函数 | 行号 |
|------|---------|------|
| `node_context_pool_manager_gles.cpp` | `FilterRenderPass` | 837-880 |
| `node_context_pool_manager_gles.cpp` | `BindToFboMultisampled` | 326-394 |
| `node_context_pool_manager_gles.cpp` | `MapColorAttachments` | 594-623 |
| `node_context_pool_manager_gles.cpp` | `GenerateSubPassFBO` | 422-488 |
| `node_context_pool_manager_gles.cpp` | `GetFramebufferHandle` | 748-804 |
| `render_backend_gles.cpp` | `ResolveMSAA` | 1631-1690 |
| `gpu_image_gles.cpp` | Renderbuffer创建 | 216-226 |
| `device_gles.cpp` | 扩展检查 | 1171-1182 |

---

## 参考资料

1. [GL_EXT_multisampled_render_to_texture Extension Spec](https://www.khronos.org/registry/OpenGL/extensions/EXT/EXT_multisampled_render_to_texture.txt)
2. [OpenGL ES 3.0 Spec - glBlitFramebuffer](https://www.khronos.org/registry/OpenGL/specs/es/3.0/es_spec_3.0.html)
3. ARM Mali Best Practices: MSAA Resolve Recommendations
