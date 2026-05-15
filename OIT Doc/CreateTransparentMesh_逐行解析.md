# CreateTransparentMesh 函数逐行解析

## 函数概述
`CreateTransparentMesh()` 函数用于创建一个透明网格对象，该网格由多个层叠的平面组成，每层具有不同的颜色和旋转角度。

---

## 逐行解析

### 第1-4行：函数定义和常量声明
```cpp
void CreateTransparentMesh()
{
    constexpr Math::Vec3 SIZE(10.f, 10.f, 10.f);
    constexpr Math::UVec3 DIM(100, 100, 10);
    constexpr Math::Vec4 COLORS[] { { 0.f, 0.f, 0.25f, 0.25f }, { 0.25f, 0.25f, 0.f, 0.25f }, { 0.25f, 0.f, 0.f, 0.25f }, { 0.75f, 0.75f, 0.75f, 1.f } };
```

- **第1行**：定义函数 `CreateTransparentMesh`，无参数，无返回值
- **第2行**：定义常量 `SIZE`，表示网格在三个维度上的尺寸，均为10.0单位
- **第3行**：定义常量 `DIM`，表示网格在三个维度上的分段数：
  - X方向：100段
  - Y方向：100段
  - Z方向：10层
- **第4行**：定义颜色数组 `COLORS`，包含4种颜色（RGBA格式）：
  - 深蓝色半透明 (0, 0, 0.25, 0.25)
  - 黄绿色半透明 (0.25, 0.25, 0, 0.25)
  - 深红色半透明 (0.25, 0, 0, 0.25)
  - 浅灰色不透明 (0.75, 0.75, 0.75, 1)

### 第6行：类型别名定义
```cpp
using DimType = std::remove_cv_t<std::remove_reference_t<decltype(DIM.data[0])>>;
```
- 定义类型别名 `DimType`，通过类型推导获取 `DIM.data[0]` 的类型
- `remove_reference_t` 移除引用类型
- `remove_cv_t` 移除const和volatile修饰符
- 结果为 `uint32_t` 类型，用于循环索引

### 第8-13行：创建MeshBuilder实例
```cpp
auto meshBuilder = CreateInstance<IMeshBuilder>(*renderContext_, UID_MESH_BUILDER);
if (!meshBuilder) {
    CORE_LOG_E("Cannot create MeshBuilder");
    return;
}
```
- **第8行**：调用 `CreateInstance` 创建 `IMeshBuilder` 接口实例
  - 传入渲染上下文 `renderContext_` 和唯一标识符 `UID_MESH_BUILDER`
- **第9-12行**：检查创建是否成功
  - 如果失败，记录错误日志并提前返回

### 第15-35行：定义toDataBuffer Lambda函数
```cpp
auto toDataBuffer = [](const auto& vec) -> IMeshBuilder::DataBuffer {
    using ValueType = typename std::remove_reference_t<decltype(vec)>::value_type;

    Format fmt = [&]() {
        if constexpr (std::is_same_v<ValueType, Math::Vec4>) {
            return Format::BASE_FORMAT_R32G32B32A32_SFLOAT;
        }
        if constexpr (std::is_same_v<ValueType, Math::Vec3>) {
            return Format::BASE_FORMAT_R32G32B32_SFLOAT;
        }
        if constexpr (std::is_same_v<ValueType, Math::Vec2>) {
            return Format::BASE_FORMAT_R32G32_SFLOAT;
        }
        if constexpr (std::is_same_v<ValueType, uint32_t>) {
            return Format::BASE_FORMAT_R32_UINT;
        }
        if constexpr (std::is_same_v<ValueType, uint16_t>) {
            return Format::BASE_FORMAT_R16_UINT;
        }
        return Format::BASE_FORMAT_UNDEFINED;
    }();

    return IMeshesBuilder::DataBuffer { fmt, sizeof(ValueType),
        { reinterpret_cast<const uint8_t*>(vec.data()), vec.size() * sizeof(ValueType) } };
};
```

- **第15行**：定义lambda函数 `toDataBuffer`，接受一个vector引用，返回 `IMeshBuilder::DataBuffer`
- **第16行**：推导vector的值类型 `ValueType`
- **第18-30行**：使用立即lambda根据 `ValueType` 确定数据格式：
  - `Math::Vec4` → RGBA 32位浮点格式
  - `Math::Vec3` → RGB 32位浮点格式
  - `Math::Vec2` → RG 32位浮点格式
  - `uint32_t` → 32位无符号整数格式
  - `uint16_t` → 16位无符号整数格式
- **第33-35行**：构造并返回 `DataBuffer` 结构体：
  - 格式类型
  - 值类型大小
  - 数据指针和总大小（转换为字节指针）

