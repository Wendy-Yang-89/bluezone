# OpenGL_ES核心对象详解

## 背景与问题引入

### OpenGL ES渲染架构

OpenGL ES是移动平台的图形渲染API，采用对象化设计管理渲染资源。渲染过程涉及多种GPU对象，各对象承担不同职责：

- **数据存储对象**：Texture、Renderbuffer - 存储图像/渲染数据
- **容器管理对象**：Framebuffer - 组织渲染目标集合
- **状态对象**：Pipeline、Sampler - 配置渲染参数

理解这些对象的特性差异，是正确配置渲染管线的基础。

### 核心问题

在OpenGL ES渲染系统中，开发者常面临以下选择：

1. **Texture还是Renderbuffer**：颜色附件应使用哪种对象？
2. **MSAA支持**：如何实现多重采样抗锯齿？
3. **多视图渲染**：VR左右眼如何高效共享资源？
4. **离屏渲染**：渲染结果如何传递给后续Pass？

错误选择可能导致：
- Renderbuffer无法被后续Pass采样
- Texture不支持MSAA（GLES限制）
- 资源分配效率低下

### 本文档解决的问题

本文档系统对比OpenGL ES四种核心对象：
- **Texture2D**：2D纹理对象
- **Texture Layer**：Array Texture的单层
- **Renderbuffer**：渲染缓冲对象
- **Framebuffer**：帧缓冲对象（FBO）

通过特性对比和使用场景分析，指导开发者正确选择和使用渲染对象。

---

## 核心概念

### Texture（纹理）

**Texture** 是存储图像数据的GPU对象，主要特性：

| 特性 | 说明 |
|------|------|
| **Shader可采样** | 通过sampler2D等uniform在Shader中读取 |
| **可作为渲染目标** | 绑定到Framebuffer的Color Attachment |
| **支持Mipmap** | 多级分辨率，用于距离衰减 |
| **格式灵活** | RGBA8、RGBA16F、R32F等多种格式 |

Texture适用于需要后续Pass采样的渲染输出（如后期处理输入、材质纹理）。

### Renderbuffer

**Renderbuffer** 是专为渲染目标设计的GPU存储对象：

| 特性 | 说明 |
|------|------|
| **Shader不可采样** | 无法在Shader中读取数据 |
| **可作为渲染目标** | 绑定到Framebuffer Attachment |
| **支持MSAA** | GLES核心支持多采样Renderbuffer |
| **内存布局优化** | Tile-Based GPU可能更高效 |

Renderbuffer适用于不需要后续采样的渲染输出（如深度附件、MSAA颜色缓冲）。

### Array Texture（纹理数组）

**Array Texture** 是多层数据共享存储的纹理类型：

- 所有层共享相同尺寸和格式
- 单层可独立绑定到Framebuffer
- Shader可采样指定层（sampler2DArray + layer索引）

Array Texture适用于多视图渲染（VR）、级联阴影、动态渲染目标池等场景。

### Framebuffer（FBO）

**Framebuffer** 是渲染目标的容器对象：

- 不存储数据，仅引用Texture或Renderbuffer
- 绑定Color/Depth/Stencil多种Attachment
- 支持多颜色附件（MRT）
- 离屏渲染的必要载体

Framebuffer是OpenGL ES渲染管线的核心枢纽。

### Attachment类型

Framebuffer可绑定以下Attachment：

| Attachment类型 | 用途 | 常用格式 |
|---------------|------|---------|
| **Color Attachment** | 存储颜色输出 | RGBA8、RGBA16F |
| **Depth Attachment** | 存储深度值 | DEPTH24、DEPTH32F |
| **Stencil Attachment** | 存储模板值 | STENCIL8 |
| **Depth-Stencil Attachment** | 深度+模板组合 | DEPTH24_STENCIL8 |

Attachment的选择决定渲染输出的内容和格式。

---

## 一、对象定义对比表

