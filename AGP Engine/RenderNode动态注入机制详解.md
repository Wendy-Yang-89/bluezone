# RenderNode动态注入机制详解

## 背景

LumeRender采用 **RenderNodeGraph（渲染节点图）** 架构组织渲染流程：

| 特性 | 说明 |
|------|------|
| **DAG结构** | 渲染节点按依赖关系组成有向无环图 |
| **声明式配置** | 通过JSON/RNG文件定义渲染流程 |
| **动态扩展** | 支持运行时注入新的渲染节点 |

传统渲染系统的问题：节点硬编码、依赖管理复杂、扩展困难。动态注入机制通过插件注册器自动发现节点，解决这些问题。

---

## 核心概念

### RenderNode

**RenderNode** 是渲染流程的基本执行单元，继承 `IRenderNode` 接口，实现具体渲染任务（材质渲染、阴影渲染、后处理等）。

### RenderNodeTypeInfo

**RenderNodeTypeInfo** 是RenderNode的元数据：

| 字段 | 类型 | 作用 |
|------|------|------|
| `uid` | Uid | 节点类型的唯一标识符 |
| `typeName` | string | 节点类型名称 |
| `afterNode` | Uid | 后置依赖：需要在此节点之后执行 |
| `beforeNode` | Uid | 前置依赖：需要在此节点之前执行 |

### RenderNodeDependency

**RenderNodeDependency** 定义节点的插入位置：

```cpp
struct RenderNodeDependency {
    string_view typeName;   // 依赖目标节点的类型名称
    Position position;      // 插入位置枚举

    enum class Position {
        BEFORE_FIRST,  // 目标节点的第一个实例之前
        BEFORE_LAST,   // 目标节点的最后一个实例之前
        AFTER_FIRST,   // 目标节点的第一个实例之后
        AFTER_LAST     // 目标节点的最后一个实例之后
    };
};
```

---

## InjectRenderNodes 流程

```
InjectRenderNodes 执行流程:

┌────────────────────────────────────────────────────┐
│ 输入: RenderNodeGraphDesc + RenderNodeGraphManager │
└────────────────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ Step 1: 获取所有RenderNode类型信息                         │
├───────────────────────────────────────────────────────────┤
│ GetPluginRegister().GetTypeInfos(RenderNodeTypeInfo::UID) │
│   └─► 返回: 所有已注册的RenderNode类型                      │
└───────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 2: 筛选有依赖关系的节点                       │
├──────────────────────────────────────────────────┤
│ GetRenderNodesWithDependencies()                 │
│   └─► 筛选条件: afterNode或beforeNode不为空       │
│   └─► 返回: 需处理依赖的节点列表                   │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 3: 遍历依赖节点                              │
├──────────────────────────────────────────────────┤
│ for each depending:                              │
│   └─ 检查节点是否已存在 → 已存在则跳过              │
│   └─ 解析 afterNode → 创建 AFTER_LAST 依赖        │
│   └─ 解析 beforeNode → 创建 BEFORE_LAST 依赖      │
│   └─ 创建 RenderNodeDesc + JSON配置               │
│   └─ 注册到 manager.AddRenderNodeInsertion()      │
│   └─ 应用插入 manager.PatchRenderNodeGraph()      │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Step 4: 清理临时请求                              │
├──────────────────────────────────────────────────┤
│ for each request:                                │
│   └─ manager.RemoveRenderNodeInsertion(request)  │
└──────────────────────────────────────────────────┘
```

---

## 依赖处理详解

### afterNode 与 beforeNode 的区别

| 依赖类型 | 含义 | Position选择 |
|----------|------|-------------|
| `afterNode` | 在目标节点之后执行 | `AFTER_LAST` |
| `beforeNode` | 在目标节点之前执行 | `BEFORE_LAST` |

### 为什么统一使用 AFTER_LAST / BEFORE_LAST？

当目标节点有多个实例时，不同Position产生不同效果：

| Position | 插入位置 | 示例结果 |
|----------|----------|---------|
| `BEFORE_FIRST` | 第一个实例之前 | `[C] → [A1] → [A2] → [A3]` |
| `BEFORE_LAST` | 最后一个实例之前 | `[A1] → [A2] → [C] → [A3]` |
| `AFTER_FIRST` | 第一个实例之后 | `[A1] → [C] → [A2] → [A3]` |
| `AFTER_LAST` | 最后一个实例之后 | `[A1] → [A2] → [A3] → [C]` |

**选择 AFTER_LAST / BEFORE_LAST 的原因**：

