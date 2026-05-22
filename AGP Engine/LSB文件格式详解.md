# LSB文件格式详解

## 背景与问题引入

### Shader反射数据

**Shader反射数据（Reflection Data）** 是从编译后的Shader中提取的元数据，描述Shader的资源布局：

- **Descriptor Sets**：资源集的定义（set索引、binding索引、资源类型）
- **Push Constants**：推送常量的布局和大小
- **Specialization Constants**：特化常量的ID和类型
- **Vertex Inputs**：顶点输入属性的布局

反射数据用于运行时正确绑定Shader资源，是跨平台渲染系统的基础设施。

### LSB文件的作用

LumeRender采用SPIR-V作为统一Shader格式，需要配套的元数据文件支持跨平台资源绑定。**LSB（Layout Shader Binary）文件** 存储SPIR-V的反射数据，解决以下问题：

1. **跨平台兼容**：Vulkan和GL后端共享相同的资源布局信息
2. **运行时查找**：GL后端需要通过名称查找binding位置
3. **PipelineLayout构建**：Vulkan后端需要反射数据构建Descriptor Set Layout

### 为什么需要二进制格式？

LSB采用二进制格式而非JSON/XML等文本格式，原因：

- **加载效率**：二进制可直接内存映射，无需解析开销
- **体积紧凑**：数值直接存储为二进制，无文本冗余
- **版本兼容**：固定结构便于版本演进和向后兼容

### 本文档解决的问题

本文档详细解析LSB文件的二进制结构，包括：
- 文件头部和数据段布局
- 各数据段的具体格式（Descriptor Sets、Push Constants等）
- 版本差异（V0和V1格式）
- 如何从LSB提取PipelineLayout信息

---

## 核心概念

### Descriptor Set与Binding

Vulkan使用两级索引组织Shader资源：

| 层级 | 说明 | 示例 |
|------|------|------|
| **Descriptor Set** | 资源集合，对应一个Set索引 | Set 0 = 全局资源，Set 1 = 材质资源 |
| **Binding** | Set内的资源槽位 | binding 0 = Camera Buffer，binding 1 = Texture |

LSB文件存储每个Descriptor Set的所有Binding信息。

### Descriptor类型

| 类型 | Vulkan常量 | 说明 |
|------|-----------|------|
| **Uniform Buffer** | VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER | 只读全局参数 |
| **Storage Buffer** | VK_DESCRIPTOR_TYPE_STORAGE_BUFFER | 可读写数据缓冲 |
| **Texture/Sampler** | VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER | 纹理采样器 |
| **Storage Image** | VK_DESCRIPTOR_TYPE_STORAGE_IMAGE | 可读写图像 |
| **Input Attachment** | VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT | Subpass输入引用 |

### PipelineLayout

**PipelineLayout** 是Vulkan的资源绑定框架，定义：

- **Descriptor Set Layouts**：各Set的资源布局
- **Push Constant Range**：推送常量的范围和Stage可见性

LSB文件数据用于构建PipelineLayout对象，是创建Pipeline的前提。

### LSB文件结构

```
LSB文件二进制结构:

┌──────────────────────────────────────────────────┐
│ 文件头部 (16字节)                                 │
├──────────────────────────────────────────────────┤
│ tag[4]: 'rfl' + version                          │
│ type: Shader stage flags                         │
│ offsetPushConstants: 段偏移                       │
│ offsetSpecializationConstants: 段偏移             │
│ offsetDescriptorSets: 段偏移                      │
│ offsetInputs: 段偏移                              │
│ offsetLocalSize: 段偏移                           │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Push Constants段                                 │
├──────────────────────────────────────────────────┤
│ hasConstants: uint8 (是否有push constants)        │
│ byteSize: uint16 (字节大小)                       │
│ [数据内容...]                                     │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Specialization Constants段                       │
├──────────────────────────────────────────────────┤
│ constantCount: uint32                            │
│ for each constant:                               │
│   └─ id: uint32                                  │
│   └─ type: uint32 (BOOL/UINT32/INT32/FLOAT)      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Descriptor Sets段                                │
├──────────────────────────────────────────────────┤
│ descriptorSetCount: uint16                       │
│ for each set:                                    │
│   └─ set: uint16                                 │
│   └─ bindingCount: uint16                        │
│   └─ for each binding:                           │
│       └─ binding: uint16                         │
│       └─ descriptorType: uint16                  │
│       └─ descriptorCount: uint16                 │
│       └─ imageDimension: uint8 (V1)              │
│       └─ imageFlags: uint8 (V1)                  │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Vertex Inputs段                                  │
├──────────────────────────────────────────────────┤
│ inputCount: uint16                               │
│ for each input:                                  │
│   └─ location: uint16                            │
│   └─ format: uint16                              │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Local Size段 (Compute Shader)                    │
├──────────────────────────────────────────────────┤
│ x: uint32                                        │
│ y: uint32                                        │
│ z: uint32                                        │
└──────────────────────────────────────────────────┘
```

