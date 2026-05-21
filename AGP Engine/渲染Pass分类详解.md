# 渲染Pass分类详解

## 背景与问题引入

### 渲染Pass概念

**渲染Pass（Render Pass）** 是GPU渲染的独立执行阶段：

- 拥有独立的渲染目标和状态配置
- 执行特定的渲染任务（如阴影、深度、颜色）
- 按顺序执行，形成完整渲染流程

现代渲染引擎将渲染分解为多个Pass，实现功能分离和性能优化。

### 多Pass渲染架构

Lume3D采用多Pass渲染架构组织渲染流程：

```
渲染流程：
  Shadow Pass → Depth Pre-Pass → Main Pass → Post Process
      ↓              ↓              ↓              ↓
   阴影贴图       深度缓冲        颜色输出       后处理效果
```

每个Pass承担不同职责，协同完成最终画面渲染。

### 三种核心Pass

Lume3D渲染系统包含三种核心渲染Pass：

| Pass类型 | 目的 | 执行时机 |
|---------|------|---------|
| **Shadow Pass** | 生成阴影贴图 | 场景级，最早执行 |
| **Depth Pre-Pass** | 预填充深度缓冲 | 相机级，Main Pass前 |
| **Main Pass** | 完整几何渲染 | 相机级，主渲染 |

理解各Pass的作用和关系，是配置渲染流程的基础。

### 本文档解决的问题

本文档详细对比三种Pass的定义、配置和执行机制：

- 各Pass的目的和技术细节
- RenderSlot和RenderNode的对应关系
- 触发条件和性能优化策略

---

## 核心概念

### Shadow Pass

**Shadow Pass（阴影Pass）** 从光源视角渲染场景：

- 生成Shadow Map（阴影深度贴图）
- 为阴影接收者提供遮挡信息
- 执行于场景级RenderNodeGraph

技术要点：
- 仅渲染深度，不输出颜色
- 使用光源Camera的视角和投影
- 支持PCF、VSM等阴影过滤技术

### Depth Pre-Pass

**Depth Pre-Pass（深度预渲染）** 在主渲染前填充深度：

- 仅渲染几何的深度信息
- 减少主Pass的overdraw（重复渲染）
- 为透明材质提供正确的深度基准

触发条件：
- 场景存在Transmission材质
- Camera启用 `ALLOW_COLOR_PRE_PASS_BIT`
- 强制启用 `FORCE_COLOR_PRE_PASS_BIT`

### Main Pass

**Main Pass（主渲染Pass）** 执行完整的几何渲染：

- 渲染不透明物体（Opaque）
- 渲染半透明物体（Translucent）
- 输出最终颜色到屏幕或离屏目标

Main Pass是渲染流程的核心，输出可见画面。

### RenderNodeGraph层级

RenderNodeGraph分为两个层级：

| 层级 | 配置文件 | 包含内容 |
|------|---------|---------|
| **场景级** | `core3d_rng_scene.rng` | Shadow Pass |
| **相机级** | `core3d_rng_cam_scene.rng` | Depth Pre-Pass + Main Pass |

场景级Pass与相机无关，相机级Pass依赖Camera配置。

### 三种Pass执行顺序

```
完整渲染流程执行顺序:

┌────────────────────────────────────────────────────┐
│ 场景级 RenderNodeGraph (core3d_rng_scene.rng)       │
├────────────────────────────────────────────────────┤
│                                                    │
│ Shadow Pass                                        │
│   └─ 从光源视角渲染场景深度                          │
│   └─ 生成Shadow Map                                │   
│   └─ RenderNode: RenderNodeDefaultShadowRenderSlot │
│   └─ RenderSlot: CORE3D_RS_DM_DEPTH / VSM          │
│                                                    │
└────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────┐
│ 相机级 RenderNodeGraph (core3d_rng_cam_scene.rng)     │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Depth Pre-Pass (条件触发)                             │
│   └─ 触发条件: Transmission材质 / 强制Pre-Pass         │
│   └─ 仅渲染深度信息                                   │
│   └─ RenderNode: RenderNodeDefaultMaterialRenderSlot │
│   └─ RenderSlot: CORE3D_RS_DM_DEPTH_PRE_PASS         │
│                                                      │
└──────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ Main Pass                                        │
├──────────────────────────────────────────────────┤
│                                                  │
│ Opaque渲染 (不透明物体)                           │
│   └─ RenderSlot: CORE3D_RS_DM_OPAQUE             │
│                                                  │
│ Translucent渲染 (半透明物体)                      │
│   └─ RenderSlot: CORE3D_RS_DM_TRANSLUCENT        │
│                                                  │
│ 输出最终颜色                                      │
│                                                  │
└──────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────┐
│ 最终画面                                          │
└──────────────────────────────────────────────────┘
```

---

## 一、概述

在 Lume3D 渲染系统中，存在三种主要的渲染 Pass：

1. **阴影 Pass (Shadow Pass)** - 生成阴影贴图
2. **Depth Pre-Pass (深度预渲染)** - 提前填充深度缓冲
3. **正常 Mesh 渲染 Pass** - 完整的几何体渲染（Opaque/Translucent）

这三种 Pass 在渲染流程中扮演不同角色，有着不同的执行顺序、目的和技术细节。

---

## 二、三种 Pass 的定义与目的

### 2.1 阴影 Pass (Shadow Pass)

**定义：** 从光源视角渲染场景深度，生成阴影贴图（Shadow Map）。

