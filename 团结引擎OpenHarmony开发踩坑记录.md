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
	- [**Cause**]
		- 虽然调用了 `DynamicGI.UpdateEnvironment()` 但是没有触发全局光照的更新
	- [**Solution**]
		- 在修改天空盒材质的时候先修改 `ambientMode` 为纯色，再改回天空盒
		- 本质上是手动触发了 Unity 内部渲染状态的 **Dirty Flag**，

```csharp
private void ApplySkyboxToScene()
{
    if (skybox != null)
    {
        // 1. 设置天空盒材质
        RenderSettings.skybox = skybox;

        // 2. 先强制指定环境光来源为纯色，然后再重新设置为天空盒
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
eyJoaXN0b3J5IjpbMTI4NjQzNTMxNywxMDYzMDMyMzM4LC04Nj
Q4NzQxMTEsMjEwNjc1MDIyNSwtMTczODg0NjZdfQ==
-->