# Development Practice Notes for the Unity Engine OpenHarmony Platform

1. 使用脚本在运行时切换shader时应注意最终编译打包成应用的时候引擎可能会优化掉在编译时未使用到的shader/ shader variant
解决方案：1. 显示设置某些shader不被优化掉 2 . 关闭引擎的stripping
2. 
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTE5NzYwMjE5NV19
-->