# Shader资源声明与PipelineLayout配置指南

## 概述

本文档详细说明Shader中的资源声明（set、binding、descriptor type）如何映射到PipelineLayout配置文件（shaderpl），确保资源绑定的正确性。

---

## 一、Shader资源声明解析

### 1.1 基本声明格式

```glsl
layout(set = X, binding = Y, [修饰符]) [类型] [变量名];
```

### 1.2 Descriptor Type映射表

| Shader声明 | shaderpl descriptorType | 说明 |
|-----------|------------------------|------|
| `uniform sampler2D` | `combined_image_sampler` | 组合图像采样器 |
| `uniform texture2D` | `sampled_image` | 纯纹理 |
| `uniform sampler` | `sampler` | 纯采样器 |
| `layout(std430) buffer` | `storage_buffer` | SSBO |
| `layout(std140) uniform` | `uniform_buffer` | UBO |
| `layout(std140) uniform` (dynamic) | `uniform_buffer_dynamic` | Dynamic UBO |
| `uniform image2D` | `storage_image` | 存储图像 |

---

## 二、修饰符解析

### 2.1 std140 vs std430

| 修饰符 | 用于 | 对齐规则 |
|--------|------|---------|
| `std140` | UBO | 严格对齐，每元素16字节边界 |
| `std430` | SSBO | 紧凑布局，适合大数组 |

### 2.2 coherent

```glsl
layout(set = 3, binding = 0, std430) coherent buffer LinkedListHeadSBO {
    uint LinkedListHead[];
};
```

**说明：** coherent确保跨线程的内存可见性，用于原子操作场景。

### 2.3 Image Dimension Flags

| Shader声明 | shaderpl additionalDescriptorTypeFlags |
|-----------|----------------------------------------|
| `sampler2D` | `image_dimension_2d_bit` |
| `samplerCube` | `image_dimension_cube_bit` |
| `sampler3D` | `image_dimension_3d_bit` |
| `sampler2DArray` | `image_dimension_2d_bit, image_array_bit` |

---

## 三、Shaderpl配置示例

### 3.1 Set 0 - 基础Uniform Buffer

```json
{
    "set": 0,
    "bindings": [
        { "binding": 0, "descriptorType": "uniform_buffer", "descriptorCount": 1,
          "shaderStageFlags": "vertex_bit|fragment_bit" },
        { "binding": 1, "descriptorType": "uniform_buffer", "descriptorCount": 1,
          "shaderStageFlags": "vertex_bit|fragment_bit" }
    ]
}
```

### 3.2 Set 2 - Material Textures

```json
{
    "set": 2,
    "bindings": [
        { "binding": 0, "descriptorType": "combined_image_sampler", "descriptorCount": 1,
          "shaderStageFlags": "fragment_bit",
          "additionalDescriptorTypeFlags": "image_dimension_2d_bit" },
        { "binding": 1, "descriptorType": "combined_image_sampler", "descriptorCount": 10,
          "shaderStageFlags": "fragment_bit",
          "additionalDescriptorTypeFlags": "image_dimension_2d_bit" }
    ]
}
```

### 3.3 Set 3 - OIT Storage Buffers

```json
{
    "set": 3,
    "bindings": [
        { "binding": 0, "descriptorType": "storage_buffer", "descriptorCount": 1,
          "shaderStageFlags": "fragment_bit" },
        { "binding": 1, "descriptorType": "storage_buffer", "descriptorCount": 1,
          "shaderStageFlags": "fragment_bit" },
        { "binding": 2, "descriptorType": "storage_buffer", "descriptorCount": 1,
          "shaderStageFlags": "fragment_bit" },
        { "binding": 3, "descriptorType": "storage_buffer", "descriptorCount": 1,
          "shaderStageFlags": "fragment_bit" }
    ]
}
```

---

## 四、Shader Stage Flags

### 4.1 标志位定义

| 值 | shaderpl字符串 | Shader宏 |
|----|---------------|----------|
| 0x01 | `vertex_bit` | `CORE_SHADER_STAGE_VERTEX_BIT` |
| 0x10 | `fragment_bit` | `CORE_SHADER_STAGE_FRAGMENT_BIT` |
| 0x20 | `compute_bit` | `CORE_SHADER_STAGE_COMPUTE_BIT` |

