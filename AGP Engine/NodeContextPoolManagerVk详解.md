# NodeContextPoolManagerVk 详解

## 背景

在 Vulkan 渲染后端中，渲染通道（Render Pass）和帧缓冲（Framebuffer）是核心概念——每帧渲染需要创建和管理大量 `VkRenderPass` 和 `VkFramebuffer` 对象。由于这些对象的创建开销较高（涉及驱动内部验证和资源分配），且同一配置在多帧间反复出现，引擎采用**池化管理 + 哈希缓存**策略进行复用。

`NodeContextPoolManagerVk` 是 Vulkan 后端的节点上下文池管理器，负责：
- 命令池/命令缓冲区的环形缓冲管理
- `VkRenderPass` 和 `VkFramebuffer` 的哈希缓存与生命周期管理
- 帧间资源的垃圾回收（GC）

其 GLES 对应物是 `NodeContextPoolManagerGLES`，两者共享基类 `NodeContextPoolManager`，但由于 Vulkan 和 OpenGL ES 的渲染通道模型差异巨大，内部实现截然不同。

---

## 1. 类声明

**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.h:68-104`

```cpp
class NodeContextPoolManagerVk final : public NodeContextPoolManager {
public:
    explicit NodeContextPoolManagerVk(Device&, GpuResourceManager&, const GpuQueue&);
    ~NodeContextPoolManagerVk() override;

    void BeginFrame() override;
    void BeginBackendFrame() override;

    const ContextCommandPoolVk& GetContextCommandPool() const;
    const ContextCommandPoolVk& GetContextSecondaryCommandPool() const;

    LowLevelRenderPassDataVk GetRenderPassData(const RenderCommandBeginRenderPass&);
    static uint64_t HashRenderPass(const RenderCommandBeginRenderPass&);

private:
    void SetValidationDebugName(BASE_NS::string_view) override;

    Device& device_;
    GpuResourceManager& gpuResourceMgr_;
    const GpuQueue gpuQueue_ {};

    uint32_t bufferingIndex_ { 0 };

    vector<ContextCommandPoolVk> commandPools_;
    vector<ContextCommandPoolVk> commandSecondaryPools_;
    ContextFramebufferCacheVk framebufferCache_;
    ContextRenderPassCacheVk renderPassCache_;
    ContextFramebufferCacheVk renderPassCompatibilityCache_;
    RenderPassCreatorVk renderPassCreator_;

    string debugName_;
    bool firstFrame_ { true };
    uint64_t frameIndexFront_ { 0 };
    uint64_t frameIndexBack_ { 0 };
};
```

### 支撑结构体

| 结构体 | 文件:行号 | 用途 |
|--------|----------|------|
| `LowLevelCommandBufferVk` | node_context_pool_manager_vk.h:36-44 | 封装 `VkCommandBuffer` + 3 个 `VkSemaphore` 环形缓冲（帧同步） |
| `ContextCommandPoolVk` | node_context_pool_manager_vk.h:46-50 | 拥有一个 `VkCommandPool` + 一个预分配的 `LowLevelCommandBufferVk` |
| `ContextFramebufferCacheVk` | node_context_pool_manager_vk.h:52-58 | `unordered_map<hash, {frameUseIndex, VkFramebuffer}>` |
| `ContextRenderPassCacheVk` | node_context_pool_manager_vk.h:60-66 | `unordered_map<hash, {frameUseIndex, VkRenderPass}>` |

---

## 2. 核心方法解析

### 2.1 构造函数
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:278-300`

接收 `Device&`、`GpuResourceManager&`、`GpuQueue`（标识队列族）。

创建逻辑：
1. 从 `DeviceVk` 获取队列族索引
2. 按 `device_.GetCommandBufferingCount()`（通常2-3，双/三缓冲）创建 `commandPools_` 和 `commandSecondaryPools_`
3. 每个池通过 `CreateContextCommandPool()` 创建：
   - 创建 `VkCommandPool`（指定队列族）
   - 预分配一个 `VkCommandBuffer`（主级或次级）
   - 每个命令缓冲区预创建 **3 个信号量**（`SEMAPHORE_BUFFERING_COUNT = 3`），处理交换链旋转的额外同步需求

