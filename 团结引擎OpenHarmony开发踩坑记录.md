# 团结引擎OpenHarmony开发踩坑记录

1. 打包成应用后切换材质/shader后效果错误，可能是没有在脚本中保留对shader的引用，引擎无法追踪到这个shader会被使用，打包过程中该shader被剔除
2. 添加了很多附加光源但是在打包应用中只有主光源，无附加光源渲染贡献
	- 在 `Edit > Project Settings > Quality` 中确认打包目标平台的渲染质量等级
		- 有对勾说明该平台支持对应渲染质量等级
		- 绿色对勾对应该平台默认使用的渲染质量等级
	- 在资源浏览器 `Project > Assets > Settings` 下面找到对应的URP资产和Renderer资产
		- `Perfomant`: URP-Perfomant.asset  URP-Perfomant-Renderer.asset
		- `Balanced`: URP-Balanced.asset URP-Balanced-Renderer.asset
		- `High Fidelity`: URP-HighFidelity.asset  URP-HighFidelity-Renderer.asset
<!--stackedit_data:
eyJoaXN0b3J5IjpbMjEwNjc1MDIyNSwtMTczODg0NjZdfQ==
-->