# Generate Cubemaps for Unity Projects on OpenHarmony

1. Download hdr environment texture
	- https://polyhaven.com/a/belfast_sunset_puresky
2. Place it under `${UNITY_PROJ_NAME}/Assets/Resources/Textures`
3. Copy the original hdr texture and edit its property in the Inspector
	- Change the `Texture Shape` from `2D` to `Cube`
	- Override the settings for **OpenHarmony** platform as below
		![为OpenHarmony平台设置纹理属性](/imgs/2026-03-20/7iGFCGYIaGhrnTqU.png)
4. Generate 6 seperate environment maps
	- tool: *cmftStudio* ([https://github.com/dariomanesku/cmftStudio/releases](https://github.com/dariomanesku/cmftStudio/releases))
	-  steps-by-step：
		- Select `Environment` tab on the right panel
		- Click `Edit`
		- Click `Skybox > Browse` for loading textures to be transferred
		- Click `Skybox > Save` 
		- Select `.hdr` for `File Type` and `Facelist` for `Output Type`
    -  	右侧面板选中`Environment`标签页→点击`Edit`→`Skybox`→`Browse`→ 选择输入天空盒纹理。
    -   点击 `Save` 根据选定格式导出天空盒纹理。
    -   优势：自动处理坐标转换，无需担心天空盒颠倒问题。
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTExNDk3NzMwNSwtMTA2MzE0ODcxNV19
-->