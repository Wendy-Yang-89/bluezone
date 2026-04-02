# Development Practice Notes for the Unity Engine OpenHarmony Platform

1. 使用脚本在运行时切换shader时应注意最终编译打包成应用的时候引擎可能会优化掉在编译时未使用到的shader/ shader variant
解决方案：1. 显示设置某些shader不被优化掉 2 . 关闭引擎的stripping
2. 需要注意引擎在编辑器内运行时和在打包应用内运行时的区别
	- 什么时候使用Destroy，什么时候使用DestroyImmediate
	- OnValidate 的作用，打包时要注意什么，什么函数不能再OnValidate中执行
3. 编译调试时经常遇到的问题
4. 什么时候使用引用 什么时候使用实例化
5. 当打包引用中的渲染结果与编辑器内运行时或Windowsping
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTEyODMwMTk0OF19
-->