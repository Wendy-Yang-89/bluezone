# RenderNodeDefaultMaterialRenderSlotOit::CreateNewPso 函数分析

## 函数签名
```cpp
RenderNodeDefaultMaterialRenderSlotOit::PsoAndInfo RenderNodeDefaultMaterialRenderSlotOit::CreateNewPso(
    const ShaderStateData& ssd, const GraphicsState::InputAssembly& ia,
    const RenderDataDefaultMaterial::SubmeshMaterialFlags& submeshMatFlags, const RenderSubmeshFlags submeshFlags,
    const IRenderDataStoreDefaultLight::LightingFlags lightingFlags, const RenderCamera::ShaderFlags camShaderFlags)
```

## 功能概述
该函数用于创建新的管线状态对象（PSO），根据给定的着色器状态、输入装配状态、材质标志、子网格标志、光照标志和相机着色器标志，配置并返回相应的PSO句柄和相关配置信息。

## 输入参数
- `ssd`: 着色器状态数据，包含着色器和图形状态句柄
- `ia`: 图形状态的输入装配配置
- `submeshMatFlags`: 子网格材质标志
- `submeshFlags`: 子网格标志
- `lightingFlags`: 光照标志
- `camShaderFlags`: 相机着色器标志

## 返回值
- `PsoAndInfo`: 包含PSO句柄和是否需要自定义设置标志的结构体

## 详细逻辑流程

### 1. 获取着色器管理器
```cpp
const auto& shaderMgr = renderNodeContextMgr_->GetShaderManager();
```
- 从渲染节点上下文管理器获取着色器管理器引用
- 用于后续的着色器相关操作

### 2. 初始化句柄变量
```cpp
RenderHandle currShader;
RenderHandle currVid;
RenderHandle currState;
```
- `currShader`: 当前着色器句柄
- `currVid`: 当前顶点输入声明句柄
- `currState`: 当前图形状态句柄

### 3. 查找匹配的着色器
```cpp
if (RenderHandleUtil::GetHandleType(ssd.shader) == RenderHandleType::SHADER_STATE_OBJECT) {
    // we force the given shader if explicit shader render slot is not given
    if (!jsonInputs_.explicitShader) {
        currShader = ssd.shader;
    }
    const RenderHandle slotShader = shaderMgr.GetShaderHandle(ssd.shader, jsonInputs_.shaderRenderSlotId);
    if (RenderHandleUtil::IsValid(slotShader)) {
        currShader = slotShader; // override with render slot variant
    }
```

#### 逻辑分析：
1. **类型检查**: 验证着色器句柄类型是否为着色器状态对象
2. **显式着色器器检查**: 如果没有指定显式着色器渲染槽位，使用给定的着色器
3. **渲染槽位变体查找**: 
   - 调用 `shaderMgr.GetShaderHandle()` 查找匹配渲染槽位的着色器变体
   - 如果找到有效的槽位着色器，覆盖当前着色器器
4. **优先级**: 渲染槽位变体 > 原始着色器器

### 4. 获取图形状态（通过着色器）
```cpp
// if not explicit gfx state given, check if shader has graphics state for this slot
if (!RenderHandleUtil::IsValid(ssd.gfxState)) {
    const auto gfxStateHandle = shaderMgr.GetGraphicsStateHandleByShaderHandle(currShader);
    if (shaderMgr.GetRenderSlotId(gfxStateHandle) == jsonInputs_.stateRenderSlotId) {
        currState = gfxStateHandle;
    }
}
```

#### 逻辑分析：
1. **条件检查**: 仅当没有提供显式图形状态时执行
2. **通过着色器获取图形状态**: 调用 `GetGraphicsStateHandleByShaderHandle()`
3. **渲染槽位匹配**: 验证图形状态的渲染槽位ID是否匹配
4. **赋值**: 如果匹配，设置当前图形状态句柄

### 5. 获取顶点输入声明
```cpp
currVid = shaderMgr.GetVertexInputDeclarationHandleByShaderHandle(currShader);
```
- 通过着色器句柄获取对应的顶点输入声明句柄柄
- 用于后续的顶点数据布局配置

### 6. 处理显式图形状态
```cpp
if (RenderHandleUtil::GetHandleType(ssd.gfxState) == RenderHandleType::GRAPHICS_STATE) {
    const RenderHandle slotState = shaderMgr.GetGraphicsStateHandle(ssd.gfxState, jsonInputs_.stateRenderSlotId);
    if (RenderHandleUtil::IsValid(slotState)) {
        currState = slotState;
    }
}
```

