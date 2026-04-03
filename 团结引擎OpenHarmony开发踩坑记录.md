# 团结引擎OpenHarmony开发踩坑记录

1. 打包成应用后切换材质/shader后效果错误，可能是没有在脚本中保留对shader的引用，引擎无法追踪到这个shader会被使用，打包过程中该shader被剔除
2. 添加了很多附加光源但是在打包应用中只有主光源，无附加光源渲染贡献，
<!--stackedit_data:
eyJoaXN0b3J5IjpbNjY0NTM5MjMsLTE3Mzg4NDY2XX0=
-->