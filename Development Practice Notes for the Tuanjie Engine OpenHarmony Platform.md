# Development Practice Notes for the Unity Engine OpenHarmony Platform

### 1. Shader 变体剥离与丢失 (Stripping & Variant Loss)

在移动端 `Vulkan` 模式下，Shader 变体（Variant）的丢失会导致渲染错误或“直接回退到默认 *Lit*”。

-   **面板操作：显式包含 Shader**
    
    -   路径：`Edit > Project Settings > Graphics > Always Included Shaders`。
        
    -   **操作**：将脚本中通过 `Shader.Find` 调用的所有 Shader（如 `Skybox/Procedural`）手动拖入列表。
        
-   **进阶工具：Shader Variant Collection (SVC)**
    
    -   **作用**：精确记录 `multi_compile` 或 `shader_feature` 定义的组合。
        
    -   **脚本预热示例**：
        
-   **注意**：不要为了省事彻底关闭 Stripping（在 `Graphics Settings` 中设置 `Shader Precision Model` 为 `Full`），这会导致鸿蒙 App 的包体大小和加载内存激增。













1. 使用脚本在运行时切换shader时应注意最终编译打包成应用的时候引擎可能会优化掉在编译时未使用到的shader/ shader variant
解决方案：1. 显示设置某些shader不被优化掉 2 . 关闭引擎的stripping
2. 需要注意引擎在编辑器内运行时和在打包应用内运行时的区别
	- 什么时候使用Destroy，什么时候使用DestroyImmediate
	- OnValidate 的作用，打包时要注意什么，什么函数不能再OnValidate中执行
3. 编译调试时经常遇到的问题
4. 什么时候使用引用 什么时候使用实例化
5. 当打包引用中的渲染结果与编辑器内运行时或Windows平台应用不一致时应注意是否是不同平台上的quality settings有差异
6. 
<!--stackedit_data:
eyJoaXN0b3J5IjpbMjExNzIxMDMwMF19
-->