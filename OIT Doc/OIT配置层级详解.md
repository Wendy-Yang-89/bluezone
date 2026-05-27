# OIT配置层级详解

## 1. 问题背景

OIT（Order Independent Transparency）需要两类配置：

1. **启用开关**：是否使用 OIT 渲染透明物体
2. **算法类型**：PPLL / WBOIT / AT

这两个配置放在哪里最合适？需要从**配置粒度**、**语义一致性**、**实现复杂度**等角度分析。

OIT 的核心特点：
- 改变整个透明物体的渲染管线，需要专用的 Render Node Graph
- 不是后处理技术，在渲染过程中实现
- PPLL/AT 需要额外 GPU 资源（链表缓冲区），WBOIT 只需额外的 MRT target
- 与 MSAA、Deferred 管线存在互斥约束

---

## 2. 候选配置位置

### 2.1 CameraComponent（相机级）

**现有枚举结构：**

```cpp
// api/3d/ecs/components/camera_component.h:63-104
enum PipelineFlagBits : uint32_t {
    CLEAR_DEPTH_BIT = (1 << 0),
    CLEAR_COLOR_BIT = (1 << 1),
    MSAA_BIT = (1 << 2),
    ALLOW_COLOR_PRE_PASS_BIT = (1 << 3),
    FORCE_COLOR_PRE_PASS_BIT = (1 << 4),
    HISTORY_BIT = (1 << 5),
    JITTER_BIT = (1 << 6),
    VELOCITY_OUTPUT_BIT = (1 << 7),
    DEPTH_OUTPUT_BIT = (1 << 8),
    MULTI_VIEW_ONLY_BIT = (1 << 9),
    DISALLOW_REFLECTION_BIT = (1 << 11),
    CUBEMAP_BIT = (1 << 12),
    OIT_BIT = (1 << 13),  // 当前引擎实现：已存在
};
```

**优缺点：**

| 维度 | 分析 |
|------|------|
| ✅ 粒度灵活 | 不同相机可独立启用/禁用 OIT |
| ✅ 现有模式 | MSAA_BIT 等渲染标志位已在此，OIT_BIT 风格一致 |
| ✅ 多相机支持 | 主相机用 OIT、截图相机不用，各自控制 |
| ❌ 语义偏差 | OIT 影响整个场景的透明渲染，不是相机的固有属性（如 FOV） |
| ❌ 多相机冗余 | 所有相机都需要 OIT 时，每台相机需重复设置 |
| ❌ 管理分散 | 启用开关和算法类型分属不同组件，需要两步配置 |

**当前引擎实现：** `OIT_BIT = (1 << 13)` 已存在，是引擎中 OIT 的唯一启用开关。

**使用示例：**

```cpp
auto cameraMgr = GetManager<ICameraComponentManager>(*ecs_);
if (auto h = cameraMgr->Write(cameraEntity); h) {
    h->pipelineFlags |= CameraComponent::PipelineFlagBits::OIT_BIT;
}
```

### 2.2 RenderConfigurationComponent（场景级）

**现有枚举结构：**

```cpp
// api/3d/ecs/components/render_configuration_component.h
enum class SceneOitType : uint8_t {
    PPLL = 0,   // Per-Pixel Linked List
    WBOIT = 1,  // Weighted Blended OIT
    AT = 2,     // Adaptive Transparency
};

enum SceneRenderingFlagBits : uint8_t {
    CREATE_RNGS_BIT = (1 << 0),
    // 注意：当前无 ENABLE_OIT_BIT
};
```

**优缺点：**

| 维度 | 分析 |
|------|------|
| ✅ 语义一致 | 与 SceneShadowType / SceneShadowQuality 同级，OIT 是场景级渲染技术 |
| ✅ 统一管理 | 启用开关 + 算法类型在同一组件，一步配置 |
| ✅ 自动生效 | 所有相机自动继承，无需逐相机设置 |
| ❌ 粒度粗糙 | 无法对单台相机独立控制 OIT 开关 |
| ❌ 需新增字段 | 需在 SceneRenderingFlagBits 添加 ENABLE_OIT_BIT |
| ❌ 灵活性不足 | 混合渲染场景中，部分相机可能不需要 OIT |