**目的：**
- 为阴影接收者提供阴影信息
- 记录从光源视角可见的几何体深度
- 在后续渲染中用于阴影判定

**执行位置：** 场景级 Render Node Graph (`core3d_rng_scene.rng`)

**Render Node 类型：** `RenderNodeDefaultShadowRenderSlot`

**Render Slot：**
- `CORE3D_RS_DM_DEPTH` - PCF 阴影
- `CORE3D_RS_DM_DEPTH_VSM` - VSM 阴影

### 2.2 Depth Pre-Pass (深度预渲染)

**定义：** 在正常渲染前单独渲染几何体的深度信息。

**目的：**
- 提前填充深度缓冲，减少后续渲染的 overdraw
- 为透明材质（如 Transmission）提供正确的深度信息
- 优化复杂场景的性能

**执行位置：** Camera 级 Render Node Graph (`core3d_rng_cam_scene_pre_pass.rng`)

**Render Node 类型：** `RenderNodeDefaultMaterialRenderSlot`（使用 Opaque Render Slot）

**典型触发条件：**
- Camera 启用 `PipelineFlagBits::ALLOW_COLOR_PRE_PASS_BIT`
- Camera 启用 `PipelineFlagBits::FORCE_COLOR_PRE_PASS_BIT`
- 场景存在 Transmission 材质（自动触发）

### 2.3 正常 Mesh 渲染 Pass

**定义：** 完整渲染几何体的颜色、深度等信息。

**目的：**
- 生成最终可见的图像
- 执行完整的材质着色计算
- 应用光照、阴影、环境光等

**执行位置：** Camera 级 Render Node Graph

**Render Node 类型：** `RenderNodeDefaultMaterialRenderSlot`

**Render Slot：**
- `CORE3D_RS_DM_FW_OPAQUE` - 不透明几何体
- `CORE3D_RS_DM_FW_TRANSLUCENT` - 透明几何体
- `CORE3D_RS_DM_ENV` - 环境渲染（天空盒等）

---

## 三、执行顺序对比

### 3.1 完整渲染流程顺序

```
场景级 Render Node Graph (core3d_rng_scene.rng)
├── 1. RenderNodeDefaultLights        ← 处理光源数据
├── 2. RenderNodeDefaultCameras       ← 处理相机数据
├── 3. RenderNodeDefaultMaterialObjects ← 处理材质数据
├── 4. RenderNodeMorph                ← 处理 Morph Target
├── 5. RenderNodeDefaultShadowRenderSlot ← 【阴影 Pass】
├── 6. RenderNodeDefaultShadowsBlur   ← 阴影模糊（VSM/PCF）
└── 7. RenderNodeDefaultEnvironmentBlender ← 环境混合

Camera 级 Render Node Graph (每个 Camera)
├── 1. RenderNodeDefaultCameraController ← 创建渲染资源
├── 2. [Depth Pre-Pass] (可选)         ← 【Depth Pre-Pass】
│   ├── RenderNodeDefaultMaterialRenderSlot (Opaque)
│   └── RenderNodeDefaultEnv
│   └── PostProcess (降采样)
├── 3. RenderNodeDefaultMaterialRenderSlot ← 【Opaque Pass】
├── 4. RenderNodeDefaultEnv            ← 环境渲染
├── 5. RenderNodeDefaultMaterialRenderSlot ← 【Translucent Pass】
└── 6. PostProcess Nodes               ← 后处理
```

### 3.2 阴影 Pass 的特殊性

**阴影 Pass 在所有 Camera 渲染之前执行！**

```
Time Line:
    ├── Scene Processing
    ├── Shadow Pass (对所有光源)
    ├── Camera 1 Pre-Pass (可选)
    ├── Camera 1 Main Pass
    ├── Camera 2 Pre-Pass (可选)
    ├── Camera 2 Main Pass
    └── ...
```

**原因：** 阴影贴图是全局资源，所有 Camera 都需要使用同一份阴影数据。

---

## 四、技术细节对比

### 4.1 渲染输出对比

| 特性 | 阴影 Pass | Depth Pre-Pass | 正常 Mesh Pass |
|------|----------|----------------|-----------------|
| **输出内容** | 仅深度 | 仅深度（+可选 velocity） | 颜色 + 深度 + velocity + normal |
| **Color Attachment** | 不需要（PCF）/ 需要（VSM） | 可选 | 必须 |
| **Depth Attachment** | 必须（Shadow Map） | 必须 | 必须 |
| **着色计算** | 最简化（仅深度） | 最简化 | 完整（光照、材质等） |

### 4.2 Shader 对比

| 特性 | 阴影 Pass | Depth Pre-Pass | 正常 Mesh Pass |
|------|----------|----------------|-----------------|
| **Shader 类型** | Depth Shader | Depth Shader | Material Shader |
| **Fragment Shader** | 简化版（仅输出深度） | 简化版 | 完整版（PBR、光照等） |
| **材质绑定** | `depthShader` | `depthShader` | `materialShader` |
| **纹理采样** | 极少（可选 alpha mask） | 极少 | 全部材质纹理 |

### 4.3 Render Pass 配置对比

#### 阴影 Pass Render Pass

```json
// PCF 阴影
{
    "attachments": [
        {
            "format": "d16_unorm",
            "loadOp": "clear",
            "clearDepth": [1.0, 0],
            "storeOp": "store"  // 需要保存为阴影贴图
        }
    ]
}

// VSM 阴影
{
    "attachments": [
        {
            "format": "d16_unorm",
            "loadOp": "clear",
            "clearDepth": [1.0, 0],
            "storeOp": "store"
        },
        {
            "format": "r16g16_unorm",
            "loadOp": "clear",
            "clearColor": [1.0, 1.0, 0.0, 0.0],
            "storeOp": "store"  // VSM 需要颜色输出
        }
    ]
}
```