### 2.2 析构函数
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:302-342`

按顺序销毁：信号量 → 命令池 → 帧缓冲缓存 → 渲染通道缓存（两个） → 兼容渲染通道缓存。

### 2.3 BeginFrame()
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:344-349`

前端线程调用（`renderer.cpp:238`），仅记录 `frameIndexFront_`（验证用）。

### 2.4 BeginBackendFrame()
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:351-410`

后端线程每帧调用，执行三项关键操作：

**① 推进环形缓冲**：

```cpp
bufferingIndex_ = (bufferingIndex_ + 1U) % (uint32_t)commandPools_.size();
auto& semaphoreIdxRef = commandPools_[bufferingIndex_].commandBuffer.semaphoreIdx;
semaphoreIdxRef = (semaphoreIdxRef + 1U) % LowLevelCommandBufferVk::SEMAPHORE_BUFFERING_COUNT;
```

这里有两层环形结构，关键是 `semaphoreIdx` 存储在每个命令缓冲区内部（而非类成员），形成**嵌套环**：

```
外环: bufferingIndex_  按 commandPools_.size()（= bufferingCount）轮转
内环: semaphoreIdx     按 SEMAPHORE_BUFFERING_COUNT (= 3) 轮转，归属当前 commandPool 的 commandBuffer
```

以 `bufferingCount = 2` 为例，6 帧的轮转过程：

```
帧  bufferingIndex_   池的 semaphoreIdx   使用的信号量
0      0              pool[0]: 0→1        pool[0].semaphores[1]
1      1              pool[1]: 0→1        pool[1].semaphores[1]
2      0              pool[0]: 1→2        pool[0].semaphores[2]
3      1              pool[1]: 1→2        pool[1].semaphores[2]
4      0              pool[0]: 2→0        pool[0].semaphores[0]
5      1              pool[1]: 2→0        pool[1].semaphores[0]
```

**为什么 semaphoreIdx 存在每个 commandBuffer 内而非类级别？**

两个环的周期不同（`bufferingCount` vs 3），如果用全局计数器，需要额外逻辑对齐。将 `semaphoreIdx` 内嵌到每个 commandBuffer，每个池独立追踪自己的信号量位置，`bufferingIndex_` 回到同一池时自然接续上次的进度，逻辑简洁。

**为什么每个 commandBuffer 需要 3 个信号量（> bufferingCount）？**

源码注释说明：

> *more semaphores for rotation, e.g for cases where swapchain is used and does not acquire the next index normally*
> *the amount is excessive, but basically would need different semaphores per swapchain if not having extra*

Vulkan 中信号量在 `vkAcquireNextImageKHR` / `vkQueueSubmit` 中使用后进入**已信号状态**，同一信号量不能在同一帧被再次等待。交换链图像获取可能因窗口最小化、表面丢失等原因失败或跳帧，导致信号量被消耗但未正常配对。若信号量数量等于 `bufferingCount`，跳帧后会无可用信号量。3 > 典型 bufferingCount(2-3)，提供冗余槽位应对异常帧节奏。

**② 缓存垃圾回收（GC）**：

每帧遍历帧缓冲缓存和渲染通道缓存，销毁不再使用的 Vulkan 对象。核心机制如下：

```
constexpr uint64_t additionalFrameCount { 2u };
const auto minAge = bufferingCount + additionalFrameCount;
const auto ageLimit = (frameCount < minAge) ? 0 : (frameCount - minAge);

对每个缓存条目：
  if entry.frameUseIndex < ageLimit:
      vkDestroyFramebuffer / renderPassCreator_.DestroyRenderPass
      从 map 中移除
  else:
      保留（条目仍可能在后续帧使用）
```

**为什么需要 GC 销毁？**

`VkFramebuffer` 和 `VkRenderPass` 是重量级 Vulkan 对象，创建时驱动需分配内部资源（内存、描述符、验证数据等）。若只增不删，缓存会无限膨胀——例如场景切换时旧的渲染通道配置不再出现，对应的缓存条目就永远闲置却占用 GPU 资源。GC 在确认对象安全可回收后销毁它们，防止内存泄漏。

**ageLimit 的含义**

`ageLimit` 是"年龄门槛"——`frameUseIndex` 记录条目最后一次被使用的帧号，若它低于 `ageLimit`，说明该条目已经连续多帧未被命中，可安全销毁：

```
ageLimit = frameCount - (bufferingCount + 2)
         = 当前帧号 - (缓冲帧数 + 2)
