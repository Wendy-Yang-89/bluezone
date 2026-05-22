# LLOIT Shader Reflection Data错误分析与修复

**状态：已修复**

## 背景

LSB（Lume Shader Binary）反射数据是LumeShaderCompiler从编译后的SPIR-V中提取的资源描述信息，记录了shader中各descriptor set的binding类型、名称等元数据。GL后端在运行时依赖LSB反射数据来确定资源绑定类型和进行binding修复，因此反射数据的准确性直接决定GL后端能否正确绑定SSBO、纹理等GPU资源。

---

## 问题现象

`core3d_dm_fw_lloit.frag.spv.lsb`反射出的Set 3 descriptor类型为`COMBINED_IMAGE_SAMPLER`，实际应为`STORAGE_BUFFER`。

| Set | Binding | 反射类型（错误） | 正确类型 |
|-----|---------|----------------|---------|
| 3 | 0 | COMBINED_IMAGE_SAMPLER | STORAGE_BUFFER (LinkedListHeadSBO) |
| 3 | 1 | COMBINED_IMAGE_SAMPLER | STORAGE_BUFFER (LinkedListSBO) |
| 3 | 2 | COMBINED_IMAGE_SAMPLER | STORAGE_BUFFER (LinkedListCounterSBO) |
| 3 | 3 | COMBINED_IMAGE_SAMPLER | STORAGE_BUFFER (LinkedListPixelCounterSBO) |

---

## 根本原因

### 问题链路

```
Shader源码 → glslang编译 → SPIR-V（正确）
                                ↓
                          spirv-reflect（正确识别）
                                ↓
                    LumeShaderCompiler生成.lsb（BUG）
                                ↓
                    reflection data错误
```

| 数据源 | Set 3类型 | 状态 |
|--------|----------|------|
| SPIR-V文件 | StorageBuffer | ✓ 正确 |
| spirv-reflect输出 | VK_DESCRIPTOR_TYPE_STORAGE_BUFFER | ✓ 正确 |
| shaderpl文件 | storage_buffer | ✓ 正确 |
| **.lsb文件（修复前）** | COMBINED_IMAGE_SAMPLER | **✗ 错误** |
| **.lsb文件（修复后）** | STORAGE_BUFFER | **✓ 正确** |

### Shader Include结构导致Set 3冲突

`core3d_dm_fw_lloit.frag`的include顺序：

```glsl
// 1. 先include fw_frag.h
#include "core3d_dm_fw_frag.h"

// 2. 然后include OIT layout
#include "3d/shaders/common/3d_dm_oit_layout_common.h"
```

**`core3d_dm_fw_frag.h`的内容：**

```glsl
// 第34行：无条件include env_frag_layout_common.h
#include "3d/shaders/common/3d_dm_env_frag_layout_common.h"

// 第42-47行：条件include OIT layout（条件是WBOIT，不是LLOIT！）
#if (CORE3D_DM_WBOIT_FRAG_LAYOUT == 1)
    #include "3d/shaders/common/3d_dm_oit_layout_common.h"
#else
    layout(location = 0) out vec4 outColor;
    layout(location = 1) out vec4 outVelocityNormal;
#endif
```

**Include链路图：**

```
core3d_dm_fw_lloit.frag
    │
    ├─→ core3d_dm_fw_frag.h
    │       │
    │       ├─→ 3d_dm_frag_layout_common.h (Set 0-2 UBO/Image)
    │       │
    │       ├─→ 3d_dm_env_frag_layout_common.h
    │       │       │
    │       │       └─→ Set 3: sampler2D/samplerCube（先定义，LLOIT中未使用）
    │       │
    │       └─→ #if WBOIT（条件不满足，不include OIT）
    │
    └─→ 3d_dm_oit_layout_common.h
            │
            └─→ Set 3: buffer SSBO（后定义，LLOIT中实际使用）
```

### 两个文件定义了相同的Set 3, Binding 0-3

**`3d_dm_env_frag_layout_common.h`（先被include）：**

```glsl
#ifdef VULKAN
layout(set = 3, binding = 0) uniform sampler2D uImgSampler;
layout(set = 3, binding = 1) uniform samplerCube uImgCubeSampler;
layout(set = 3, binding = 2) uniform samplerCube uImgCubeSamplerBlender;
layout(set = 3, binding = 3) uniform sampler2D uImgTLutSampler;
#endif
```

类型：**COMBINED_IMAGE_SAMPLER**

**`3d_dm_oit_layout_common.h`（后被include）：**

```glsl
#ifdef VULKAN
#if (CORE3D_DM_LLOIT_FRAG_LAYOUT == 1)
layout(set = 3, binding = 0, std430) buffer LinkedListHeadSBO { uint LinkedListHead[]; };
layout(set = 3, binding = 1, std430) buffer LinkedListSBO { DefaultOitLinkedListNodeStruct nodes[]; };
layout(set = 3, binding = 2, std430) buffer LinkedListCounterSBO { uint nodeIdx; uint maxNodeIdx; };
layout(set = 3, binding = 3, std430) buffer LinkedListPixelCounterSBO { uint PixelNodeIdx[]; };
#endif
#endif
```

类型：**STORAGE_BUFFER**

---

## 为什么SPIR-V和spirv-reflect正确，但LSB错误？

### SPIR-V编译器行为（正确）

glslang编译时：
1. 未使用的env sampler声明被优化剔除（dead code elimination）
2. 实际使用的OIT SSBO声明被保留
3. SPIR-V正确记录StorageBuffer类型