#### Depth Pre-Pass Render Pass

```json
{
    "attachments": [
        {
            "format": "d16_unorm",
            "loadOp": "clear",
            "clearDepth": [1.0, 0],
            "storeOp": "dont_care"  // 后续主 Pass 会重新使用
        },
        {
            "format": "b10g11r11_ufloat_pack32",
            "loadOp": "dont_care",  // 可能用于降采样输出
            "storeOp": "store"
        }
    ]
}
```

#### 正常 Mesh Pass Render Pass

```json
{
    "attachments": [
        {
            "format": "d32_sfloat",
            "loadOp": "clear",
            "clearDepth": [1.0, 0],
            "storeOp": "store"
        },
        {
            "format": "b10g11r11_ufloat_pack32",
            "loadOp": "dont_care",  // 可能继承 Pre-Pass 结果
            "storeOp": "store"
        },
        {
            "format": "r16g16_sfloat",  // velocity_normal
            "loadOp": "clear",
            "storeOp": "store"
        }
    ],
    "subpassCount": 3,  // 多子渲染 Pass
    "subpass": {
        "subpassFlags": "merge_bit"
    }
}
```

---

## 五、阴影 Pass 详细分析

### 5.1 Shadow Pass 的核心逻辑

阴影 Pass 从光源视角渲染场景，生成阴影贴图：

```cpp
// render_node_default_shadow_render_slot.cpp

void RenderNodeDefaultShadowRenderSlot::ExecuteFrame(IRenderCommandList& cmdList) {
    // 1. 获取光源列表
    const auto lights = storeLight->GetLights();

    // 2. 创建 Render Pass
    renderPass_ = CreateRenderPass(shadowBuffers_);
    cmdList.BeginRenderPass(renderPass_.renderPassDesc, ...);

    // 3. 遍历每个阴影光源
    for (const auto& light : lights) {
        if ((light.lightUsageFlags & RenderLight::LIGHT_USAGE_SHADOW_LIGHT_BIT) == 0) {
            continue;  // 非阴影光源跳过
        }

        // 4. 获取阴影相机
        const auto& camera = cameras[light.shadowCameraIndex];

        // 5. 处理可见的 Submesh
        ProcessSlotSubmeshes(*storeCamera, *storeMaterial, light.shadowCameraIndex);

        // 6. 渲染 Submesh
        RenderSubmeshes(cmdList, *storeMaterial, shadowType, camera, light, shadowPassIdx);

        shadowPassIdx++;
    }

    cmdList.EndRenderPass();
}
```

### 5.2 Shadow Atlas（阴影贴图集）

多个阴影光源的渲染结果存储在一个 Shadow Atlas 中：

```
Shadow Atlas Layout:
┌────────────────────────────────────────┐
│ Light 0 │ Light 1 │ Light 2 │ Light 3 │  ← Directional Lights
├────────────────────────────────────────┤
│ Light 4 │ Light 5 │ ...                │  ← Spot Lights
└────────────────────────────────────────┘

每个光源占用一个固定宽度的区域
动态 Viewport/Scissor 控制渲染区域
```

```cpp
// 动态 Viewport 设置
const int32_t xOffset = static_cast<int32_t>(light.shadowIndex * currentScene_.res.x);
ViewportDesc vd = currentScene_.viewportDesc;
vd.x = static_cast<float>(xOffset);
cmdList.SetDynamicStateViewport(vd);
cmdList.SetDynamicStateScissor(sd);
```

### 5.3 阴影类型对比

| 阴影类型 | 输出 | 特点 | Render Slot |
|---------|------|------|-------------|
| **PCF** | 仅深度 | 传统阴影，硬边缘 | `CORE3D_RS_DM_DEPTH` |
| **VSM** | 深度 + 深度矩 | 软阴影，可过滤 | `CORE3D_RS_DM_DEPTH_VSM` |
| **VARIABLE_PCF** | 深度 + 额外信息 | 可变 PCF 核大小 | `CORE3D_RS_DM_DEPTH_VSM` |

### 5.4 阴影 Pass 的 Shader 选择

```cpp
// render_node_default_shadow_render_slot.cpp:373-376
const auto& selectableShaders =
    (shadowType == IRenderDataStoreDefaultLight::ShadowType::VSM ||
     shadowType == IRenderDataStoreDefaultLight::ShadowType::VARIABLE_PCF)
        ? vsmShaders_   // VSM 需要颜色输出
        : pcfShaders_;  // PCF 仅深度输出
```

---

## 六、Depth Pre-Pass 详细分析

### 6.1 Depth Pre-Pass 的触发条件

Depth Pre-Pass 在以下情况下触发：

1. **Camera 配置强制触发：**
   ```cpp
   // Camera Pipeline Flags
   PipelineFlagBits::FORCE_COLOR_PRE_PASS_BIT  // 强制每帧执行
   PipelineFlagBits::ALLOW_COLOR_PRE_PASS_BIT  // 自动触发（有 Transmission 材质时）
   ```

2. **Transmission 材质存在：**
   - Transmission 材质需要背景深度信息
   - 自动检测并触发 Pre-Pass

### 6.2 Depth Pre-Pass 的执行流程