```

举例：假设 `bufferingCount = 2`（双缓冲），当前 `frameCount = 100`：
- `ageLimit = 100 - (2 + 2) = 96`
- 若某条目 `frameUseIndex = 94`（第94帧后未再用），94 < 96 → 销毁
- 若某条目 `frameUseIndex = 98`（第98帧还在用），98 ≥ 96 → 保留

**为什么 +2 而不是 +0？**

Vulkan 帧是**异步执行**的：CPU 提交命令后，GPU 可能还在执行 `bufferingCount` 帧之前的命令。如果只减 `bufferingCount`，恰好处于"GPU 刚完成最后一帧使用该对象"的边界时刻，销毁可能导致 GPU 访问已释放资源（use-after-free）。额外 `+2` 提供安全余量：

```
缓冲帧数保证：CPU 已提交 → GPU 尚未完成的帧数
+2 余量保证：即使 GPU 调度有额外延迟，对象仍安全
```

**活跃条目如何避免被 GC？**

`GetRenderPassData()` 每次命中缓存时执行 touch 操作：`entry.frameUseIndex = frameCount`，将条目的"最后使用帧号"更新为当前帧。因此持续使用的条目 `frameUseIndex` 始终接近 `frameCount`，远高于 `ageLimit`，永远不会被 GC 回收。只有真正不再使用的条目才会因 `frameUseIndex` 停滞而被年龄门槛淘汰。

**③ 首帧调试命名**（仅验证构建）。

### 2.5 GetRenderPassData() — 核心方法
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:429-533`

输入 `RenderCommandBeginRenderPass`，输出完整的 `LowLevelRenderPassDataVk`（包含 Vulkan 渲染通道所需的全部对象）。

**执行流程**：

```
RenderCommandBeginRenderPass
           │
           ▼
   ① 收集兼容性信息
   ├─ 每个附件：查 GpuImageVk → 格式/采样数/aspectFlags
   ├─ 首个附件：计算 viewport/scissor/帧缓冲尺寸
   ├─ 检测交换链附件 → surfaceTransformFlags
   └─ 检测多视图 → viewMask
           │
           ▼
   ② 计算三重哈希（HashBeginRenderPass）
   ├─ renderPassCompatibilityHash: 格式+采样数+管线阶段+子通道描述
   ├─ renderPassHash: 兼容性哈希+布局+加载/存储操作
   └─ frameBufferHash: 兼容性哈希+GPU句柄ID+Vulkan图像ID+mip/layer
           │
           ▼
   ③ 查找/创建兼容渲染通道（renderPassCompatibilityCache_）
           │
           ▼
   ④ 查找/创建帧缓冲（framebufferCache_）
           │
           ▼
   ⑤ 查找/创建完整渲染通道（renderPassCache_）
           │
           ▼
   返回 LowLevelRenderPassDataVk
```

**三重哈希的设计意图**：

| 哈希 | 范围 | 用途 |
|------|------|------|
| `renderPassCompatibilityHash` | 格式+采样数+阶段+子通道 | Vulkan 渲染通道兼容性——兼容的 RP 可共享帧缓冲 |
| `renderPassHash` | 兼容性 + 布局 + 加载/存储操作 | 唯一标识完整渲染通道配置 |
| `frameBufferHash` | 兼容性 + GPU 句柄 + 图像 ID + mip/layer | 唯一标识帧缓冲（同一 RP 配置可绑定不同图像） |

这种分层设计使得：相同格式/采样数配置的不同渲染通道可以复用兼容 RP 对象，减少 `vkCreateRenderPass` 调用。