#### 逻辑分析：
1. **类型检查**: 验证图形状态句柄类型
2. **渲染槽位查找**: 调用 `GetGraphicsStateHandle()` 查找匹配渲染槽位的图形状态
3. **覆盖**: 如果找到有效的槽位状态，覆盖当前图形状态
4. **优先级**: 槽位图形状态 > 着色器关联的图形状态

### 7. 获取管线布局并检查自定义设置
```cpp
bool needsCustomSet = false;
const PipelineLayout& pl = GetEvaluatedPipelineLayout(currShader, needsCustomSet);
```
- 获取评估后的管线布局
- `needsCustomSet` 标志指示是否需要自定义设置
- 管线布局定义了着色器的资源绑定布局

### 8. 回退到默认值
```cpp
currShader = RenderHandleUtil::IsValid(currShader) ? currShader : allShaderData_.defaultShaderHandle;
currVid = RenderHandleUtil::IsValid(currVid) ? currVid : allShaderData_.defaultVidHandle;
currState = RenderHandleUtil::IsValid(currState) ? currState : allShaderData_.defaultStateHandle;
```

#### 逻辑分析：
1. **着色器回退**: 如果当前着色器无效，使用默认着色器
2. **顶点输入声明回退**: 如果当前VID无效，使用默认VID
3. **图形状态回退**: 如果当前图形状态无效，使用默认图形状态
4. **容错机制**: 确保总是有有效的句柄用于PSO创建

### 9. 获取PSO管理器
```cpp
auto& psoMgr = renderNodeContextMgr_->GetPsoManager();
```
- 从渲染节点上下文管理器获取PSO管理器引用
- 用于创建和管理管线状态对象

### 10. 计算特殊渲染条件
```cpp
const bool inverseWinding =
    IsInverseWinding(submeshFlags, jsonInputs_.nodeFlags, currentScene_.camData.camera.flags);
const bool customIa = (ia.primitiveTopology != CORE_PRIMITIVE_TOPOLOGY_MAX_ENUM) || (ia.enablePrimitiveRestart);
```

#### 条件分析：
1. **inverseWinding**: 
   - 指示是否需要反转顶点绕序
   - 基于子网格标志、节点标志和相机标志计算
   - 用于处理背面剔除和双面渲染

2. **customIa**:
   - 指示是否需要自定义输入装配
   - 检查图元拓扑类型是否为非默认值
   - 检查是否启用图元重启

### 11. 获取顶点输入声明视图
```cpp
const VertexInputDeclarationView vid = shaderMgr.GetVertexInputDeclarationView(currVid);
```
- 获取顶点输入声明的视图
- 提供顶点数据的格式和布局信息

### 12. 创建PSO（条件分支）

#### 分支1: 需要自定义图形状态
```cpp
if (inverseWinding || customIa) {
    const GraphicsState state = GetNewGraphicsState(shaderMgr, currState, inverseWinding, customIa, ia);
    const auto spec = GetShaderSpecView(state, submeshMatFlags, submeshFlags, lightingFlags, camShaderFlags);
    psoHandle = psoMgr.GetGraphicsPsoHandle(currShader, state, pl, vid, spec, GetDynamicStates());
}
```

**逻辑**:
1. **创建新图形状态**: 调用 `GetNewGraphicsState()` 创建修改后的图形状态
   - 应用反转绕序（如果需要）
   - 应用自定义输入装配（如果需要）
2. **获取着色器规范视图**: 调用 `GetShaderSpecView()` 生成着色器特化常量
   - 基于图形状态、材质标志、子网格标志、光照标志和相机标志
3. **创建PSO**: 调用 `GetGraphicsPsoHandle()` 创建或获取图形PSO
   - 传入着色器、图形状态、管线布局、顶点输入声明、着色器规范和动态状态

#### 分支2: 使用默认图形状态
```cpp
else {
    // graphics state in default mode
    const GraphicsState& state = shaderMgr.GetGraphicsState(currState);
    const auto spec = GetShaderSpecView(state, submeshMatFlags, submeshFlags, lightingFlags, camShaderFlags);
    psoHandle = psoMgr.GetGraphicsPsoHandle(currShader, state, pl, vid, spec, GetDynamicStates());
}
```

**逻辑**:
1. **获取图形状态**: 直接从着色器管理器获取图形状态引用
2. **获取着色器规范视图**: 与分支1相同
3. **创建PSO**: 与分支1相同，但使用未修改的图形状态

### 13. 保存PSO数据
```cpp
allShaderData_.perShaderData.push_back(PerShaderData { currShader, psoHandle, currState, needsCustomSet });
allShaderData_.shaderIdToData[ssd.hash] = (uint32_t)allShaderData_.perShaderData.size() - 1;
```

#### 逻辑分析：
1. **添加到向量**: 将PSO数据添加到 `perShaderData` 向量
   - 包含：着色器句柄、PSO句柄、图形状态句柄、自定义设置标志