```
Depth Pre-Pass (独立 Camera 渲染流程):
├── 1. Camera Controller (降采样配置)
├── 2. Opaque Render Slot (仅深度着色)
├── 3. Environment Render
├── 4. Post Process (降采样)
└── 输出: 低分辨率深度 + 颜色
```

**特点：**
- 使用较低分辨率（通常为主渲染的 1/2 或 1/4）
- 渲染到独立的 Render Target
- 后处理降采样输出

### 6.3 Depth Pre-Pass 的配置示例

```json
// core3d_rng_cam_scene_pre_pass.rng
{
    "nodeName": "CORE3D_RN_CAM_CTRL_CAMPP",
    "gpuImageDescs": [
        {
            "name": "depth",
            "format": "d16_unorm",  // 较低精度深度
            "usageFlags": "depth_stencil_attachment | transient_attachment",
            "memoryPropertyFlags": "device_local | lazily_allocated"
        },
        {
            "name": "color",
            "format": "b10g11r11_ufloat_pack32",
            "mipCount": 6  // 多级降采样
        }
    ]
}
```

### 6.4 Depth Pre-Pass 与主 Pass 的关系

```
主 Pass 继承 Pre-Pass 结果:
┌─────────────────────────────────────────────┐
│ Pre-Pass                                    │
│ ├── 低分辨率深度                            │
│ ├── 低分辨率颜色                            │
│ └── 后处理降采样                            │
└─────────────────────────────────────────────┘
           ↓ (作为 Input Attachment)
┌─────────────────────────────────────────────┐
│ 主 Pass                                     │
│ ├── loadOp: load (继承深度)                 │
│ ├── 使用 Pre-Pass 颜色作为背景              │
│ └── Transmission 材质采样 Pre-Pass 结果     │
└─────────────────────────────────────────────┘
```

---

## 七、正常 Mesh 渲染 Pass 详细分析

### 7.1 Opaque Pass（不透明渲染）

**特点：**
- 按 Material 排序（减少 PSO 切换）
- 执行完整 PBR 着色
- 应用阴影、光照、环境光

**Render Slot 配置：**
```json
{
    "renderSlot": "CORE3D_RS_DM_FW_OPAQUE",
    "renderSlotSortType": "by_material",  // 按材质排序
    "renderSlotCullType": "view_frustum_cull"
}
```

**排序目的：**
```cpp
// by_material 排序
// 减少相同材质的 PSO 切换次数
// 优化渲染性能
```

### 7.2 Translucent Pass（透明渲染）

**特点：**
- 从后向前排序（Back-to-Front）
- 启用颜色混合
- 可能使用 OIT（Order Independent Transparency）

**Render Slot 配置：**
```json
{
    "renderSlot": "CORE3D_RS_DM_FW_TRANSLUCENT",
    "renderSlotSortType": "back_to_front",  // 从后向前排序
    "renderSlotCullType": "view_frustum_cull"
}
```

**排序目的：**
```cpp
// back_to_front 排序
// 保证透明物体正确的混合顺序
// 前面的物体在后面物体之上渲染
```

### 7.3 多子渲染 Pass（Subpass）

正常 Mesh Pass 通常使用多个 Subpass：

```
Subpass 0: Opaque + Velocity/Normal
├── Depth Attachment (Write)
├── Color Attachment (Write)
├── Velocity/Normal Attachment (Write)
└── 子渲染 Pass 标志: merge_bit

Subpass 1: Environment
├── Depth Attachment (Read/Write)
├── Color Attachment (Read/Write)
└── 子渲染 Pass 标志: merge_bit

Subpass 2: Translucent
├── Depth Attachment (Read Only)
├── Color Attachment (Read/Write)
└── 子渲染 Pass 标志: merge_bit
```

**merge_bit 的作用：**
- 合并相邻子渲染 Pass 到同一个 Render Pass
- 减少 Render Pass 切换开销
- 允许 Subpass 间共享 Attachment

---

## 八、三种 Pass 的数据流对比

### 8.1 Shader/材质数据绑定对比

| 数据来源 | 阴影 Pass | Depth Pre-Pass | 正常 Pass |
|---------|----------|----------------|----------|
| **Shader 来源** | `depthShader` | `depthShader` | `materialShader` |
| **Graphics State 来源** | `depthShader.graphicsState` | `depthShader.graphicsState` | `materialShader.graphicsState` |
| **材质纹理** | 极少使用 | 极少使用 | 全部使用 |
| **材质 Uniforms** | 简化版 | 简化版 | 完整版 |

### 8.2 Descriptor Set 绑定对比

```
阴影 Pass:
├── Set 0: Camera Data + General Data
├── Set 1: Mesh Matrix + Material Data
├── Set 2: Material Resources (可选，alpha mask)
└── Set 3: Custom Resources (不使用)

Depth Pre-Pass:
├── Set 0: Camera Data + Scene Data
├── Set 1: Mesh Matrix + Material Data
├── Set 2: Material Resources (极少)
└── Set 3: Custom Resources (不使用)

正常 Pass:
├── Set 0: Camera Data + Scene Data + Lighting Data
├── Set 1: Mesh Matrix + Skin Matrix + Material Data
├── Set 2: Material Resources (全部纹理)
├── Set 3: Custom Resources (自定义材质)
└── Set 4+: 后处理绑定
```

### 8.3 PSO 创建对比