| 对象类型 | 定义 | 主要用途 | 是否可采样 | 是否可渲染 | 内存类型 |
|---------|------|---------|-----------|-----------|---------|
| **Texture2D** | 2D纹理对象 | 存储2D图像数据供Shader采样 | ✅ 是 | ✅ 是（作为attachment） | GPU纹理内存 |
| **Texture Layer** | 纹理层（Array Texture的一部分） | 存储多层图像数据（如Array Texture的单层） | ✅ 是 | ✅ 是（作为attachment） | GPU纹理内存 |
| **Renderbuffer** | 渲染缓冲对象 | 专门用于渲染目标的存储 | ❌ 否 | ✅ 是（作为attachment） | GPU渲染内存 |
| **Framebuffer** | 帧缓冲对象（FBO） | 组织和管理渲染目标集合 | N/A（容器） | N/A（容器） | 容器对象 |

---

## 二、Texture2D详解

### 2.1 定义

**Texture2D（2D纹理）**：存储二维图像数据的GPU对象，可以被Shader采样读取，也可以作为渲染目标。

### 2.2 创建流程

```cpp
// 1. 生成纹理对象
GLuint texture2D;
glGenTextures(1, &texture2D);

// 2. 绑定纹理
glBindTexture(GL_TEXTURE_2D, texture2D);

// 3. 设置纹理参数
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

// 4. 分配存储并上传数据（可选）
glTexImage2D(
    GL_TEXTURE_2D,          // target
    0,                      // level (mipmap level)
    GL_RGBA8,               // internal format
    width,                  // width
    height,                 // height
    0,                      // border (must be 0)
    GL_RGBA,                // format
    GL_UNSIGNED_BYTE,       // type
    imageData               // data (可为NULL，仅分配存储)
);

// 5. 生成Mipmap（可选）
glGenerateMipmap(GL_TEXTURE_2D);
```

### 2.3 作为渲染目标绑定

```cpp
// 将Texture2D绑定为Framebuffer的颜色附件
glFramebufferTexture2D(
    GL_FRAMEBUFFER,         // target
    GL_COLOR_ATTACHMENT0,   // attachment
    GL_TEXTURE_2D,          // textarget
    texture2D,              // texture
    0                       // level
);
```

### 2.4 Shader中采样

```glsl
// GLSL Shader
uniform sampler2D uTexture;

void main() {
    vec4 color = texture(uTexture, texCoord);
}
```

### 2.5 特点和限制

**优点：**
- ✅ 可被Shader采样读取
- ✅ 可作为渲染目标
- ✅ 支持 mipmap
- ✅ 支持多种格式（RGBA8、RGBA16F、R32F等）
- ✅ 可用于后续渲染pass（作为输入）

**限制：**
- ❌ GLES不支持 `GL_TEXTURE_2D_MULTISAMPLE`（MSAA纹理2D）
- ❌ 某些格式不支持作为渲染目标（需检查格式支持）

**适用场景：**
1. **颜色附件**：渲染输出颜色
2. **深度附件**：存储深度值（需使用深度格式）
3. **后期处理输入**：作为下一pass的采样源
4. **纹理映射**：模型材质纹理

---

## 三、Texture Layer详解

### 3.1 定义

**Texture Layer**：纹理层，指Array Texture（如GL_TEXTURE_2D_ARRAY）的单个层。Array Texture是多层数据的集合，每层可独立绑定到Framebuffer。

### 3.2 创建流程

```cpp
// 1. 生成Array Texture
GLuint textureArray;
glGenTextures(1, &textureArray);

// 2. 绑定为Array Texture
glBindTexture(GL_TEXTURE_2D_ARRAY, textureArray);

// 3. 设置参数
glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

// 4. 分配存储（所有层共享相同尺寸和格式）
glTexImage3D(
    GL_TEXTURE_2D_ARRAY,    // target (GLES中用3D分配array)
    0,                      // level
    GL_RGBA8,               // internal format
    width,                  // width
    height,                 // height
    layerCount,             // depth = layer count
    0,                      // border
    GL_RGBA,                // format
    GL_UNSIGNED_BYTE,       // type
    NULL                    // data (先分配存储)
);

// 5. 上传单层数据（可选）
for (uint32_t layer = 0; layer < layerCount; ++layer) {
    glTexSubImage3D(
        GL_TEXTURE_2D_ARRAY,
        0,                  // level
        0,                  // xoffset
        0,                  // yoffset
        layer,              // zoffset = layer index
        width,
        height,
        1,                  // depth = 1 layer
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        layerData[layer]
    );
}
```