**当前引擎实现：** `SceneOitType` 已存在用于配置算法类型，但**无** `ENABLE_OIT_BIT`——启用开关由 `CameraComponent::OIT_BIT` 承担。

**使用示例（替代方案——需新增 ENABLE_OIT_BIT）：**

```cpp
auto configMgr = GetManager<IRenderConfigurationComponentManager>(*ecs_);
if (auto h = configMgr->Write(sceneEntity); h) {
    h->renderingFlags |= RenderConfigurationComponent::SceneRenderingFlagBits::ENABLE_OIT_BIT;
    h->oitType = RenderConfigurationComponent::SceneOitType::WBOIT;
}
```

### 2.3 MaterialComponent（材质级）

不推荐。OIT 是渲染管线级技术，影响场景中**所有**透明物体的渲染方式，而非单个材质的表面属性。MaterialComponent 描述的是材质光学特征（颜色、粗糙度、金属度），将管线技术放在这里违反组件职责划分。且 OIT 启用后需要切换 Render Node Graph 和 GPU 资源分配，这不是材质级别能承担的。

### 2.4 PostProcessConfiguration（后处理级）

不推荐。OIT 在渲染过程中实现（透明物体绘制阶段），不是渲染完成后的后处理。将其放在 PostProcessEnableFlagBits（tonemap、bloom、TAA 等真正的后处理）中会误导 OIT 的技术性质，且后处理节点无法控制前置渲染管线的 Render Slot 和 RNG 选择。

---

## 3. 引擎当前实现

引擎采用**混合方案**：`CameraComponent::OIT_BIT`（启用开关）+ `RenderConfigurationComponent::SceneOitType`（算法类型）。

```
CameraComponent::OIT_BIT
    → RenderCamera::CAMERA_FLAG_OIT_BIT (render_system.cpp:321)
    → hasActiveOitCameras 检测 (render_system.cpp:1884)
    → ProcessOit(): shaderFlags |= OIT_PPLL/WBOIT/AT_BIT (render_system.cpp:2072)

RenderConfigurationComponent::SceneOitType
    → RenderDataStoreDefaultCamera::SetOitType() (render_system.cpp:1902)
    → Render Slot 选择: LLOIT / WBOIT (render_system.cpp:3246)
    → 自动创建对应 RNG (lloit/wboit) (render_system.cpp:2970)

验证: OIT 不兼容 Deferred → 自动禁用; PPLL/AT 不兼容 MSAA → 自动禁用 MSAA
```

两个配置分属不同组件，通过 `RenderSystem` 汇合后共同决定最终的 OIT 行为。

---

## 4. 方案对比与替代方案

### 4.1 当前方案（混合方案）评价

**架构：** 启用开关在相机级，算法类型在场景级。

优势：
- 灵活性高：不同相机可独立开关 OIT（主相机开启，辅助相机关闭）
- 复用现有结构：`OIT_BIT` 嵌入 `PipelineFlagBits`，与 `MSAA_BIT` 风格一致

问题：
- 语义分裂：OIT 的完整配置（开关+算法）跨越两个组件，使用者需要理解两者关系
- 多相机场景需重复设置：每台需要 OIT 的相机都要手动添加 `OIT_BIT`
- 场景级语义被削弱：OIT 本质是场景级渲染特性，启用开关却不在场景配置中

### 4.2 替代方案A：纯场景级

在 `SceneRenderingFlagBits` 添加 `ENABLE_OIT_BIT`，所有相机统一启用/禁用。

```cpp
enum SceneRenderingFlagBits : uint8_t {
    CREATE_RNGS_BIT = (1 << 0),
    ENABLE_OIT_BIT = (1 << 1),  // 新增
};
```