1. **语义一致性**：确保依赖节点紧挨目标节点的边界实例，避免插入到过前或过后的位置。

2. **数据依赖保证**：典型场景：
   ```
   原始顺序：
   [MaterialNode (Shadow)] → [MaterialNode (Opaque)] → [MaterialNode (Translucent)]
   
   CustomNode 设置 beforeNode = MaterialNode：
   - BEFORE_FIRST: 在Shadow之前执行，数据未准备好
   - BEFORE_LAST: 在Translucent之前执行，数据完整
   ```

3. **对应关系**：
   - `afterNode` + `AFTER_LAST`：目标节点全部完成后执行
   - `beforeNode` + `BEFORE_LAST`：目标节点开始前执行，但不过早

---

## 代码实现要点

### GetRenderNodesWithDependencies 函数

**位置**: `render_util.cpp:162-176`

```cpp
vector<const RenderNodeTypeInfo*> GetRenderNodesWithDependencies()
{
    vector<const RenderNodeTypeInfo*> result;
    auto typeInfos = GetPluginRegister().GetTypeInfos(RenderNodeTypeInfo::UID);
    for (auto* info : typeInfos) {
        if (info && (info->typeUid == RenderNodeTypeInfo::UID)) {
            auto* renderNodeTypeInfo = static_cast<const RenderNodeTypeInfo*>(info);
            // 筛选条件：有前置或后置依赖
            if ((renderNodeTypeInfo->afterNode != Uid{}) || 
                (renderNodeTypeInfo->beforeNode != Uid{})) {
                result.push_back(renderNodeTypeInfo);
            }
        }
    }
    return result;
}
```

### 依赖解析核心逻辑

```cpp
// 解析后置依赖
if (depending->afterNode != Uid{}) {
    auto info = std::find_if(renderNodeTypeInfos.begin(), renderNodeTypeInfos.end(),
        [uid = depending->afterNode](auto* info) { return info->uid == uid; });
    if (info != renderNodeTypeInfos.end()) {
        dependencies.push_back({ (*info)->typeName, Position::AFTER_LAST });
    }
}

// 解析前置依赖
if (depending->beforeNode != Uid{}) {
    auto info = std::find_if(renderNodeTypeInfos.begin(), renderNodeTypeInfos.end(),
        [uid = depending->beforeNode](auto* info) { return info->uid == uid; });
    if (info != renderNodeTypeInfos.end()) {
        dependencies.push_back({ (*info)->typeName, Position::BEFORE_LAST });
    }
}
```

---

## 使用示例

### 添加自定义后处理节点

```cpp
// 定义类型信息
RenderNodeTypeInfo customNodeInfo = {
    .uid = Uid{ 0x12345678, 0x9ABCDEF0 },
    .typeName = "CustomPostProcessNode",
    .afterNode = Uid{ 0x00000001, 0x00000002 },  // MaterialNode的UID
    .beforeNode = Uid{}  // 无前置依赖
};
```

**处理过程**：
1. `GetRenderNodesWithDependencies()` 返回此节点
2. 检查节点不在当前图中
3. 查找 `afterNode` UID 对应的类型
4. 创建 `AFTER_LAST` 依赖
5. 生成节点名称：`CORE3D_RN_SCENE_CustomPostProcessNode`
6. 创建JSON配置并注入

### 同时声明前后依赖

```cpp
RenderNodeTypeInfo nodeInfo = {
    .afterNode = Uid{ ... },   // 节点A之后
    .beforeNode = Uid{ ... }   // 节点B之前
};
```

结果：节点插入在 A 之后、B 之前的区间内。

---

## 性能与调试

### 时间复杂度

| 操作 | 复杂度 |
|------|--------|
| GetRenderNodesWithDependencies | O(n) |
| 检查节点是否存在 | O(m) |
| 查找依赖节点 | O(n) |
| **总体** | O(k × (m + n)) |

n: 总节点类型数，m: 当前图节点数，k: 依赖节点数

### 开发调试

```cpp
#if (CORE3D_DEV_ENABLED == 1)
    PLUGIN_LOG_I("Injecting RenderNodeWeatherSimulation node");
#endif
```

### 验证要点

1. 依赖节点 UID 是否正确注册
2. 节点是否插入到预期位置
3. 重复注入是否被正确过滤
4. 多依赖节点的相对顺序

---

## 源码位置

**InjectRenderNodes**: `src/util/render_util.cpp:197-244`

**GetRenderNodesWithDependencies**: `src/util/render_util.cpp:162-176`