```cpp
// 阴影 Pass PSO 创建
ShaderStateData ssd {
    ssp.shaderHandle,      // 使用 depthShader
    ssp.gfxStateHandle,    // 使用 depthShader.graphicsState
    ...
};
ssd.hash = HashShaderAndSubmesh(ssd.hash, currMaterialFlags.renderDepthHash, ia);
// 使用 renderDepthHash（不同于正常渲染的 renderHash）

// 正常 Pass PSO 创建
ShaderStateData ssd {
    ssp.shaderHandle,      // 使用 materialShader
    ssp.gfxStateHandle,    // 使用 materialShader.graphicsState
    ...
};
ssd.hash = HashShaderDataAndSubmesh(ssd.hash, renderSubmeshMaterialFlags.renderHash, lightingFlags, ...);
// 使用完整 hash（包含 lighting、camera、postProcess flags）
```

---

## 九、性能优化对比

### 9.1 阴影 Pass 性能优化

```cpp
// 1. Shadow Atlas 减少资源切换
// 所有阴影光源渲染到同一个 Shadow Atlas
// 减少 Render Pass 切换

// 2. 最简化 Shader
// 仅计算深度，不执行复杂着色

// 3. 动态 Viewport 控制
// 每个光源使用 Viewport Offset 定位到 Atlas 区域

// 4. VSM 额外 Blur Pass
// 后续执行 Blur Pass 软化阴影边缘
```

### 9.2 Depth Pre-Pass 性能优化

```cpp
// 1. 低分辨率渲染
// 使用 1/2 或 1/4 分辨率减少像素数量

// 2. 最简化 Shader
// 仅计算深度，不执行光照计算

// 3. 减少主 Pass Overdraw
// 提前填充深度，主 Pass 丢弃被遮挡像素

// 4. Transmission 材质专用
// 为 Transmission 提供背景深度
```

### 9.3 正常 Pass 性能优化

```cpp
// 1. Material 排序（Opaque）
// 减少相同材质间的 PSO 切换

// 2. View Frustum Culling
// 丢弃视野外的几何体

// 3. 多子渲染 Pass（Subpass）
// 合并相关渲染，减少 Render Pass 切换

// 4. Bindless 模式
// 使用 Bindless Descriptor Set 减少资源绑定
```

---

## 十、示例：完整渲染流程

### 10.1 场景配置

假设有一个场景：
- 1 个 Directional Light（阴影光源）
- 2 个 Camera（Camera A, Camera B）
- 100 个 Opaque Mesh
- 10 个 Translucent Mesh
- 5 个 Transmission Mesh

### 10.2 渲染流程执行

```
Frame Rendering Timeline:

=== Scene Level (core3d_rng_scene.rng) ===
[1] RenderNodeDefaultLights
    └── 处理 1 个 Directional Light 数据

[2] RenderNodeDefaultCameras
    └── 处理 Camera A 和 Camera B 数据

[3] RenderNodeDefaultMaterialObjects
    └── 提交 110 个 Mesh 的材质数据

[4] RenderNodeMorph
    └── 处理 Morph Target（如果有）

[5] RenderNodeDefaultShadowRenderSlot  ← 【阴影 Pass】
    ├── 创建 Shadow Atlas (2048 x 2048)
    ├── BeginRenderPass (Shadow Atlas)
    ├── 渲染 Light 0 的阴影
    │   ├── Viewport: (0, 0) 到 (2048, 2048)
    │   ├── 渲染所有阴影投射者（约 100 个 Mesh）
    │   ├── 使用 depthShader
    │   └── 输出深度到 Shadow Atlas
    └── EndRenderPass

[6] RenderNodeDefaultShadowsBlur
    └── 对 Shadow Atlas 执行 Blur（VSM 模式）

[7] RenderNodeDefaultEnvironmentBlender
    └── 处理环境 Cubemap

=== Camera A Level ===
[1] RenderNodeDefaultCameraController
    └── 创建 depth/color/velocity_normal Render Targets

[2] Pre-Pass (自动触发，因为有 Transmission)  ← 【Depth Pre-Pass】
    ├── Camera 配置: ALLOW_COLOR_PRE_PASS_BIT
    ├── 创建低分辨率 Render Targets (512 x 512)
    ├── BeginRenderPass
    ├── 渲染所有 Opaque Mesh（仅深度）
    │   ├── 使用 depthShader
    │   ├── 不执行光照计算
    │   └── 输出深度 + 降采样颜色
    ├── 渲染 Environment
    ├── PostProcess 降采样
    └── EndRenderPass

[3] RenderNodeDefaultMaterialRenderSlot (Opaque)  ← 【Opaque Pass】
    ├── BeginRenderPass (Subpass 0)
    ├── 渲染 100 个 Opaque Mesh
    │   ├── 使用 materialShader
    │   ├── 执行完整 PBR 着色
    │   ├── 应用阴影（采样 Shadow Atlas）
    │   ├── 应用光照
    │   ├── 排序: by_material
    │   └── 输出 color + depth + velocity_normal
    └── (Subpass 继续)

[4] RenderNodeDefaultEnv  ← 【Environment Pass】
    ├── (Subpass 1, merge_bit)
    ├── 渲染天空盒/环境
    └── 输出到 color attachment

[5] RenderNodeDefaultMaterialRenderSlot (Translucent)  ← 【Translucent Pass】
    ├── (Subpass 2, merge_bit)
    ├── 渲染 10 个 Translucent Mesh
    │   ├── 使用 materialShader
    │   ├── 启用混合
    │   ├── 排序: back_to_front
    │   └── Transmission Mesh 采样 Pre-Pass 结果
    └── EndRenderPass

[6] PostProcess Nodes
    └── Tone Mapping, Bloom, FXAA 等

=== Camera B Level ===
[重复 Camera A 的流程]
└── Camera B 可能不触发 Pre-Pass（无 Transmission 视野）
```