2. **建立映射**: 在 `shaderIdToData` 映射中记录哈希到索引的映射
   - 使用着色器状态数据的哈希作为键
   - 使用新添加元素的索引作为值
   - 用于快速查找已创建的PSO

### 14. 返回结果
```cpp
return { psoHandle, needsCustomSet };
```
- 返回包含PSO句柄和自定义设置标志的结构体

## 关键特性

### 1. 多级回退机制
- 着色器: 渲染槽位变体 → 原始着色器 → 默认着色器
- 顶点输入声明: 着色器关联 → 默认VID
- 图形状态: 槽位状态 → 着色器关联 → 默认状态

### 2. 渲染槽位支持
- 支持通过渲染槽位ID查找着色器变体
- 支持通过渲染槽位ID查找图形状态变体
- 允许同一着色器在不同渲染槽位有不同的配置

### 3. 动态图形状态修改
- 支持反转顶点绕序（用于双面渲染）
- 支持自定义输入装配（图元拓扑和图元重启）
- 在需要时创建修改后的图形状态

### 4. 着色器特化
- 通过 `GetShaderSpecView()` 生成着色器特化常量
- 基于多个标志组合：材质、子网格、光照、相机
- 允许编译时优化和条件编译

### 5. PSO缓存
- 使用 `GetGraphicsPsoHandle()` 而非直接创建
- PSO管理器负责缓存和重用
- 避免重复创建相同配置的PSO

### 6. 数据管理
- 自动保存创建的PSO数据
- 建立哈希到数据的快速查找映射
- 支持后续的PSO重用和查询

## 性能优化

### 1. 早期类型检查
- 在操作前验证句柄类型
- 避免无效操作

### 2. 条件分支优化
- 仅在需要时创建修改后的图形状态
- 默认情况下使用缓存的图形状态

### 3. PSO缓存
- 通过PSO管理器实现PSO缓存
- 减少昂贵的PSO创建操作

### 4. 快速查找
- 使用哈希映射存储PSO数据
- O(1)时间复杂度的查找

## 依赖关系

### 外部依赖
- `renderNodeContextMgr_`: 渲染节点上下文管理器
- `jsonInputs_`: JSON输入配置
- `allShaderData_`: 所有着色器数据容器
- `currentScene_`: 当前场景数据

### 关键函数调用
- `shaderMgr.GetShaderHandle()`: 查找着色器变体
- `shaderMgr.GetGraphicsStateHandleByShaderHandle()`: 通过着色器获取图形状态
- `shaderMgr.GetVertexInputDeclarationHandleByShaderHandle()`: 获取顶点输入声明
- `shaderMgr.GetGraphicsStateHandle()`: 查找图形状态变体
- `GetEvaluatedPipelineLayout()`: 获取管线布局
- `GetNewGraphicsState()`: 创建修改后的图形状态
- `GetShaderSpecSpecView()`: 生成着色器特化常量
- `psoMgr.GetGraphicsPsoHandle()`: 创建或获取PSO

## 使用场景

### 典型使用场景
1. **材质渲染**: 为不同材质创建对应的PSO
2. **着色器变体**: 处理同一着色器的不同配置变体
3. **特殊渲染**: 处理双面渲染、自定义拓扑等特殊情况
4. **光照渲染**: 根据光照配置创建优化的PSO
5. **相机效果**: 根据相机着色器标志创建特效PSO

### 渲染流程中的位置
- 在渲染节点处理过程中调用
- 当需要新的PSO配置时触发
- 作为PSO缓存机制的创建入口

## 注意事项

### 1. 句柄有效性
- 所有句柄在使用前都应验证有效性
- 提供默认值作为回退方案

### 2. 渲染槽位ID
- 着色器渲染槽位ID和图形状态渲染槽位ID可能不同
- 需要分别处理和匹配

### 3. 状态修改
- 图形状态的修改会创建新的状态对象
- 原始状态不会被修改

### 4. PSO唯一性
- PSO由多个参数组合唯一确定
- 任何参数变化都会导致不同的PSO

### 5. 内存管理
- PSO数据存储在类成员变量中
- 生命周期与渲染节点相关联

## 调试建议

### 关键检查点
1. 着色器句柄是否有效
2. 图形状态句柄是否有效
3. 顶点输入声明句柄是否有效
4. 渲染槽位ID是否正确
5. PSO是否成功创建

### 常见问题
1. **PSO创建失败**: 检查所有句柄的有效性和兼容性
2. **渲染结果不正确**: 检查图形状态配置和着色器特化常量
3. **性能问题**: 检查PSO缓存命中率和重复创建
4. **渲染槽位不匹配**: 验证渲染槽位ID的一致性
