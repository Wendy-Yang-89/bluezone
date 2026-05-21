# Shader句柄查找机制详解

## 背景与问题引入

### Shader句柄概念

**Shader句柄（Shader Handle）** 是LumeRender的Shader资源标识：

- 类型为 `RenderHandle` 或 `RenderHandleReference`
- 封装Shader在资源管理器中的索引
- 用于Shader绑定、Pipeline创建等操作

句柄是渲染系统访问Shader资源的唯一入口。

### 查找机制的作用

渲染过程中需要根据不同条件查找Shader：

| 查找场景 | 输入 | 输出 |
|---------|------|------|
| **材质渲染** | ShaderState + RenderSlot | ShaderVariant句柄 |
| **Pipeline创建** | ShaderState句柄 | ShaderModule句柄 |
| **变体切换** | 基础Shader + RenderSlot | 变体Shader句柄 |

`GetShaderHandle` 函数是Shader查找的核心接口，支持多种查找路径。

### 多路径查找需求

Shader查找涉及多种匹配路径：

1. **直接匹配**：ShaderState直接关联RenderSlot
2. **变体继承**：通过BaseShaderHandle查找继承链
3. **回退机制**：未找到时返回空句柄或默认Shader

复杂查找逻辑需要清晰的优先级和回退策略。

### 本文档解决的问题

本文档详细分析 `GetShaderHandle` 函数的实现逻辑：

- 句柄类型验证和早期退出
- RenderSlot ID匹配检查
- BaseShaderHandle继承链查找
- Compute Shader的特殊处理

---

## 核心概念

### RenderHandle

**RenderHandle** 是资源的轻量级标识：

| 属性 | 说明 |
|------|------|
| **类型** | 64位整数（type + index + id） |
| **类型字段** | 区分Shader/GraphicsState/Texture等 |
| **索引字段** | 资源在管理器数组中的位置 |

RenderHandle通过位操作提取类型和索引，高效访问资源。

### RenderHandleReference

**RenderHandleReference** 是带引用计数的句柄：

- 继承RenderHandle的所有功能
- 自动管理资源生命周期
- 用于需要长期持有Shader的场景

RenderHandleReference确保Shader不会被过早销毁。

### ShaderStateObject

**ShaderStateObject** 是Shader的配置容器：

- 包含Shader句柄和GraphicsState句柄
- 关联RenderSlot ID
- 存储变体索引和特化常量

ShaderStateObject是材质绑定的核心数据结构。

### RenderSlot ID

**RenderSlot ID** 是渲染槽位的数字标识：

- 通过 `GetRenderSlotId(renderSlotName)` 获取
- 用于Shader查找时的槽位匹配
- 不同渲染场景使用不同RenderSlot ID

典型RenderSlot ID：
- `CORE3D_RS_DM_OPAQUE` = 0（Opaque渲染）
- `CORE3D_RS_DM_TRANSLUCENT` = 1（Translucent渲染）

### Shader查找流程

```
ShaderManager::GetShaderHandle 查找流程:

┌──────────────────────────────────────────────────┐
│ 输入: handle + renderSlotId                      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│ Step 1: 类型验证                                          │
├──────────────────────────────────────────────────────────┤
│ handleType = GetHandleType(handle)                       │
│ if (不是SHADER_STATE_OBJECT或COMPUTE_SHADER_STATE_OBJECT) │
│   └─► 返回: 空句柄 (早期退出)                              │
│                                                          │
│ 类型正确则继续                                            │
└──────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 2: 提取索引                                  │
├──────────────────────────────────────────────────┤
│ index = GetIndexPart(handle)                     │
│ ownBaseShaderHandle = 初始化                      │
│ addBaseShaderHandle = 初始化                      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 3: 根据类型处理                              │
├──────────────────────────────────────────────────┤
│                                                  │
│ Graphics Shader:                                 │
│   └─ 获取clientData[index]                       │
│   └─ if (renderSlotId匹配) → 返回rhr             │ 
│   └─ 获取ownBaseShaderHandle                     │
│   └─ 获取addBaseShaderHandle                     │
│                                                  │
│ Compute Shader:                                  │
│   └─ 获取computeShaderMappings[index]            │
│   └─ if (renderSlotId匹配) → 返回rhr             │
│   └─ 获取baseShaderHandle                        │
│                                                  │
│ 未直接匹配则继续                                  │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: BaseShader回溯查找                           │
├─────────────────────────────────────────────────────┤
│ GetBaseShaderMatchedSlotHandle(ownBaseShaderHandle) │
│   └─► 查找继承链匹配                                 │
│                                                     │
│ GetBaseShaderMatchedSlotHandle(addBaseShaderHandle) │
│   └─► 查找外部变体匹配                                │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ 返回: 匹配的ShaderHandleReference                 │
└──────────────────────────────────────────────────┘
```

---

## 函数签名
```cpp
RenderHandleReference ShaderManager::GetShaderHandle(const RenderHandle& handle, const uint32_t renderSlotId) const
```

## 功能概述
该函数用于根据给定的渲染句柄和渲染槽位ID，获取对应的渲染句柄引用。它支持通过基础着色器变体进行查找，提供了灵活的着色器句柄解析机制。

## 输入参数
- `handle`: 渲染句柄，用于标识着色器状态对象
- `renderSlotId`: 渲染槽位ID，用于匹配特定的渲染槽位

## 返回值
- `RenderHandleReference`: 渲染句柄引用，如果未找到匹配则返回空引用

## 详细逻辑流程