---

## 一、LSB文件格式

### 1.1 文件头部结构（16字节）

```cpp
struct ReflectionHeader {
    uint8_t tag[4];      // 'rfl' + version (如 "rfl\x01")
    uint16_t type;       // Shader stage flags
    uint16_t offsetPushConstants;
    uint16_t offsetSpecializationConstants;
    uint16_t offsetDescriptorSets;
    uint16_t offsetInputs;
    uint16_t offsetLocalSize;
};
```

**版本：**
- Version 0：基础格式，每个binding 6字节
- Version 1：扩展格式，每个binding 8字节（增加image dimension和flags）

---

## 二、数据段结构

### 2.1 Push Constants段

```
uint8_t  hasConstants     // 是否有push constants
uint16_t byteSize         // push constant字节大小
[数据内容...]
```

### 2.2 Specialization Constants段

```
uint32_t constantCount    // 常量数量
for each constant:
    uint32_t id           // constant ID
    uint32_t type         // 类型（BOOL=1, UINT32=2, INT32=3, FLOAT=4）
```

### 2.3 Descriptor Sets段

```
uint16_t descriptorSetCount    // descriptor set数量
for each descriptor set:
    uint16_t set               // set索引
    uint16_t bindingCount      // binding数量
    for each binding:
        // V0格式（6字节）
        uint16_t binding       // binding索引
        uint16_t descriptorType // descriptor类型
        uint16_t descriptorCount // descriptor数量

        // V1格式（8字节）
        uint16_t binding
        uint16_t descriptorType
        uint16_t descriptorCount
        uint8_t  imageDimension  // 图像维度
        uint8_t  imageFlags      // 图像标志
```

### 2.4 Vertex Inputs段

```
uint16_t inputCount    // 输入数量
for each input:
    uint16_t location  // location索引
    uint16_t format    // 格式值
```

### 2.5 Local Size段（Compute Shader）

```
uint32_t x    // workgroup size x
uint32_t y    // workgroup size y
uint32_t z    // workgroup size z
```

---

## 三、Descriptor Type编码

| 值 | 名称 | 说明 |
|----|------|------|
| 0 | SAMPLER | 纯采样器 |
| 1 | COMBINED_IMAGE_SAMPLER | 组合图像采样器 |
| 2 | SAMPLED_IMAGE | 可采样图像 |
| 3 | STORAGE_IMAGE | 存储图像 |
| 4 | UNIFORM_TEXEL_BUFFER | Uniform纹理缓冲 |
| 5 | STORAGE_TEXEL_BUFFER | 存储纹理缓冲 |
| 6 | UNIFORM_BUFFER | Uniform缓冲 |
| 7 | STORAGE_BUFFER | 存储缓冲（SSBO） |
| 8 | UNIFORM_BUFFER_DYNAMIC | Dynamic Uniform缓冲 |
| 9 | STORAGE_BUFFER_DYNAMIC | Dynamic存储缓冲 |
| 10 | INPUT_ATTACHMENT | 输入附件 |
| 1000150000 | ACCELERATION_STRUCTURE | 加速结构 |

---

## 四、Image Dimension编码

| 值 | 名称 |
|----|------|
| 0 | DIMENSION_1D |
| 1 | DIMENSION_2D |
| 2 | DIMENSION_3D |
| 3 | DIMENSION_CUBE |
| 4 | DIMENSION_RECT |
| 5 | DIMENSION_BUFFER |
| 6 | DIMENSION_SUBPASS |

---

## 五、Image Flags编码