### 4.2 组合使用

```json
"shaderStageFlags": "vertex_bit|fragment_bit|compute_bit"
```

---

## 五、Dynamic Buffer配置

### 5.1 Shader声明

```glsl
layout(set = 1, binding = 0, std140) uniform uMeshStructData {
    DefaultMaterialMeshStruct uMeshMatrix;
};
```

### 5.2 shaderpl配置（Dynamic）

```json
{
    "binding": 0,
    "descriptorType": "uniform_buffer_dynamic",
    "descriptorCount": 1,
    "shaderStageFlags": "vertex_bit|fragment_bit"
}
```

**说明：** Dynamic buffer允许在绑定时指定偏移量，适合per-object数据。

---

## 六、Storage Image配置

### 6.1 Shader声明

```glsl
layout(set = 3, binding = 0, rgba32f) uniform image2D LinkedListHeadImage;
```

### 6.2 shaderpl配置

```json
{
    "binding": 0,
    "descriptorType": "storage_image",
    "descriptorCount": 1,
    "shaderStageFlags": "fragment_bit",
    "additionalDescriptorTypeFlags": "image_dimension_2d_bit"
}
```

---

## 七、配置检查清单

### 7.1 声明与配置匹配

| 检查项 | Shader | shaderpl |
|--------|--------|----------|
| Set索引 | 一致 ✓ | 一致 ✓ |
| Binding索引 | 一致 ✓ | 一致 ✓ |
| Descriptor Type | 一致 ✓ | 一致 ✓ |
| Descriptor Count | 一致 ✓ | 一致 ✓ |
| Image Flags | 匹配 ✓ | 匹配 ✓ |

### 7.2 常见配置错误

**错误1：类型不匹配**
```
Shader: layout(std430) buffer (SSBO)
shaderpl: "descriptorType": "combined_image_sampler" ✗
```

**错误2：Set/Binding冲突**
```
Set 3 Binding 0 在多个shaderpl文件中有不同定义 ✗
```

**错误3：遗漏Flags**
```
Shader: samplerCube
shaderpl: 缺少 "image_dimension_cube_bit" ✗
```

---

## 八、RenderSlot关联

### 8.1 shaderpl中的renderSlot定义

```json
{
    "renderSlot": "CORE3D_RS_DM_FW_OPAQUE",
    "renderSlotDefault": true
}
```

### 8.2 RenderSlot对应Shader

| RenderSlot | Shader文件 |
|-----------|-----------|
| `CORE3D_RS_DM_FW_OPAQUE` | `core3d_dm_fw.frag` |
| `CORE3D_RS_DM_FW_TRANSLUCENT_WBOIT` | `core3d_dm_fw_wboit.frag` |
| `CORE3D_RS_DM_FW_TRANSLUCENT_LLOIT` | `core3d_dm_fw_lloit.frag` |
| `CORE3D_RS_DM_ENV` | `core3d_dm_env.frag` |

---

## 九、实践经验

1. **新增Shader资源时**：先在shaderpl中添加对应binding配置
2. **验证配置**：使用lsb_parser.py检查LSB与shaderpl一致性
3. **避免冲突**：确保同一set/binding只定义一次
4. **Debug工具**：启用`RENDER_VALIDATION_ENABLED`检查绑定错误

---

## 十、相关文件位置

| 文件类型 | 位置 |
|---------|------|
| Shader源码 | `assets/3d/shaders/shader/*.frag` |
| shaderpl配置 | `assets/3d/pipelinelayouts/*.shaderpl` |
| LSB reflection | `assets/3d/shaders/shader/*.spv.lsb` |

---

## 十一、配置模板

### 11.1 新增Binding模板

```json
{
    "binding": X,
    "descriptorType": "[type]",
    "descriptorCount": Y,
    "shaderStageFlags": "[flags]",
    "additionalDescriptorTypeFlags": "[flags]"  // 如果是image类型
}
```

### 11.2 新增Set模板

```json
{
    "set": X,
    "bindings": [
        // binding配置列表
    ]
}
```