### 1. 句柄类型验证
```cpp
const RenderHandleType handleType = RenderHandleUtil::GetHandleType(handle);
if ((handleType != RenderHandleType::COMPUTE_SHADER_STATE_OBJECT) &&
    (handleType != RenderHandleType::SHADER_STATE_OBJECT)) {
    return {}; // early out
(}
```
- 首先获取句柄类型
- 如果不是计算着色器状态对象或着色器状态对象，直接返回空引用
- 这是一个早期退出机制，避免无效处理

### 2. 提取索引和初始化变量
```cpp
const uint32_t index = RenderHandleUtil::GetIndexPart(handle);
RenderHandle ownBaseShaderHandle;
RenderHandle addBaseShaderHandle;
```
- 从句柄中提取索引部分
- 初始化两个基础着色器句柄变量

### 3. 检查自身有效性并获取基础着色器句柄

#### 对于计算着色器：
```cpp
if ((handleType == RenderHandleType::COMPUTE_SHADER_STATE_OBJECT) &&
    (index < static_cast<uint32_t>(computeShaderMappings_.clientData.size()))) {
    const auto& ref = computeShaderMappings_.clientData[index];
    if (ref.renderSlotId == renderSlotId) {
        return ref.rhr; // early out
    }
    ownBaseShaderHandle = ref.ownBaseShaderHandle;
    addBaseShaderHandle = ref.addBaseShaderHandle;
}
```
- 检查索引是否在计算着色器映射数据范围内
- 如果渲染槽位ID匹配，直接返回对应的渲染句柄引用
- 否则提取自身基础着色器句柄和附加基础着色器句柄

#### 对于图形着色器：
```cpp
else if ((handleType == RenderHandleType::SHADER_STATE_OBJECT) &&
         (index < static_cast<uint32_t>(shaderMappings_.clientData.size()))) {
    const auto& ref = shaderMappings_.clientData[index];
    if (ref.renderSlotId == renderSlotId) {
        return ref.rhr; // early out
    }
    ownBaseShaderHandle = ref.ownBaseShaderHandle;
    addBaseShaderHandle = ref.addBaseShaderHandle;
}
```
- 类似的逻辑，但使用图形着色器映射数据

### 4. 基础着色器变体匹配函数
```cpp
auto GetBaseShaderMatchedSlotHandle = [](const auto& hashToShaderVariant, const auto& clData,
                                          const RenderHandle baseShaderHandle, const uint32_t renderSlotId) {
    PLUGIN_ASSERT(RenderHandleUtil::IsValid(baseShaderHandle));

    RenderHandleReference rhr;
    const uint64_t hash = HashHandleAndSlot(baseShaderHandle, renderSlotId);
    if (const auto iter = hashToShaderVariant.find(hash); iter != hashToShaderVariant.cend()) {
        const uint32_t arrayIndex = RenderHandleUtil::GetIndexPart(iter->second);
        if (arrayIndex < clData.size() && (clData[arrayIndex].renderSlotId == renderSlotId)) {
            rhr = clData[arrayIndex].rhr;
        }
    }
    return rhr;
};
```
这是一个lambda函数，用于：
- 断言基础着色器句柄的有效性
- 计算基础着色器句柄和渲染槽位ID的哈希值
- 在哈希表中查找匹配的着色器变体
- 验证找到的索引和渲染槽位ID是否匹配
- 返回对应的渲染句柄引用

### 5. 通过基础着色器变体查找匹配

#### 对于计算着色器：
```cpp
if (handleType == RenderHandleType::COMPUTE_SHADER_STATE_OBJECT) {
    if (RenderHandleUtil::IsValid(ownBaseShaderHandle)) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, computeShaderMappings_.clientData, ownBaseShaderHandle, renderSlotId);
    }
    if ((!slotHandle) && (RenderHandleUtil::IsValid(addBaseShaderHandle))) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, computeShaderMappings_.clientData, addBaseShaderHandle, renderSlotId);
    }
}
```
- 首先尝试使用自身基础着色器句柄查找
- 如果未找到且附加基础着色器句柄有效，则尝试使用附加基础着色器句柄

#### 对于图形着色器：
```cpp
else if (handleType == RenderHandleType::SHADER_STATE_OBJECT) {
    if (RenderHandleUtil::IsValid(ownBaseShaderHandle)) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, shaderMappings_.clientData, ownBaseShaderHandle, renderSlotId);
    }
    if ((!slotHandle) && (RenderHandleUtil::IsValid(addBaseShaderHandle))) {
        slotHandle = GetBaseShaderMatchedSlotHandle(
            hashToShaderVariant_, shaderMappings_.clientData, addBaseShaderHandle, renderSlotId);
    }
}
```
- 相同的逻辑，但使用图形着色器映射数据

### 6. 返回结果
```cpp
return slotHandle;
```

## 关键特性

1. **双重查找机制**：
   - 直接匹配：首先尝试直接匹配渲染槽位ID
   - 基础着色器查找：如果直接匹配失败，通过基础着色器变体进行查找

2. **多级回退策略**：
   - 自身基础着色器句柄 → 附加基础着色器句柄
   - 确保最大可能的匹配机会

3. **类型安全**：
   - 明确区分计算着色器和图形着色器
   - 使用不同的映射数据结构

4. **性能优化**：
   - 多个早期退出点
   - 使用哈希表加速查找
   - 避免不必要的计算

5. **错误处理**：
   - 边界检查（索引范围验证）
   - 句柄有效性验证
   - 断言确保关键条件

## 使用场景
该函数主要用于：
- 着色器资源管理
- 渲染管线状态查询
- 着色器变体解析
- 多槽位渲染系统中的着色器句柄解析

## 注意事项
- 函数是const成员函数，不修改对象状态
- 依赖于RenderHandleUtil工具类进行句柄操作
- 使用哈希函数HashHandleAndSlot进行键值计算
- 假设computeShaderMappings_和shaderMappings_是类的成员变量
