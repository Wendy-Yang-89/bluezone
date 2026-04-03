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
4. 
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTE5NjkyNDc2MTQsLTg2NDg3NDExMSwyMT
A2NzUwMjI1LC0xNzM4ODQ2Nl19
-->