### 3.3 绑定单层到Framebuffer

```cpp
// 将Texture Array的第N层绑定为Framebuffer附件
glFramebufferTextureLayer(
    GL_FRAMEBUFFER,         // target
    GL_COLOR_ATTACHMENT0,   // attachment
    textureArray,           // texture
    0,                      // level
    layerIndex              // layer (第几层)
);
```

### 3.4 Shader中采样

```glsl
// GLSL Shader
uniform sampler2DArray uTextureArray;

void main() {
    // 采样第N层
    vec4 color = texture(uTextureArray, vec3(texCoord, layerIndex));
}
```

### 3.5 特点和限制

**优点：**
- ✅ 多层共享存储，减少内存分配开销
- ✅ 每层可独立绑定到不同Framebuffer
- ✅ 支持Shader采样
- ✅ 适合多视图渲染（VR、立体渲染）

**限制：**
- ❌ 所有层必须相同尺寸和格式
- ❌ GLES不支持 `GL_TEXTURE_2D_MULTISAMPLE_ARRAY`
- ❌ 需要GLES 3.0+支持

**适用场景：**
1. **多视图渲染**：VR左右眼渲染、立体渲染
2. **Cascaded Shadow Maps**：多级阴影映射
3. **Deferred Rendering G-Buffer**：多附件打包
4. **动态渲染目标池**：复用同一Array的不同层

---

## 四、Renderbuffer详解

### 4.1 定义

**Renderbuffer**：专门为渲染目标设计的GPU存储对象，不能被Shader采样，只能作为Framebuffer附件。

### 4.2 创建流程

```cpp
// 1. 生成Renderbuffer
GLuint renderbuffer;
glGenRenderbuffers(1, &renderbuffer);

// 2. 绑定Renderbuffer
glBindRenderbuffer(GL_RENDERBUFFER, renderbuffer);

// 3. 分配存储
glRenderbufferStorage(
    GL_RENDERBUFFER,        // target
    GL_RGBA8,               // internal format
    width,                  // width
    height                  // height
);

// 4. MSAA Renderbuffer（如果需要）
glRenderbufferStorageMultisampleEXT(
    GL_RENDERBUFFER,
    samples,                // 采样数（如4）
    GL_RGBA8,
    width,
    height
);
```

### 4.3 绑定到Framebuffer

```cpp
// 将Renderbuffer绑定为Framebuffer附件
glFramebufferRenderbuffer(
    GL_FRAMEBUFFER,         // target
    GL_COLOR_ATTACHMENT0,   // attachment
    GL_RENDERBUFFER,        // renderbuffertarget
    renderbuffer            // renderbuffer
);
```

### 4.4 Shader中不可采样

```glsl
// ❌ Renderbuffer不能被Shader采样
// uniform sampler2D uRenderbuffer; // 错误！Renderbuffer不可采样
```

### 4.5 特点和限制

**优点：**
- ✅ 专为渲染优化，性能可能更好
- ✅ 支持MSAA（`glRenderbufferStorageMultisampleEXT`）
- ✅ 内存布局可能更高效（Tile-Based GPU）
- ✅ 不占用纹理采样器资源

**限制：**
- ❌ **不能被Shader采样读取**
- ❌ 不能用于后续渲染pass作为输入
- ❌ 不能用于后期处理
- ❌ 不支持 mipmap