```cpp
auto configMgr = GetManager<IRenderConfigurationComponentManager>(*ecs_);
if (auto h = configMgr->Write(sceneEntity); h) {
    h->renderingFlags |= RenderConfigurationComponent::SceneRenderingFlagBits::ENABLE_OIT_BIT;
    h->oitType = RenderConfigurationComponent::SceneOitType::WBOIT;
}
```

**适用场景：** 所有相机都使用 OIT 的简单应用，一步配置完成。

**局限：** 无法实现"主相机开启 OIT、反射相机关闭 OIT"的精细控制。

### 4.3 替代方案B：纯相机级

在 `CameraComponent` 同时放置启用开关和算法类型。

```cpp
// 在 CameraComponent 中新增 OIT 算法枚举
enum class CameraOitType : uint8_t {
    DISABLED = 0,  // 关闭 OIT
    PPLL = 1,
    WBOIT = 2,
    AT = 3,
};
```

```cpp
auto cameraMgr = GetManager<ICameraComponentManager>(*ecs_);
if (auto h = cameraMgr->Write(mainCamera); h) {
    h->pipelineFlags |= CameraComponent::PipelineFlagBits::OIT_BIT;
    h->oitType = CameraComponent::CameraOitType::WBOIT;  // 性能优先
}
if (auto h = cameraMgr->Write(screenshotCamera); h) {
    h->pipelineFlags |= CameraComponent::PipelineFlagBits::OIT_BIT;
    h->oitType = CameraComponent::CameraOitType::PPLL;   // 精确优先
}
```

**适用场景：** 不同相机需要不同 OIT 算法——主相机用 WBOIT（性能优先），截图/离线渲染相机用 PPLL（精确优先）。

**局限：** `CameraComponent` 职责膨胀，每台相机需独立配置，场景级一致性无保证。

### 4.4 对比总结

| 维度 | 混合方案（当前） | 纯场景级 | 纯相机级 |
|------|-----------------|---------|---------|
| 配置灵活性 | 中 | 低 | 高 |
| 语义一致性 | 低（分裂在两个组件） | 高（集中在一处） | 中（OIT 非相机固有属性） |
| 多相机开关 | 独立控制 | 自动统一 | 独立控制 |
| 多相机算法 | 统一（场景级） | 统一（场景级） | 独立控制 |
| 配置步骤 | 两步（开关+算法） | 一步 | 一步（但每台相机） |
| 实现复杂度 | 中（需跨组件协调） | 低 | 高（每相机独立 RNG/资源） |
| 与引擎现状的兼容性 | ✅ 完全兼容 | 需改造启用路径 | 需改造算法路径 |

**选择建议：**
- 简单应用 → 纯场景级，配置直觉、不易出错
- 需要多相机差异化 → 混合方案或纯相机级
- 当前引擎维持混合方案是合理的工程折中，但应注意其语义分裂的代价

---

## 5. 参考

| 文件 | 关键内容 |
|------|---------|
| `api/3d/ecs/components/camera_component.h` | `PipelineFlagBits::OIT_BIT` 定义 |
| `api/3d/ecs/components/render_configuration_component.h` | `SceneOitType`、`SceneRenderingFlagBits` 定义 |
| `api/3d/render/intf_render_data_store_default_camera.h` | `OitType`、`SetOitType`、`SetHasActiveOitCameras` |
| `api/3d/render/render_data_defines_3d.h` | `RenderCamera::CAMERA_FLAG_OIT_BIT`、`ShaderFlagBits` |
| `src/ecs/systems/render_system.cpp` | OIT 启用路径、ProcessOit()、render slot 选择、RNG 自动创建 |
| `assets/3d/rendernodegraphs/core3d_rng_cam_scene_lwrp_lloit.rng` | Light-forward + PPLL/AT RNG |
| `assets/3d/rendernodegraphs/core3d_rng_cam_scene_lwrp_wboit.rng` | Light-forward + WBOIT RNG |