### 10.3 资源传递关系

```
资源流向图:

Shadow Pass 输出:
└── Shadow Atlas (d16_unorm)
    ↓
    ├── Camera A 主 Pass (作为 Sampler)
    ├── Camera B 主 Pass (作为 Sampler)
    └── ...

Pre-Pass 输出:
├── 低分辨率深度 (d16_unorm)
├── 低分辨率颜色 (降采样)
    ↓
    └── Camera A 主 Pass (Transmission 材质采样)

主 Pass 输出:
├── color (b10g11r11_ufloat_pack32)
├── depth (d32_sfloat)
├── velocity_normal (r16g16_sfloat)
    ↓
    └── PostProcess Nodes
    └── 下一帧 History Buffer
```

---

## 十一、关键代码位置

| 功能 | 文件路径 |
|------|---------|
| Shadow Pass 实现 | `src/render/node/render_node_default_shadow_render_slot.cpp` |
| 正常 Pass 实现 | `src/render/node/render_node_default_material_render_slot.cpp` |
| 材质数据处理 | `src/render/node/render_node_default_material_objects.cpp` |
| 场景级 RNG 配置 | `assets/3d/rendernodegraphs/core3d_rng_scene.rng` |
| Camera 级 RNG 配置 | `assets/3d/rendernodegraphs/core3d_rng_cam_scene_hdrp.rng` |
| Pre-Pass RNG 配置 | `assets/3d/rendernodegraphs/core3d_rng_cam_scene_pre_pass.rng` |
| Render Slot 定义 | `render/default_material_constants.h` |
| 阴影 Shader 常量 | `render/default_material_constants.h` |
| 阴影 Blur 实现 | `src/render/node/render_node_default_shadows_blur.cpp` |

---

## 十二、总结

### 12.1 三种 Pass 的核心差异

| 维度 | 阴影 Pass | Depth Pre-Pass | 正常 Pass |
|------|----------|----------------|----------|
| **执行时机** | 所有 Camera 前 | Camera 主 Pass 前 | Camera 主流程 |
| **渲染视角** | 光源视角 | Camera 视角 | Camera 视角 |
| **输出目的** | 阴影贴图 | 减少 Overdraw | 最终图像 |
| **Shader 类型** | depthShader | depthShader | materialShader |
| **着色复杂度** | 最低 | 低 | 最高 |
| **排序方式** | by_material | by_material | by_material / back_to_front |
| **全局性** | 全局资源 | Camera 级 | Camera 级 |

### 12.2 选择建议

| 场景 | 建议配置 |
|------|---------|
| **无阴影场景** | 禁用 Shadow Pass |
| **大量透明物体** | 启用 Pre-Pass + OIT |
| **Transmission 材质** | 自动触发 Pre-Pass |
| **性能优先** | 使用 Pre-Pass + Deferred |
| **移动端** | 使用 LWRP + 酌情 Pre-Pass |

### 12.3 最佳实践

1. **阴影 Pass：**
   - 使用合适的 Shadow Map 分辨率
   - 避免过多阴影光源
   - VSM 适合软阴影，PCF 适合硬阴影

2. **Depth Pre-Pass：**
   - 仅在有明确需求时启用
   - Transmission 材质自动触发
   - 考虑低分辨率优化

3. **正常 Pass：**
   - Opaque 按 Material 排序
   - Translucent 按 Back-to-Front 排序
   - 使用多子渲染 Pass 合并相关渲染

---

## 十三、Transmission 材质自动触发 Depth Pre-Pass 的机制

### 13.1 Transmission 材质的特殊性

**Transmission（透射）材质** 是一种特殊的透明材质类型（如玻璃、水等），它允许光线穿过物体表面。

**技术挑战：**
- Transmission 材质需要看到物体背后的背景颜色
- 传统的透明渲染（Alpha Blend）无法正确处理复杂的透射效果
- 需要预先知道场景中其他物体的颜色和深度信息

**解决方案：** 使用 Depth Pre-Pass 预先渲染背景，Transmission 材质在主 Pass 中采样 Pre-Pass 结果。

### 13.2 自动触发机制

Transmission 材质会自动触发 Depth Pre-Pass，这一机制发生在 Render System 的材质处理阶段：

```cpp
// render_system.cpp:1912-1920
void RenderSystem::EvaluateRenderDataStoreOutput() {
    const auto info = dsMaterial_->GetRenderFrameObjectInfo();

    // 检查场景中是否存在 Transmission 材质
    if (info.renderMaterialFlags & RenderMaterialFlagBits::RENDER_MATERIAL_TRANSMISSION_BIT) {
        // 如果存在，设置 NEEDS_COLOR_PRE_PASS 标志
        renderProcessing_.frameFlags |= NEEDS_COLOR_PRE_PASS;  // ← 自动触发 Pre-Pass
    }

    // ...
}
```

### 13.3 Pre-Pass Camera 的创建

当 `NEEDS_COLOR_PRE_PASS` 标志被设置后，Render System 会自动创建 Pre-Pass Camera：