### spirv-reflect行为（正确）

从SPIR-V提取reflection时，正确识别实际使用的资源类型：

```
Set 3:
  Binding 0: VK_DESCRIPTOR_TYPE_STORAGE_BUFFER (LinkedListHeadSBO)
  Binding 1: VK_DESCRIPTOR_TYPE_STORAGE_BUFFER (LinkedListSBO)
  Binding 2: VK_DESCRIPTOR_TYPE_STORAGE_BUFFER (LinkedListCounterSBO)
  Binding 3: VK_DESCRIPTOR_TYPE_STORAGE_BUFFER (LinkedListPixelCounterSBO)
```

### LumeShaderCompiler的bug

生成.lsb reflection data时：
1. **未正确处理SPIR-V中优化剔除的资源** — 可能从shader源码而非SPIR-V提取reflection
2. **按include顺序而非实际使用情况处理声明** — env_frag_layout先include，被错误记录
3. **缺少对unused资源的过滤** — 未使用的env sampler也被记录到reflection

---

## 为什么Vulkan正常但GL失败

### Vulkan后端（不受影响）

Vulkan运行时使用正确数据：
1. **shaderpl文件定义的PipelineLayout** — Set 3定义为storage_buffer ✓
2. **SPIR-V中的实际资源** — StorageBuffer ✓

即使LSB反射数据错误，Vulkan运行时：
- PipelineLayout由shaderpl文件定义（正确）
- Descriptor绑定基于shaderpl而非.lsb
- SPIR-V shader正确使用SSBO

### GL后端（受影响）

GL backend依赖.lsb reflection data：
1. 生成GLSL时的binding修复（binding=11问题）
2. 确定resource绑定类型

LSB错误显示为COMBINED_IMAGE_SAMPLER时：
- GL backend尝试绑定texture而非buffer
- 导致SSBO绑定失败
- LLOIT渲染失败

---

## 解决方案

### 方案A：修改`core3d_dm_fw_frag.h`（推荐）

添加LLOIT条件判断，避免env sampler与OIT SSBO冲突：

```glsl
// 修改第34行附近：LLOIT时不include env layout
#ifndef CORE3D_DM_LLOIT_FRAG_LAYOUT
#include "3d/shaders/common/3d_dm_env_frag_layout_common.h"
#endif

// 修改第42行附近：扩展OIT条件
#if (CORE3D_DM_WBOIT_FRAG_LAYOUT == 1) || (CORE3D_DM_LLOIT_FRAG_LAYOUT == 1)
    #include "3d/shaders/common/3d_dm_oit_layout_common.h"
#else
    layout(location = 0) out vec4 outColor;
    layout(location = 1) out vec4 outVelocityNormal;
#endif
```

优点：LLOIT shader不需要environment samplers；不改变descriptor set布局；保持与其他shader一致性。

### 方案B：修改OIT layout使用不同Set

将OIT SSBO改到Set 4或其他未使用的set：

```glsl
// 3d_dm_oit_layout_common.h
#if (CORE3D_DM_LLOIT_FRAG_LAYOUT == 1)
layout(set = 4, binding = 0, std430) buffer LinkedListHeadSBO { ... };
layout(set = 4, binding = 1, std430) buffer LinkedListSBO { ... };
...
#endif
```

缺点：需要修改整个render pass的descriptor set layout。

### 方案C：修改`core3d_dm_fw_lloit.frag`

不使用`core3d_dm_fw_frag.h`，直接定义所需的bindings（类似`core3d_dm_fullscreen_lloit.frag`的做法）。

缺点：代码重复，维护成本高。

### 实际实施的修复

**修复LumeShaderCompiler**生成.lsb reflection data的逻辑，确保：
1. 从SPIR-V而非shader源码提取reflection
2. 过滤未使用的资源声明
3. 正确识别StorageBuffer类型

---

## 修复验证

修复后重新编译shader，.lsb文件正确显示：

```
Set 3:
  Binding 0: STORAGE_BUFFER (type=7) ✓
  Binding 1: STORAGE_BUFFER (type=7) ✓
  Binding 2: STORAGE_BUFFER (type=7) ✓
  Binding 3: STORAGE_BUFFER (type=7) ✓
```

验证方法：重新编译shader并使用lsb_parser.py检查Set 3的descriptor_type应为STORAGE_BUFFER (type=7)。

---

## 受影响Shader

| Shader | 是否受影响 | 原因 |
|--------|-----------|------|
| `core3d_dm_fw_lloit.frag` | ✓ | 使用LLOIT layout，Set 3冲突 |
| `core3d_dm_fw_lloit_bl.frag` | ✓ | 使用LLOIT layout，Set 3冲突 |
| `core3d_dm_fw_wboit.frag` | ✓ | env layout同样无条件include |
| `core3d_dm_fullscreen_lloit.frag` | ✗ | 直接定义bindings，无冲突 |
| `core3d_dm_fullscreen_wboit.frag` | ✗ | 直接定义bindings，无冲突 |

---

## 总结

**问题根源**：LumeShaderCompiler生成.lsb反射数据时的bug——未正确从SPIR-V提取实际使用的资源类型，错误记录了因include顺序先出现但未被使用的env sampler声明（COMBINED_IMAGE_SAMPLER），覆盖了实际使用的OIT SSBO声明（STORAGE_BUFFER）。

**影响范围**：Vulkan后端不受影响（使用shaderpl和SPIR-V）；GL后端受影响（依赖.lsb反射数据）。

**修复状态**：已修复LumeShaderCompiler，反射数据现已正确。