### 2.6 HashRenderPass()
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:535-553`

公开静态方法，用于次级命令缓冲区场景的验证。哈希字段与内部 `HashBeginRenderPass()` 不同——此方法哈希 layer/mip/handle/renderArea/subpassCount，用于检测跨次级命令缓冲区的渲染通道兼容性。

---

## 3. 池化管理策略

### 3.1 资源池总览

| 资源 | 池结构 | 缓存键 | 创建时机 | 回收方式 |
|------|--------|--------|---------|---------|
| 命令池 + 缓冲区 | `vector<ContextCommandPoolVk>` | `bufferingIndex_` 环形索引 | 构造时（预分配） | 每帧 `vkResetCommandPool` 重置 |
| 信号量 | 3个/命令缓冲区 | `semaphoreIdx` 环形索引 | 构造时（预分配） | 帧间轮转 |
| 帧缓冲 | `ContextFramebufferCacheVk` 哈希表 | `frameBufferHash` | 首次使用 | GC（`frameUseIndex < ageLimit`） |
| 渲染通道 | `ContextRenderPassCacheVk` 哈希表 | `renderPassHash` | 首次使用 | GC |
| 兼容渲染通道 | `ContextRenderPassCacheVk` 哈希表 | `renderPassCompatibilityHash` | 首次使用 | GC |

### 3.2 命令缓冲区嵌套环形缓冲

```
外环: bufferingIndex_  按 bufferingCount 轮转（选择哪个命令池）
内环: semaphoreIdx     按 3 轮转，内嵌于每个 commandBuffer（选择池内哪个信号量）

每帧选取: commandPools_[bufferingIndex_].commandBuffer.semaphores[semaphoreIdx]
```

两个环周期不同（`bufferingCount` vs 3），`semaphoreIdx` 内嵌于 commandBuffer 使得每个池独立追踪，回绕时自然接续。3 个信号量 > 典型 bufferingCount，为交换链跳帧提供冗余。

### 3.3 缓存条目生命周期

```
创建: 插入 map，frameUseIndex = 0（兼容RP）或 frameCount（完整RP/FB）
命中: 更新 frameUseIndex = frameCount（touch，保持存活）
GC:   frameUseIndex < ageLimit → 销毁 Vulkan 对象 + 从 map 移除
```

兼容渲染通道在创建时 `frameUseIndex = 0`，但 `GetRenderPassData` 总是先查找兼容缓存再查找帧缓冲缓存，因此帧缓冲命中前兼容条目必先被 touch 更新，保证兼容 RP 不会被先于帧缓冲被 GC 回收。

---

## 4. 与其他类的协作

```
┌─────────────┐     创 建     ┌───────────────────────────┐
│  DeviceVk   │ ────────────> │  NodeContextPoolManagerVk │
└─────────────┘               └─────────────┬─────────────┘
                                            │
       ┌────────────────────────────────────┤
       │                                    │
       ▼                                    ▼
┌──────────────┐                 ┌───────────────────┐
│ GpuResource  │                 │ RenderPassCreator │
│   Manager    │ ←  图像查找      │        Vk         │ ← RP 创建委托
└──────────────┘                 └───────────────────┘
       │
       │  GpuImageVk 平台数据
       ▼
┌──────────────┐
│RenderBackend │ ← 消费 GetRenderPassData() 返回值
│     Vk       │ ← 调用 BeginBackendFrame()
└──────────────┘
       │
       ▼
   vkCmdBeginRenderPass(renderPass, framebuffer, …)
