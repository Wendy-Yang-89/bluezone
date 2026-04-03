# 团结引擎OpenHarmony开发踩坑记录

 1. 打包成应用后切换材质/shader后效果错误，可能是没有在脚本中保留对shader的引用，引擎无法追踪到这个shader会被使用，打包过程中该shader被剔除
 2. 添加了很多附加光源但是在打包应用中只有主光源，无附加光源渲染贡献
	- 在 `Edit > Project Settings > Quality` 中确认打包目标平台的渲染质量等级
		- 有对勾说明该平台支持对应渲染质量等级
		- 绿色对勾对应该平台默认使用的渲染质量等级
	- 在资源浏览器 `Project > Assets > Settings` 下面找到对应的URP资产和Renderer资产

		| 质量级别 | URP 资产文件 | Renderer 渲染器资产文件 |
		|---------|-------------|------------------------| 
		| `Perfomant` | URP-Perfomant.asset | URP-Perfomant-Renderer.asset | 
		| `Balanced` | URP-Balanced.asset | URP-Balanced-Renderer.asset | 
		| `High Fidelity` | URP-HighFidelity.asset | URP-HighFidelity-Renderer.asset |
 3. 渲染管线优先级与覆盖规则
	Unity手册：https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/Rendering.GraphicsSettings-currentRenderPipeline.html
	- **优先级 1（最高）**：`QualitySettings.renderPipeline` 对应当前质量等级设置的渲染管线资产，会覆盖默认设置。 
	- **优先级 2**：`GraphicsSettings.defaultRenderPipeline` 全局默认渲染管线，当质量设置未指定时生效。 
	- **优先级 3（最低）**：内置渲染管线 Built-in Render Pipeline 当以上两项均未设置时，Unity 自动使用内置管线。 
	- **最终生效结果**：`GraphicsSettings.currentRenderPipeline` 由 Unity 自动按上述优先级计算，返回当前实际使用的渲染管线。
 4. 全局光照同步问题
	- [**BUG**] 在脚本中动态加载或移除天空盒的代码 `SkyboxManager.cs` 中存在光照信息丢失问题。
	- [**Reproduction**]
		- Step1: 点击 `Create & Apply` 在运行时动态创建天空盒材质并且应用到场景中
		- Step2: 点击 `Remove Skybox` 在运行时销毁天空盒材质并且设置 `RenderSettings.skybox = null` 
		- Step3: 第二次 点击 `Create & Apply` 之后加载出来的模型确实光照信息，渲染结果为全黑色
	- 

这是一个非常经典且让人头疼的 **环境光照同步（GI Sync）** 问题。
模型变黑是因为你的代码在“移除”和“重新加载”的过程中，弄丢了场景的**环境光数据（Ambient Lighting）**。

在 Unity/团结引擎中，物体的亮度由 **直接光** 和 **环境光（Indirect/Ambient Light）** 组成。当你执行 `RemoveSkybox` 时：

1.  你把 `RenderSettings.skybox` 设为了 `null`。
    
2.  你调用了 `DynamicGI.UpdateEnvironment()`。此时，Unity 会重新计算环境光。因为天空盒没了，计算出的环境光系数（Spherical Harmonics）全是 **0（黑色）**。
    
3.  **关键点**：当你第二次 `Apply` 时，虽然你把新材质给了 `RenderSettings.skybox`，但由于 **URP 渲染管线或烘焙系统的缓存机制**，环境光探测器（Ambient Probe）可能没有立即被告知“现在又有光了”。
    

结果就是：天空盒虽然显示出来了，但场景里的模型依然在使用上一刻计算出的“全黑”环境光数据，所以模型看起来是黑色的。

----------

### 解决方案：三步修复法

你需要修改 `ApplySkyboxToScene` 函数，强制 Unity 重新同步所有环境数据。

#### 1. 强制重置环境光模式

在赋值天空盒后，显式地告诉 Unity 使用天空盒作为环境光来源，并触发探针刷新。

C#

```
private void ApplySkyboxToScene()
{
    if (skybox != null)
    {
        // 1. 设置天空盒材质
        RenderSettings.skybox = skybox;

        // 2. 强制指定环境光来源为天空盒 (这一步至关重要)
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Skybox;

        // 3. 强制触发环境光和反射探针的全面更新
        // 在某些 Unity 版本中，仅仅 UpdateEnvironment 是不够的
        DynamicGI.UpdateEnvironment();
        
        // 如果是在编辑器环境下，有时需要额外标记场景已改变
        #if UNITY_EDITOR
        if (!Application.isPlaying)
        {
            EditorUtility.SetDirty(this);
            // 强制重绘场景视图以看到光照变化
            SceneView.RepaintAll();
        }
        #endif

        Debug.Log("天空盒已应用，环境光已强制同步。");
    }
}
```

#### 2. 解决材质被“误杀”的问题

在你的 `OnDestroy` 和 `RemoveSkybox` 里，你使用了 `DestroyImmediate(skybox)`。

-   如果你在第二次 Load 时，由于某种逻辑逻辑判定（比如 `if (skybox == null)`），没有正确地重新 `new Material`，那么你其实是在给 `RenderSettings.skybox` 赋值一个**已经销毁的 Null 引用**。
    
-   建议在 `UpdateSkyboxMaterial` 的开头加入更严谨的检查：
    

C#

```
private void UpdateSkyboxMaterial()
{
    // ... 之前的 Shader 判断逻辑 ...

    // 确保材质一定存在且有效
    if (skybox == null) 
    {
        skybox = new Material(skyboxShader);
        skybox.hideFlags = HideFlags.HideAndDontSave; // 防止被误删
    }
    else
    {
        skybox.shader = skyboxShader;
    }
    
    // ... 后续的属性同步 ...
}
```

#### 3. 检查 URP Asset 的环境设置

如果模型还是黑色，请检查你的 **URP Asset** 设置：

-   **Lighting > Environment**：确保没有勾选一些奇怪的优化项导致环境光不再自动更新。
    
-   **Vulkan 平台特殊性**：你在 OpenHarmony 上使用 Vulkan，Vulkan 的常量缓冲区更新可能存在延迟。如果 `DynamicGI.UpdateEnvironment()` 没生效，可以尝试在 `Apply` 后延迟一帧再调用一次 `DynamicGI.UpdateEnvironment()`。
    

----------

### 为什么第一次是好的？

第一次运行脚本时，场景的 **Lighting Data Asset**（光照贴图数据）通常还带有上一个天空盒残留的有效环境光信息。而当你手动 `Remove` 后，你把这个“有效信息”彻底刷成了“纯黑”，所以第二次加载就必须靠代码强行“唤醒”光照系统。

**小贴士**：如果你的模型使用了自定义 Shader，请确保 Shader 内部有 `_GLOSSY_ENV_REFLECTIONS` 宏或者正确处理了 `SH`（球面谐波）光照计算。否则，就算天空盒回来了，模型也可能因为拿不到环境光探针的数据而保持黑色。

**你现在重新 `Apply` 之后，场景里的 Directional Light（方向光）是否还能正常照亮模型？**（如果方向光能亮但阴影处全黑，那百分之百是 Ambient Probe 环境光探针没刷新）。
<!--stackedit_data:
eyJoaXN0b3J5IjpbMTA2MzAzMjMzOCwtODY0ODc0MTExLDIxMD
Y3NTAyMjUsLTE3Mzg4NDY2XX0=
-->