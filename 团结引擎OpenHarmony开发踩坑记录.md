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

```csharp
private void ApplySkyboxToScene()
{
    if (skybox != null)
    {
        // 1. 设置天空盒材质
        RenderSettings.skybox = skybox;

        // 2. 先强制指定环境光来源为天空盒 (这一步至关重要)
        RenderSettings.ambientMode = AmbientMode.Flat;
        RenderSettings.ambientMode = AmbientMode.Skybox;

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
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTEwNDcxOTI1MzQsMTA2MzAzMjMzOCwtOD
Y0ODc0MTExLDIxMDY3NTAyMjUsLTE3Mzg4NDY2XX0=
-->