```

| 协作类 | 交互方式 |
|--------|---------|
| `DeviceVk` | 工厂创建（`device_vk.cpp:1488`），提供 `VkDevice`、缓冲计数、帧计数、队列信息、表面变换标志、多视图扩展检查 |
| `RenderBackendVk` | 主消费者：调用 `BeginBackendFrame()`、`GetContextCommandPool()`、`GetRenderPassData()` |
| `GpuResourceManager` | 提供 `GpuImageVk*` 查找（格式、采样数、图像视图） |
| `RenderPassCreatorVk` | 拥有的成员，委托 `vkCreateRenderPass` 调用 |
| `Renderer` | 前端线程调用 `BeginFrame()` |

---

## 5. Vulkan 与 GLES 实现对比

| 方面 | Vulkan (`PoolManagerVk`) | GLES (`PoolManagerGLES`) |
|------|-------------------------|--------------------------|
| **命令池管理** | 显式：`VkCommandPool` + 预分配命令缓冲区 + 信号量环形缓冲 | 无（GLES 隐式管理） |
| **次级命令池** | 有：独立的 `commandSecondaryPools_` | 无 |
| **渲染通道缓存** | **三层**：兼容 RP / 完整 RP / 帧缓冲（独立哈希表） | **单层**：`renderPassHashToIndex` 映射 |
| **帧缓冲存储** | `VkFramebuffer`（Vulkan 对象，按哈希缓存） | `LowlevelFramebufferGL` 含 `vector<SubPassPair>`（每子通道一个 FBO + 可选解析 FBO） |
| **哈希策略** | 3 个独立哈希（兼容性/完整/帧缓冲） | 1 个组合哈希 |
| **MSAA 解析** | **隐式**：Vulkan 渲染通道的解析附件，驱动自动处理 | **显式**：创建独立解析 FBO，`glBlitFramebuffer` 或 `GL_EXT_multisampled_render_to_texture2` |
| **渲染到纹理优化** | 不需要（Vulkan 原生支持） | `multisampledRenderToTexture_` 标志；`FilterRenderPass()` **重写**渲染通道描述，将渲染目标直接指向解析纹理 |
| **附件重映射** | 无 | `imageMap_`：将颜色/深度附件映射到解析目标；重写子通道附件索引 |
| **多视图处理** | `viewMask` 在 `VkSubpassDescription` + `mipImageAllLayerViews` | `glFramebufferTextureMultiviewOVR` / `glFramebufferTextureMultisampleMultiviewOVR` |
| **交换链检测** | `RenderHandleUtil::IsSwapchain()` + `surfaceTransformFlags` | `IsDefaultAttachment()` 检查 GL 图像 ID 和 renderbuffer 是否均为 0 |
| **Y 翻转** | `surfaceTransformFlags` + 视口旋转 | `RENDER_GL_FLIP_Y_SWAPCHAIN` 编译时标志 |
| **GC/回收** | 哈希表迭代，按 `frameUseIndex < ageLimit` 移除 | 线性扫描 `frameBufferFrameUseIndex[]` 向量 |
| **FBO 验证** | Vulkan 验证层处理 | 显式 `glCheckFramebufferStatus()` + 详细错误日志 |
| **调试命名** | 首帧设置所有命令缓冲区的调试名称 | 空实现 |

**核心差异**：Vulkan 版本将渲染通道描述视为不可变对象，依赖驱动处理解析；GLES 版本则需要主动重写渲染通道描述以实现 MSAA 优化，这是两者最大的架构差异。

---

## 6. 值得注意的实现细节

### 6.1 GPU 句柄哈希的健壮性
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:102-122`

帧缓冲哈希同时包含 `gpuHandle.id` 和 Vulkan 图像 ID。

原因：双重标识防止缓存命中过期条目。
- 浅层句柄可能共享代计数器
- Vulkan 图像 ID 在销毁后可被复用。

### 6.2 兼容渲染通道不 touch 的设计

对比三重缓存命中时的行为：

| 缓存 | 命中时 | 新建时 |
|------|--------|--------|
| 兼容 RP (`renderPassCompatibilityCache_`) | **不 touch**（不更新 `frameUseIndex`） | `frameUseIndex = 0` |
| 帧缓冲 (`framebufferCache_`) | `frameUseIndex = frameCount` | `frameUseIndex = frameCount` |
| 完整 RP (`renderPassCache_`) | `frameUseIndex = frameCount` | `frameUseIndex = frameCount` |

兼容 RP 命中时不 touch 是**有意为之**。要理解为什么安全，需要区分两种场景：

**场景 A：帧缓冲命中（复用）——不需要兼容 RP**

```
帧 N: GetRenderPassData(配置X)
  ① 查兼容缓存 → 命中 → 获取 VkRenderPass 兼容对象（不 touch）
  ② 查帧缓冲缓存 → 命中 → 获取 VkFramebuffer（touch，frameUseIndex = N）
  ③ 查完整 RP 缓存 → 命中 → 获取完整 VkRenderPass（touch）
  → 返回结果，渲染

帧 N+1, N+2, ... : 同配置，帧缓冲持续命中
  → 帧缓冲 frameUseIndex 持续更新，永远不会被 GC
  → 兼容 RP frameUseIndex 停滞不变，可能被 GC
  → 但这不影响任何东西！因为帧缓冲已存在，不需要兼容 RP 参与
```