**适用场景：**
1. **深度/Stencil附件**：不需要后续采样的深度缓冲
2. **MSAA颜色附件**：需要MSAA但不需要后续采样的颜色缓冲
3. **临时渲染目标**：只在当前pass使用，不需要传递
4. **只写不读的附件**：不需要Shader访问的渲染结果

---

## 五、Framebuffer详解

### 5.1 定义

**Framebuffer（FBO）**：容器对象，组织和管理多个渲染目标（Texture或Renderbuffer）的集合。它不存储数据，只是引用已有的Texture或Renderbuffer。

### 5.2 创建流程

```cpp
// 1. 生成Framebuffer
GLuint framebuffer;
glGenFramebuffers(1, &framebuffer);

// 2. 绑定Framebuffer
glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);

// 3. 绑定附件（Texture或Renderbuffer）
// 颜色附件
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, colorTexture, 0);
// 或使用Renderbuffer
glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, colorRenderbuffer);

// 深度附件
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, depthTexture, 0);
// 或使用Renderbuffer
glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depthRenderbuffer);

// 4. 检查完整性
GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
if (status != GL_FRAMEBUFFER_COMPLETE) {
    // 处理错误
    switch (status) {
        case GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT:
            // 附件不完整
            break;
        case GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT:
            // 缺少附件
            break;
        case GL_FRAMEBUFFER_UNSUPPORTED:
            // 不支持的格式组合
            break;
    }
}

// 5. 指定渲染输出（多附件时）
GLenum drawBuffers[] = { GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1 };
glDrawBuffers(2, drawBuffers);
```

### 5.3 Framebuffer附件类型

| 附件类型 | 说明 | 可用对象 |
|---------|------|---------|
| **Color Attachment** | 颜色输出（0-15） | Texture2D、Texture Layer、Renderbuffer |
| **Depth Attachment** | 深度输出 | Texture2D、Renderbuffer |
| **Stencil Attachment** | Stencil输出 | Renderbuffer（通常） |
| **Depth-Stencil Attachment** | 深度+Stencil组合 | Texture2D、Renderbuffer |

### 5.4 绑定方式对比

```cpp
// 方式1：Texture2D绑定
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture2D, 0);

// 方式2：Texture Layer绑定（Array Texture的单层）
glFramebufferTextureLayer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, textureArray, 0, layerIndex);

// 方式3：Renderbuffer绑定
glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, renderbuffer);
```

### 5.5 特点和限制

**优点：**
- ✅ 统一管理多个渲染目标
- ✅ 支持多颜色附件（MRT - Multiple Render Targets）
- ✅ 可动态切换附件
- ✅ 支持离屏渲染（Off-screen Rendering）

**限制：**
- ❌ 所有附件必须相同尺寸
- ❌ 附件格式必须兼容
- ❌ GLES最少保证4个颜色附件（GL_MAX_COLOR_ATTACHMENTS >= 4，实际取决于实现，LumeRender定义为8）
- ❌ 某些格式组合不被支持

**适用场景：**
1. **离屏渲染**：渲染到纹理而非屏幕
2. **后期处理**：多pass渲染管线
3. **Deferred Rendering**：G-Buffer输出多附件
4. **Shadow Mapping**：渲染深度到纹理
5. **MSAA解析**：渲染到MSAA Renderbuffer，解析到Texture

---

## 六、核心区别对比总结

### 6.1 MSAA支持对比

| 对象 | MSAA支持 | GLES扩展需求 |
|------|---------|-------------|
| **Texture2D** | ❌ 不支持（GLES限制） | 需特殊扩展：`GL_EXT_multisampled_render_to_texture2` |
| **Texture Layer** | ❌ 不支持 | 无 |
| **Renderbuffer** | ✅ 支持 | 核心功能：`glRenderbufferStorageMultisample`（GLES 3.0+）或 EXT扩展：`glRenderbufferStorageMultisampleEXT` |
| **Framebuffer** | N/A（容器） | - |

### 6.2 绑定方式对比