### 第37-52行：生成基础位置和法线数据
```cpp
vector<Math::Vec3> basedPositions;
vector<Math::Vec3> normals;
{
    basedPositions.reserve(static_cast<size_t>(DIM.y + 1) * (DIM.x + 1));
    normals.reserve(static_cast<size_t>(DIM.y + 1) * (DIM.x + 1));

    Math::Vec3 pos(0.f, 0.f, 0.f);
    for (DimType y = 0; y <= DIM.y; ++y) {
        pos.y = SIZE.y * y / DIM.y - .5f * SIZE.y;
        for (DimType x = 0; x <= DIM.x; ++x) {
            pos.x = SIZE.x * x / DIM.x - .5f * SIZE.x;
            basedPositions.push_back(pos);

            if (normals.size() < basedPositions.size()) {
                normals.push_back(Math::Vec3(0.f, 0.f, 1.f));
            }
        }
    }
}
```

- **第37-38行**：声明位置和法线vector
- **第40-41行**：预分配内存空间：
  - (100+1) × (100+1) = 10201个顶点
- **第43行**：初始化位置向量
- **第44行**：外层循环遍历Y方向（0到100，共101行）
- **第45行**：计算Y坐标：
  - `SIZE.y * y / DIM.y`：从0到10线性插值
  - `- .5f * SIZE.y`：居中偏移，范围变为[-5, 5]
- **第46行**：内层循环遍历X方向（0到100，共101列）
- **第47行**：计算X坐标，同样居中偏移到[-5, 5]
- **第48行**：将位置添加到basedPositions
- **第50-51行**：确保法线数量与位置数量一致，添加Z轴正向法线(0,0,1)

### 第54-70行：生成索引数据
```cpp
vector<uint16_t> indices;
{
    indices.reserve(static_cast<size_t>(DIM.y) * DIM.x * 6);

    for (DimType y = 0; y < DIM.y; ++y) {
        for (DimType x = 0; x < DIM.x; ++x) {
            const uint16_t i0 = static_cast<uint16_t>(y * (DIM.x + 1) + x);
            const uint16_t i1 = static_cast<uint16_t>(i0 + 1);
            const uint16_t i2 = static_cast<uint16_t>(i0 + (DIM.x + 1));
            const uint16_t i3 = static_cast<uint16_t>(i2 + 1);
            indices.push_back(i0);
            indices.push_back(i2);
            indices.push_back(i1);
            indices.push_back(i1);
            indices.push_back(i2);
            indices.push_back(i3);
        }
    }
}
```

- **第54行**：声明索引vector
- **第56行**：预分配内存：
  - 100 × 100 × 6 = 60000个索引（每个网格单元2个三角形，每个三角形3个顶点）
- **第58行**：外层循环遍历Y方向（0到99）
- **第59行**：内层循环遍历X方向（0到99）
- **第61-64行**：计算当前网格单元的4个顶点索引：
  - `i0`：左下角顶点
  - `i1`：右下角顶点（i0 + 1）
  - `i2`：左上角顶点（下一行）
  - `i3`：右上角顶点
- **第66-71行**：添加两个三角形的索引（逆时针绕序）：
  - 第一个三角形：i0 → i2 → i1
  - 第二个三角形：i1 → i2 → i3

### 第73-84行：定义generateSingleColorMaterial Lambda函数
```cpp
auto generateSingleColorMaterial = [&](Math::Vec4 color) {
    auto matMgr = GetManager<IMaterialComponentManager>(*ecs_);
    Entity matEntt = ecs_->GetEntityManager().Create();
    matMgr->Create(matEntt);
    if (auto matHandle = matMgr->Write(matEntt); matHandle) {
        matHandle->textures[MaterialComponent::TextureIndex::BASE_COLOR].factor = color;
    }

    return matEntt;
};
```

- **第73行**：定义lambda函数，接受颜色参数，返回实体ID
- **第74行**：获取材质组件管理器
- **第75行**：创建新实体
- **第76行**：为实体创建材质组件
- **第77-79行**：获取材质写入句柄并设置基础颜色因子
- **第81行**：返回材质实体ID

### 第86-100行：初始化MeshBuilder
```cpp
{
    auto& shaderMgr = renderContext_->GetDevice().GetShaderManager();
    const VertexInputDeclarationView vid =
        shaderMgr.GetVertexInputDeclarationView(shaderMgr.GetVertexInputDeclarationHandle(
            DefaultMaterialShaderConstants::VERTEX_INPUT_DECLARATION_FORWARD));
    meshBuilder->Initialize({ vid, static_cast<size_t>(DIM.z) });

    IMeshBuilder::Submesh submesh;
    for (DimType z = 0; z < DIM.z; ++z) {
       子网格.vertexCount = basedPositions.size();
        submesh.indexCount = indices.size();
        submesh.material = generateSingleColorMaterial(COLORS[z % 2]);
        meshBuilder->AddSubmesh(submesh);
    }

    meshBuilder->Allocate();
}
```