**场景 B：帧缓冲未命中（新建）——需要兼容 RP，但此时兼容缓存一定有条目**

```
帧 N: GetRenderPassData(新配置X)
  ① 查兼容缓存 → 未命中 → 创建兼容 RP，frameUseIndex = 0
  ② 查帧缓冲缓存 → 未命中 → vkCreateFramebuffer(兼容RP, ...) → frameUseIndex = N
  ③ 查完整 RP 缓存 → 未命中 → vkCreateRenderPass(兼容RP, ...) → frameUseIndex = N
```

关键：步骤②创建帧缓冲时，`VkFramebufferCreateInfo.renderPass` 字段填入兼容 RP。但 Vulkan 规范只要求帧缓冲创建时兼容 RP 存在；**创建完成后，帧缓冲内部已保留兼容性数据，兼容 RP 对象即可销毁**。类比：兼容 RP 是"模具"，帧缓冲是"铸件"，模具用完后可以丢弃。

**为什么兼容 RP 新建时 `frameUseIndex = 0` 而不是 `frameCount`？**

因为 `frameUseIndex = 0` 意味着"这个条目如果后续没有新建需求，可以尽快被 GC"。如果设为 `frameCount`，即使后续帧只做帧缓冲复用（场景 A），兼容 RP 也会被 touch... 但实际上兼容 RP 命中时不 touch，所以设不设都一样。设为 0 更明确地表达了意图：**兼容 RP 的生命周期不应超过它帮助创建的对象**。

**如果兼容 RP 被 GC 了，后来又需要同配置的新帧缓冲怎么办？**

```
帧 100: 配置X 帧缓冲命中（复用），兼容 RP 已被 GC
帧 200: 配置X 的帧缓冲因图像变更失效，需要新建
  ① 查兼容缓存 → 未命中 → 重新 vkCreateRenderPass → frameUseIndex = 0
  ② 查帧缓冲缓存 → 未命中 → vkCreateFramebuffer → frameUseIndex = 200
  → 正常工作，仅多一次 vkCreateRenderPass 调用
```

总结：不 touch 是**主动优化**而非疏忽。兼容 RP 是一次性使用的工厂对象，让它在没有新建需求时尽早被 GC，比保持存活更节省内存。代价仅是偶尔重建的开销（一次 `vkCreateRenderPass`）。

**注意：重复创建循环**

上述设计存在一个实际代价。一旦兼容 RP 被 GC，此后每帧都会经历：

```
帧 N:   BeginBackendFrame → GC: 兼容 RP (frameUseIndex=0 < ageLimit) → 删除
         GetRenderPassData → 兼容缓存未命中 → 重建，frameUseIndex = 0
帧 N+1: BeginBackendFrame → GC: 兼容 RP (frameUseIndex=0 < ageLimit) → 再删除
         GetRenderPassData → 兼容缓存未命中 → 再重建，frameUseIndex = 0
         ...每帧重复...
```

原因：兼容 RP 新建时 `frameUseIndex = 0`，命中时不 touch，所以 `frameUseIndex` 永远停留在 0，始终低于 `ageLimit`，每帧被 GC 又被重建。

不过影响有限：
- 兼容 RP 的 `vkCreateRenderPass` 仅包含格式/采样数/子通道描述，不含加载存储操作，创建开销低于完整 RP
- 仅在帧缓冲持续命中（场景 A）时触发此循环；一旦帧缓冲也未命中（场景 B），完整 RP 和帧缓冲会一起重建，兼容 RP 的开销相比可忽略
- 若要消除此循环，可在命中时也 touch 兼容 RP，代价是兼容 RP 永远不会被 GC，缓存持续膨胀

### 6.3 线程安全

类文档注明仅单线程使用。前端 `BeginFrame()` 和后端 `BeginBackendFrame()` 在不同线程调用但处于不同阶段，通过 `frameIndexFront_ == frameIndexBack_` 断言验证同步。

### 6.4 帧缓冲 ImageView 选择逻辑
**文件位置：** `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp:182-196`

