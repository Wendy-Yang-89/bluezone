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
3. 渲染管线设置优先级
	# 渲染管线优先级与覆盖规则 | 优先级 | 设置项 | API | 作用 | 最终生效规则 | | :--- | :--- | :--- | :--- | :--- | | **1（最高）** | Quality Settings 质量等级渲染管线 | `QualitySettings.renderPipeline` | 当前画质等级的**覆盖管线** | 不为空 → 优先使用此覆盖管线 | | **2** | Graphics Settings 默认渲染管线 | `GraphicsSettings.defaultRenderPipeline` | 全局默认管线 | 覆盖为空 → 使用此默认管线 | | **3（最低）** | 内置渲染管线 | - | 系统兜底 | 前两者均为空 → 自动使用 Built-in 管线 | | 最终获取 | 当前活动渲染管线 | `GraphicsSettings.currentRenderPipeline` | 直接返回**最终生效**的管线资产 | 自动按优先级返回结果，无需判断 |
<!--stackedit_data:
eyJoaXN0b3J5IjpbNDI0NTY0NzYzLC04NjQ4NzQxMTEsMjEwNj
c1MDIyNSwtMTczODg0NjZdfQ==
-->