| 位 | 名称 |
|----|------|
| 0x01 | IMAGE_DEPTH |
| 0x02 | IMAGE_ARRAY |
| 0x04 | IMAGE_MULTISAMPLE |
| 0x08 | IMAGE_SAMPLED |
| 0x10 | IMAGE_LOAD_STORE |

---

## 六、解析工具实现

### 6.1 关键解析函数

```python
def read_uint16(data: bytes, offset: int) -> Tuple[int, int]:
    value = struct.unpack_from("<H", data, offset)[0]
    return value, offset + 2

def read_uint32(data: bytes, offset: int) -> Tuple[int, int]:
    value = struct.unpack_from("<I", data, offset)[0]
    return value, offset + 4
```

### 6.2 Descriptor Set解析（V1格式）

```python
def parse_descriptor_set_v1(data, ptr):
    set_idx, ptr = read_uint16(data, ptr)
    binding_count, ptr = read_uint16(data, ptr)

    bindings = []
    for _ in range(binding_count):
        binding, ptr = read_uint16(data, ptr)
        desc_type, ptr = read_uint16(data, ptr)
        desc_count, ptr = read_uint16(data, ptr)
        image_dim = data[ptr]
        ptr += 1
        image_flags = data[ptr]
        ptr += 1

        bindings.append({
            'binding': binding,
            'descriptor_type': desc_type,
            'descriptor_count': desc_count,
            'image_dimension': image_dim,
            'image_flags': image_flags
        })

    return set_idx, bindings, ptr
```

---

## 七、实际解析示例

### 7.1 解析结果示例

```
PipelineLayout:
  Shader Stage: FRAGMENT_BIT (0x00000010)
  Version: 1

  Descriptor Sets:
    Set 0:
      Binding 0: UNIFORM_BUFFER (count=1)
      Binding 6: STORAGE_BUFFER (count=1)
      Binding 7: COMBINED_IMAGE_SAMPLER [IMAGE_SAMPLED, DIMENSION_2D]

    Set 3:
      Binding 0: STORAGE_BUFFER (count=1)
      Binding 1: STORAGE_BUFFER (count=1)
      Binding 2: STORAGE_BUFFER (count=1)
      Binding 3: STORAGE_BUFFER (count=1)
```

### 7.2 与shaderpl对比

LSB文件提取的PipelineLayout应与对应的shaderpl文件匹配：

```
shaderpl定义:
  Set 3:
    Binding 0: storage_buffer ✓
    Binding 1: storage_buffer ✓
    Binding 2: storage_buffer ✓
    Binding 3: storage_buffer ✓
```

---

## 八、解析工具使用

### 8.1 基本用法

```bash
# 解析单个LSB文件
python lsb_parser.py path/to/shader.spv.lsb

# JSON格式输出
python lsb_parser.py path/to/shader.spv.lsb --json

# 输出到文件
python lsb_parser.py path/to/shader.spv.lsb --json --output result.json
```

### 8.2 输出内容

- Shader Stage：shader类型
- Push Constant：byte size
- Descriptor Sets：所有descriptor set的bindings
- Specialization Constants：constant ID和类型
- Vertex Inputs：location和format
- Local Size：compute shader的workgroup size

---

## 九、常见问题

### 9.1 解析结果与SPIR-V不符

**原因：** LumeShaderCompiler生成LSB时可能存在bug

**排查：**
1. 使用`spirv-reflect`检查SPIR-V中的实际descriptor类型
2. 对比shaderpl文件定义
3. 确认LSB文件是否正确生成

### 9.2 Descriptor Type显示错误

**症状：** STORAGE_BUFFER显示为COMBINED_IMAGE_SAMPLER

**原因：** Shader源码中有重复的set/binding声明，LumeShaderCompiler可能记录了错误的声明

**解决：** 修复LumeShaderCompiler，确保从SPIR-V而非源码提取reflection data

---

## 十、工具代码位置

解析工具已创建在：`lsb_parser.py`

---

## 十一、实践经验

1. **调试reflection问题**：对比LSB、spirv-reflect输出、shaderpl三者的一致性
2. **验证binding配置**：确保LSB提取的类型与实际shader使用的资源类型一致
3. **自动化检查**：可批量解析所有LSB文件，检查是否有异常的descriptor类型