`CreateFramebuffer` 为每个附件选择 `VkImageView` 时，根据 `viewMask`、`arrayLayers`、`mipLevel`、`layer` 四个变量做分支选择。先理解这些变量和预创建的 ImageView 集合：

**四个关键变量**：

| 变量 | 来源 | 含义 |
|------|------|------|
| `viewMask` | `renderPassData.viewMask` | Vulkan 多视图位掩码，bit i = 1 表示渲染到 layer i。`> 1` 表示启用多视图 |
| `arrayLayers` | `GpuImagePlatformDataVk::arrayLayers` | 图像的数组层数（如立方体贴图 = 6） |
| `mipLevel` | `AttachmentDesc::mipLevel` | 渲染目标指向的 mip 等级，0 = 基础分辨率 |
| `layer` | `AttachmentDesc::layer` | 渲染目标指向的数组层，0 = 第一层 |

**预创建的 ImageView 集合**（`GpuImagePlatformDataViewsVk`，仅 color attachment 创建）：

| 集合 | 创建条件 | 每个元素的 VkImageSubresourceRange | 用途 |
|------|---------|-----------------------------------|------|
| `imageViewBase` | 始终 | mip=0, levelCount=1, layer=0, layerCount=1 | 默认视图（mip0 + layer0） |
| `mipImageViews[mip]` | `mipLevels > 1` | mip=索引, levelCount=1, layer=0, layerCount=1 | 单层特定 mip 级别 |
| `mipImageAllLayerViews[mip]` | `mipLevels > 1 && arrayLayers > 1` 或 cube map | mip=索引, levelCount=1, layer=0, layerCount=**arrayLayers** | **全层**特定 mip 级别 |
| `layerImageViews[layer]` | `arrayLayers > 1` | mip=0, levelCount=1, layer=索引, layerCount=1 | 特定层的基础 mip |

**选择逻辑**（按优先级）：

```
默认: imageViewBase (mip=0, layer=0)

① if viewMask > 1 && arrayLayers > 1:     ← 多视图模式
     if mipImageAllLayerViews 非空 && mipLevel 在范围内:
         → mipImageAllLayerViews[mipLevel]  (全层 + 特定mip)
     else:
         → imageView                         (回退)
     size.layers = 1                         ← Vulkan 多视图要求

② else if mipLevel >= 1 && mipLevel < mipImageViews.size():
     → mipImageViews[mipLevel]               (单层 + 特定mip)

③ else if layer >= 1 && layer < layerImageViews.size():
     → layerImageViews[layer]                (特定层 + mip0)
```

**分支设计意图**：

- **分支①**：多视图渲染需要一次性渲染到多个层。`mipImageAllLayerViews` 的 `layerCount = arrayLayers`（如 `VK_IMAGE_VIEW_TYPE_2D_ARRAY`），Vulkan 驱动根据 `viewMask` 将片段路由到对应层。`size.layers = 1` 是 Vulkan 多视图规范要求——帧缓冲声明1层，实际由 `viewMask` 控制多层渲染。

- **分支②**：非多视图但指定了 `mipLevel ≥ 1`（如渲染到降采样 mip 链）。使用 `mipImageViews[mip]`，仅覆盖 layer0、单 mip 级别。`mipLevel = 0` 时不进入此分支，直接使用默认 `imageViewBase`。

- **分支③**：非多视图、非特定 mip，但指定了 `layer ≥ 1`（如渲染到立方体贴图的某个面）。使用 `layerImageViews[layer]`，仅覆盖 mip0、单层。

- **默认**：`mipLevel = 0 && layer = 0 && 非多视图` → `imageViewBase` 即可满足，无需额外视图。

---

## 7. 参考代码

| 文件 | 说明 |
|------|------|
| `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.h` | 类声明 |
| `submodules/LumeRender/src/vulkan/node_context_pool_manager_vk.cpp` | 实现 |
| `submodules/LumeRender/src/vulkan/render_pass_creator_vk.h/cpp` | 渲染通道创建委托 |
| `submodules/LumeRender/src/gles/node_context_pool_manager_gles.h/cpp` | GLES 对应实现 |
| `submodules/LumeRender/src/vulkan/render_backend_vk.cpp` | 主消费者 |