| 对象 | 绑定函数 | 绑定参数 |
|------|---------|---------|
| **Texture2D** | `glFramebufferTexture2D` | `GL_TEXTURE_2D, texture, level` |
| **Texture Layer** | `glFramebufferTextureLayer` | `texture, level, layer` |
| **Renderbuffer** | `glFramebufferRenderbuffer` | `GL_RENDERBUFFER, renderbuffer` |

---

## 七、典型使用场景示例

### 7.1 离屏渲染（Texture2D + Framebuffer）

```cpp
// 创建Texture2D作为颜色附件
GLuint colorTexture;
glGenTextures(1, &colorTexture);
glBindTexture(GL_TEXTURE_2D, colorTexture);
glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1024, 1024, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);

// 创建Framebuffer
GLuint fbo;
glGenFramebuffers(1, &fbo);
glBindFramebuffer(GL_FRAMEBUFFER, fbo);

// 绑定Texture2D到Framebuffer
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, colorTexture, 0);

// 渲染到Texture2D
glCheckFramebufferStatus(GL_FRAMEBUFFER); // 检查完整性
// ... 执行渲染 ...

// 后续pass中使用Texture2D作为输入
glBindTexture(GL_TEXTURE_2D, colorTexture);
// Shader中采样 texture(uColorTexture, texCoord)
```

### 7.2 MSAA渲染（Renderbuffer + Framebuffer）

```cpp
// 创建MSAA Renderbuffer
GLuint msaaRenderbuffer;
glGenRenderbuffers(1, &msaaRenderbuffer);
glBindRenderbuffer(GL_RENDERBUFFER, msaaRenderbuffer);
glRenderbufferStorageMultisampleEXT(GL_RENDERBUFFER, 4, GL_RGBA8, 1024, 1024);

// 创建Resolve Texture（非MSAA）
GLuint resolveTexture;
glGenTextures(1, &resolveTexture);
glBindTexture(GL_TEXTURE_2D, resolveTexture);
glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1024, 1024, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);

// 创建MSAA FBO
GLuint msaaFbo;
glGenFramebuffers(1, &msaaFbo);
glBindFramebuffer(GL_FRAMEBUFFER, msaaFbo);
glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, msaaRenderbuffer);

// 创建Resolve FBO
GLuint resolveFbo;
glGenFramebuffers(1, &resolveFbo);
glBindFramebuffer(GL_FRAMEBUFFER, resolveFbo);
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, resolveTexture, 0);

// 渲染到MSAA Renderbuffer
glBindFramebuffer(GL_FRAMEBUFFER, msaaFbo);
// ... 执行渲染 ...

// 解析MSAA到Resolve Texture
glBindFramebuffer(GL_READ_FRAMEBUFFER, msaaFbo);
glBindFramebuffer(GL_DRAW_FRAMEBUFFER, resolveFbo);
glBlitFramebuffer(0, 0, 1024, 1024, 0, 0, 1024, 1024, GL_COLOR_BUFFER_BIT, GL_NEAREST);

// 后续pass使用Resolve Texture
glBindTexture(GL_TEXTURE_2D, resolveTexture);
```

### 7.3 多视图渲染（Texture Layer + Framebuffer）

```cpp
// 创建Array Texture（2层，用于VR左右眼）
GLuint vrTextureArray;
glGenTextures(1, &vrTextureArray);
glBindTexture(GL_TEXTURE_2D_ARRAY, vrTextureArray);
glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, GL_RGBA8, 1024, 1024, 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);

// 创建Framebuffer
GLuint vrFbo;
glGenFramebuffers(1, &vrFbo);
glBindFramebuffer(GL_FRAMEBUFFER, vrFbo);

// 渲染左眼（layer 0）
glFramebufferTextureLayer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, vrTextureArray, 0, 0);
// ... 渲染左眼 ...

// 渲染右眼（layer 1）
glFramebufferTextureLayer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, vrTextureArray, 0, 1);
// ... 渲染右眼 ...

// 后续采样左右眼
// Shader: texture(uVRTextureArray, vec3(texCoord, layerIndex))
```