```cpp
// render_system.cpp:2239-2252
const bool createPrePassCam =
    (component.pipelineFlags & CameraComponent::FORCE_COLOR_PRE_PASS_BIT) ||   // 强制触发
    (component.pipelineFlags & CameraComponent::ALLOW_COLOR_PRE_PASS_BIT);      // 允许自动触发

if (createPrePassCam) {
    // 计算 Pre-Pass Camera 的唯一 ID
    prePassCameraHash = Hash(camera.id, camera.id);

    // 设置 Pre-Pass 颜色目标的名称
    camera.prePassColorTargetName = renderScene.name +
                                     DefaultMaterialCameraConstants::CAMERA_COLOR_PREFIX_NAME +
                                     to_hex(prePassCameraHash) + '_' + to_hex(prePassCameraHash);

    // 创建 Pre-Pass RenderCamera
    tmpCameras.push_back(CreateColorPrePassRenderCamera(
        *gpuHandleMgr_, *cameraMgr_, *gpuResourceMgr_, camera,
        component.prePassCamera, prePassCameraHash, backendType_));
}
```

### 13.4 Camera 排序与依赖关系

当存在 Pre-Pass 需求时，Camera 的排序会发生变化：

```cpp
// render_system.cpp:2923
const vector<CameraOrdering> baseCameras =
    SortCameras(renderCameras, (renderProcessing_.frameFlags & NEEDS_COLOR_PRE_PASS));
```

```cpp
// render_system.cpp:1159-1162
// Pre-Pass Camera 作为主 Camera 的依赖
if (!(cam.flags & RenderCamera::CAMERA_FLAG_COLOR_PRE_PASS_BIT) || prepassRequired) {
    depCameras.push_back({ cam.id, cam.mainCameraId, camIdx });
}
```

**排序结果：**
```
Pre-Pass Camera → 主 Camera → 其他 Camera
```

Pre-Pass Camera 必须在其主 Camera 之前执行，以便主 Camera 可以使用 Pre-Pass 的结果。

---

## 十四、Pre-Pass 输出在主 Pass 中的使用

### 14.1 Pre-Pass 输出的传递方式

Pre-Pass 渲染的颜色输出通过以下方式传递给主 Pass：

**Shader Binding 位置：**
```glsl
// 3d_dm_frag_layout_common.h:57
layout(set = 0, binding = 7) uniform CORE_RELAXEDP sampler2D uSampColorPrePass;
```

这个 sampler 在所有使用 Default Material Fragment Layout 的 shader 中都可用。

### 14.2 Pre-Pass 输出的内容

Pre-Pass Camera 渲染以下内容：

```
Pre-Pass Output (降采样):
├── Depth Buffer (d16_unorm)     ← 低精度深度
├── Color Buffer (降采样)        ← 背景/不透明物体颜色
│   ├── Mip Level 0: 全分辨率
│   ├── Mip Level 1: 1/2 分辨率
│   ├── Mip Level 2: 1/4 分辨率
│   └── ...
└── PostProcess 降采样           ← 最终输出用于主 Pass
```

**降采样配置示例：**
```json
{
    "name": "output",
    "format": "b10g11r11_ufloat_pack32",
    "mipCount": 6,  // 多级降采样，用于不同精度的 Transmission
    "usageFlags": "color_attachment | sampled"
}
```

### 14.3 Transmission 材质的透射计算

Transmission 材质在 shader 中使用 Pre-Pass 颜色进行透射效果：

```glsl
// 3d_dm_lighting_common.h:138-145
void AppendIndirectTransmission(
    in CORE_RELAXEDP vec3 radianceSample,   // Pre-Pass 采样结果
    in CORE_RELAXEDP vec3 baseColor,        // 材质基础颜色
    in CORE_RELAXEDP float transmission,    // 透射系数
    inout CORE_RELAXEDP vec3 irradiance)    // 输出光照结果
{
    // Approximate double refraction by assuming a solid sphere beneath the point.
    const CORE_RELAXEDP vec3 Ft = radianceSample * baseColor.rgb;
    irradiance *= (1.0 - transmission);     // 减少直接光照
    irradiance = mix(irradiance, Ft, transmission);  // 混合透射颜色
}
```

### 14.4 完整的 Transmission 渲染流程

```
Pre-Pass 渲染流程:
┌─────────────────────────────────────────────┐
│ 1. Camera Controller (Pre-Pass 配置)        │
│    ├── 创建降采样 Render Target             │
│    └── 配置 depth/color attachment          │
│                                             │
│ 2. Opaque Render Slot                      │
│    ├── 渲染所有不透明几何体                  │
│    ├── 使用 depthShader (简化版)            │
│    ├── 输出 depth + color                   │
│    └── 不执行完整光照计算                   │
│                                             │
│ 3. Environment Render                      │
│    └── 渲染天空盒/环境                      │
│                                             │
│ 4. PostProcess (降采样)                    │
│    ├── 将 color 降采样到多级 mip            │
│    └── 输出最终的 prePassColor              │
└─────────────────────────────────────────────┘
           ↓
    uSampColorPrePass (set 0, binding 7)
           ↓
┌─────────────────────────────────────────────┐
│ 主 Pass 渲染流程:                            │
│                                             │
│ Transmission 材质 Fragment Shader:          │
│                                             │
│ 1. 计算当前像素的 UV 坐标                   │
│ 2. 根据透射系数计算采样参数                 │
│    ├── transmission = material.transmission │
│    ├── 选择合适的 mip level                 │
│    └── 应用 UV 偏移（模拟折射）             │
│                                             │
│ 3. 采样 Pre-Pass 颜色                       │
│    vec3 backgroundColor = textureLod(       │
│        uSampColorPrePass,                   │
│        refractedUV,                         │
│        mipLevel                             │
│    );                                       │
│                                             │
│ 4. 计算 Transmission 最终颜色               │
│    vec3 transmissionColor = backgroundColor │
│        * baseColor                          │
│        * transmission;                      │
│                                             │
│ 5. 混合透射颜色与直接光照                   │
│    finalColor = mix(                        │
│        directLighting,                      │
│        transmissionColor,                   │
│        transmission                         │
│    );                                       │
└─────────────────────────────────────────────┘
```