- **第87行**：获取着色器管理器引用
- **第88-90行**：获取前向渲染的顶点输入声明视图
- **第91行**：初始化MeshBuilder，传入顶点布局和子网格数量（10层）
- **第93行**：声明子网格结构体
- **第94行**：循环遍历Z方向（0到9）
- **第95-96行**：设置子网格的顶点和索引数量
- **第97行**：根据Z索引选择颜色（交替使用COLORS[0]和COLORS[1]）
- **第98行**：添加子网格到MeshBuilder
- **第100行**：分配网格数据内存

### 第102-108行：定义rotatePositions Lambda函数
```cpp
auto rotatePositions = [&](float rad, vector<Math::Vec3>& positions) {
    for (size_t idx = 0; idx < positions.size(); ++idx) {
        Math::Vec4 src(basedPositions[idx], 1.f);
        Math::Quat quat = Math::Euler(0.f, rad, 0.f);
        positions[idx] = quat * src;
    }
};
```

- **第102行**：定义lambda函数，接受旋转角度和位置vector引用
- **第103行**：遍历所有位置
- **第104行**：将3D位置转换为4D齐次坐标（w=1）
- **第105行**：创建绕Y轴旋转的四元数（欧拉角：pitch=0, yaw=rad, roll=0）
- **第106行**：应用旋转变换并存储结果

### 第110-114行：设置每层网格数据
```cpp
for (DimType z = 0; z < DIM.z; ++z) {
    auto positions = basedPositions;
    rotatePositions(180.f * z / DIM.z, positions);

    meshBuilder->SetIndexData(z, toDataBuffer(indices));
    meshBuilder->SetVertexData(z, toDataBuffer(positions), toDataBuffer(normals), {}, {}, {}, {});
    meshBuilder->CalculateAABB(z, toDataBuffer(positions));
}
```

- **第110行**：循环遍历Z方向（0到9）
- **第111行**：复制基础位置数据
- **第112行**：计算旋转角度：
  - z=0: 0°
  - z=1: 18°
  - z=2: 36°
  - ...
  - z=9: 162°
- **第113行**：设置索引数据（所有层共享相同索引）
- **第114行**：设置顶点数据：
  - 位置
  - 法线
  - 空的切线、副法线、纹理坐标、颜色
- **第115行**：计算并设置轴对齐包围盒（AABB）

### 第117-118行：创建网格实体和节点
```cpp
auto meshEntt = meshBuilder->CreateMesh(*ecs_);
auto meshNode = graphicsContext_->GetMeshUtil().GenerateEntity(*ecs_, "Translucent Mesh Node", meshEntt);
```

- **第117行**：从MeshBuilder创建网格实体
- **第118行**：生成网格节点实体，命名为"Translucent Mesh Node"

---

## 数据结构总结

### 顶点网格
- **顶点总数**：(100+1) × (100+1) = 10,201个顶点
- **网格单元数**：100 × 100 = 10,000个四边形
- **三角形数**：20,000个
- **索引数**：60,000个

### 层级结构
- **总层数**：10层
- **每层旋转**：绕Y轴旋转，角度从0°到162°，步进18°
- **颜色交替**：偶数层使用深蓝色，奇数层使用黄绿色

### 内存布局
- 所有层共享相同的索引和法线数据
- 每层有独立的位置数据（经过旋转变换）
- 每层有独立的材质实体

---

## 函数流程图

```
开始
  ↓
定义常量（SIZE, DIM, COLORS）
  ↓
创建MeshBuilder实例
  ↓
定义toDataBuffer转换函数
  ↓
生成基础顶点位置和法线
  ↓
生成三角形索引
  ↓
定义材质生成函数
  ↓
初始化MeshBuilder并添加子网格
  ↓
定义位置旋转函数
  ↓
循环10层：
  ├─ 复制基础位置
  ├─ 应用Y轴旋转
  ├─ 设置索引数据
 ├─ 设置顶点数据
  └─ 计算AABB
  ↓
创建网格实体
  ↓
创建网格节点
  ↓
结束
```

---

## 关键技术点

1. **constexpr常量**：编译期常量，提高性能
2. **类型推导**：使用decltype和type_traits自动推导类型
3. **Lambda表达式**：用于数据转换和材质生成
4. **四元数旋转**：使用四元数实现3D旋转变换
5. **网格构建器模式**：通过IMeshBuilder接口构建复杂网格
6. **子网格系统**：支持一个网格包含多个子网格，每层一个子网格
7. **内存预分配**：使用reserve避免vector重新分配
8. **齐次坐标**：使用Vec4表示3D点，便于矩阵变换

---

## 生成的视觉效果

该函数创建了一个由10层透明平面组成的结构：
- 每层是一个100×100的网格平面
- 每层绕Y轴旋转不同角度，形成扇形展开效果
- 偶数层和奇数层使用不同的半透明颜色
- 整体呈现为一个半透明的旋转体结构