---

## 八、LumeCoreSamples中的应用

### 8.1 Texture2D应用

**文件位置**：`submodules\LumeRender\src\gles\gpu_image_gles.cpp:103-164`

```cpp
// GpuImageGLES创建Texture2D (在构造函数中)
void GenerateImageStorage(DeviceGLES& device, const GpuImageDesc& desc, GpuImagePlatformDataGL& plat)
{
    const uint32_t sampleCount = ConvertSampleCountFlags(desc.sampleCountFlags);
    glGenTextures(1, &plat.image);

    const Math::UVec2 size2D { desc.width, desc.height };
    switch (desc.imageViewType) {
        case CORE_IMAGE_VIEW_TYPE_2D: {
            if (sampleCount > 1) {
                plat.type = GL_TEXTURE_2D_MULTISAMPLE;
                device.TexStorage2DMultisample(plat.image, plat.type, sampleCount, plat.internalFormat, size2D, true);
            } else {
                plat.type = GL_TEXTURE_2D;
                device.TexStorage2D(plat.image, plat.type, desc.mipCount, plat.internalFormat, size2D);
            }
            break;
        }
        // ... 其他imageViewType分支
    }
}
```

### 8.2 Renderbuffer应用

**文件位置**：`submodules\LumeRender\src\gles\gpu_image_gles.cpp:203-228`

```cpp
// GpuImageGLES创建Renderbuffer（在构造函数中）
// 条件：非Array、非Src/Dst、非Sampled、非Storage、非Input
if ((!isArray) && (!isSrc) && (!isDst) && (!isSample) && (!isStorage) && (!isInput)) {
    glGenRenderbuffers(1, &plat_.renderBuffer);
    glBindRenderbuffer(GL_RENDERBUFFER, plat_.renderBuffer);
    if (sampleCount > 1) {
        if (device_.HasExtension("GL_EXT_multisampled_render_to_texture2")) {
            glRenderbufferStorageMultisampleEXT(GL_RENDERBUFFER, sampleCount, plat_.internalFormat, width, height);
        } else {
            glRenderbufferStorageMultisample(GL_RENDERBUFFER, sampleCount, plat_.internalFormat, width, height);
        }
    } else {
        glRenderbufferStorage(GL_RENDERBUFFER, plat_.internalFormat, width, height);
    }
}
```

### 8.3 Texture Layer应用

**文件位置**：`submodules\LumeRender\src\gles\node_context_pool_manager_gles.cpp:312-318`

```cpp
// BindToFbo中处理Array Texture绑定到Framebuffer
if ((plat.type == GL_TEXTURE_2D_ARRAY) || (plat.type == GL_TEXTURE_2D_MULTISAMPLE_ARRAY)) {
    if (views) {
        glFramebufferTextureMultiviewOVR(
            GL_FRAMEBUFFER, attachType, plat.image, (GLint)image.mipLevel, (GLint)image.layer, (GLsizei)views);
    } else {
        glFramebufferTextureLayer(
            GL_FRAMEBUFFER, attachType, plat.image, (GLint)image.mipLevel, (GLint)image.layer);
    }
}
```

### 8.4 Framebuffer管理

**文件位置**：`submodules\LumeRender\src\gles\node_context_pool_manager_gles.cpp:422-488`