### 14.5 Pre-Pass Depth 的使用

虽然 Pre-Pass 输出了深度，但在主 Pass 中**深度通常不通过采样使用**：

**原因：**
- 主 Pass 有自己的深度缓冲，通过 Early-Z 测试优化
- Pre-Pass 的低精度深度（d16_unorm）不适合直接用于主 Pass
- 主 Pass 通常使用更高精度的深度（d32_sfloat）

**Pre-Pass Depth 的实际用途：**
- Pre-Pass 自身的深度测试（减少 Pre-Pass 的 overdraw）
- 不传递给主 Pass（`storeOp: dont_care`）

```json
// Pre-Pass depth attachment 配置
{
    "name": "depth",
    "format": "d16_unorm",
    "loadOp": "clear",
    "storeOp": "dont_care"  // 不保存，不传递给主 Pass
}
```

### 14.6 Pre-Pass Color 的 Mip Level 选择

Transmission 材质根据透射系数选择不同精度的背景采样：

```glsl
// 选择 mip level 的逻辑示例
float transmission = uMaterialData.factors[CORE_MATERIAL_FACTOR_TRANSMISSION_IDX].x;
float mipLevel = 0.0;

// 高透射系数使用低分辨率 mip（模糊效果）
if (transmission > 0.8) {
    mipLevel = 2.0;  // 使用 1/4 分辨率
} else if (transmission > 0.5) {
    mipLevel = 1.0;  // 使用 1/2 分辨率
} else {
    mipLevel = 0.0;  // 使用全分辨率
}

vec3 backgroundColor = textureLod(uSampColorPrePass, uv, mipLevel);
```

**设计意图：**
- 高透射材质（如透明玻璃）使用模糊背景更自然
- 低透射材质（如薄玻璃）使用清晰背景更精确
- 减少高透射材质的采样开销

---

## 十五、Pre-Pass 自动触发 vs 手动触发

### 15.1 触发方式对比

| 触发方式 | 配置标志 | 触发时机 | 应用场景 |
|---------|---------|---------|---------|
| **自动触发** | `ALLOW_COLOR_PRE_PASS_BIT` | 场景存在 Transmission 材质 | Transmission 材质渲染 |
| **强制触发** | `FORCE_COLOR_PRE_PASS_BIT` | 每帧都执行 | 性能优化（减少 overdraw） |
| **禁用** | 无上述标志 | 永不触发 | 无 Transmission 的场景 |

### 15.2 Camera 配置示例

```cpp
// 自动触发（推荐）
CameraComponent camera;
camera.pipelineFlags = CameraComponent::PipelineFlagBits::ALLOW_COLOR_PRE_PASS_BIT;
// 场景存在 Transmission 材质时自动触发

// 强制触发（性能优化）
CameraComponent camera;
camera.pipelineFlags = CameraComponent::PipelineFlagBits::FORCE_COLOR_PRE_PASS_BIT;
// 每帧都执行 Pre-Pass，即使没有 Transmission 材质

// 禁用 Pre-Pass
CameraComponent camera;
camera.pipelineFlags = 0;  // 不设置任何 Pre-Pass 相关标志
// 永不触发 Pre-Pass
```

### 15.3 自动触发的优缺点

**优点：**
- 无需手动判断场景内容
- 仅在有 Transmission 材质时触发，节省性能
- 自动创建 Pre-Pass Camera，简化配置

**缺点：**
- Pre-Pass Camera 增加内存和 GPU 开销
- 可能与手动配置的 Pre-Pass Camera 冲突
- 自动创建的 Pre-Pass Camera 可能不满足特殊需求

### 15.4 何时选择强制触发

**推荐强制触发的场景：**
1. **复杂场景（大量 Overdraw）：**
   - Pre-Pass 提前填充深度，减少主 Pass 的像素计算

2. **延迟渲染（Deferred）：**
   - Pre-Pass 提供 G-Buffer 的基础数据

3. **自定义 Transmission 效果：**
   - 需要特定的 Pre-Pass 配置（分辨率、降采样等）

---

## 十六、代码位置参考

| 功能 | 文件路径 |
|------|---------|
| Transmission 自动触发检测 | `src/ecs/systems/render_system.cpp:1916-1919` |
| Pre-Pass Camera 创建 | `src/ecs/systems/render_system.cpp:2239-2252` |
| Camera 排序逻辑 | `src/ecs/systems/render_system.cpp:1140-1178` |
| Pre-Pass 颜色 Shader Binding | `api/3d/shaders/common/3d_dm_frag_layout_common.h:57` |
| Transmission Shader 处理 | `api/3d/shaders/common/3d_dm_lighting_common.h:138-145` |
| Render Material Flags 定义 | `api/3d/render/render_data_defines_3d.h:187-241` |
| Camera Pipeline Flags 定义 | `api/3d/ecs/components/camera_component.h:63-104` |

---

**文档版本**: 1.1
**创建日期**: 2026-05-18
**更新日期**: 2026-05-18
**状态**: 已更新 - 新增 Transmission 自动触发 Pre-Pass 机制与 Pre-Pass 输出使用说明