```cpp
// GenerateSubPassFBO创建Subpass的FBO
uint32_t GenerateSubPassFBO(DeviceGLES& device, LowlevelFramebufferGL& framebuffer,
    const RenderPassSubpassDesc& sb, const array_view<const BindImage> images,
    const size_t resolveAttachmentCount, const array_view<const uint32_t> imageMap,
    bool multisampledRenderToTexture)
{
    GLuint fbo;
    glGenFramebuffers(1, &fbo);
    device.BindFrameBuffer(fbo);

    // 绑定Color Attachments
    for (uint32_t idx = 0; idx < sb.colorAttachmentCount; ++idx) {
        const uint32_t ci = sb.colorAttachmentIndices[idx];
        drawBuffers[idx] = GL_COLOR_ATTACHMENT0 + colorAttachmentCount;
        if (original == EMPTY_ATTACHMENT) {
            BindToFbo(drawBuffers[idx], images[ci], ...);
        } else {
            BindToFboMultisampled(drawBuffers[idx], images[original], images[ci], ...);
        }
        ++colorAttachmentCount;
    }
    glDrawBuffers((GLsizei)sb.colorAttachmentCount, drawBuffers);

    // 绑定Depth Attachment
    if (sb.depthAttachmentCount == 1) {
        BindToFboMultisampled(bindType, images[original], images[di], ...);
    }

    if (!VerifyFBO()) {
        glDeleteFramebuffers(1, &fbo);
        fbo = 0U;
    }
    return fbo;
}
```

---

## 九、常见问题与最佳实践

### 9.1何时使用Texture vs Renderbuffer？

**决策规则：**

| 场景 | 推荐对象 | 原因 |
|------|---------|------|
| 需要后续Shader采样 | **Texture2D / Texture Layer** | Renderbuffer不可采样 |
| 不需要后续采样 | **Renderbuffer** | 性能可能更好，节省纹理资源 |
| 需要MSAA但不需采样 | **Renderbuffer (MSAA)** | GLES不支持Texture2D MSAA |
| 需要MSAA且需采样 | **特殊扩展 + Texture2D** | 使用 `GL_EXT_multisampled_render_to_texture2` |
| 需要多视图渲染 | **Texture Layer (Array)** | 多层共享存储，高效 |

### 9.2 Framebuffer完整性检查

**常见错误：**

```cpp
GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
switch (status) {
    case GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT:
        // 附件格式不兼容或尺寸为0
        break;
    case GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT:
        // 至少需要一个颜色附件
        break;
    case GL_FRAMEBUFFER_INCOMPLETE_DIMENSIONS:
        // 所有附件尺寸不一致
        break;
    case GL_FRAMEBUFFER_UNSUPPORTED:
        // 格式组合不被支持（如RGBA8 + DEPTH24_STENCIL8在某些设备）
        break;
}
```

### 9.3 性能优化建议

**最佳实践：**

1. **减少FBO切换**：
   ```cpp
   // ❌ 频繁切换FBO
   for (auto& pass : passes) {
       glBindFramebuffer(GL_FRAMEBUFFER, pass.fbo);
       RenderPass(pass);
   }

   // ✅ 合理规划，减少切换
   glBindFramebuffer(GL_FRAMEBUFFER, mainFbo);
   RenderAllPasses(mainFbo);
   ```

2. **合理使用Renderbuffer**：
   ```cpp
   // ✅ 深度附件：如果不需要后续采样，使用Renderbuffer
   glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depthRB);

   // ✅ MSAA颜色附件：使用Renderbuffer
   glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, msaaRB);
   ```

3. **Texture Layer优化多视图**：
   ```cpp
   // ✅ VR渲染：使用Array Texture，减少内存分配
   glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, GL_RGBA8, width, height, 2, ...);
   ```

---

## 十、参考资源

### 10.1 OpenGL ES规范

- [OpenGL ES 3.0 Specification](https://www.khronos.org/registry/OpenGL/specs/es/3.0/es_spec_3.0.pdf)
- [OpenGL ES 3.1 Specification](https://www.khronos.org/registry/OpenGL/specs/es/3.1/es_spec_3.1.pdf)

### 10.2 扩展文档

- `GL_EXT_multisampled_render_to_texture2` - MSAA纹理渲染扩展
- `GL_OVR_multiview_multisampled_render_to_texture` - VR多视图MSAA扩展

### 10.3 LumeCoreSamples相关文档

- `GL_ES_MSAA解析方法总结.md` - MSAA解析方法详解
- `GL后端FBO与Subpass处理详解.md` - FBO和Subpass处理流程
- `GL后端Shader编译流程详解.md` - Shader编译和绑定
