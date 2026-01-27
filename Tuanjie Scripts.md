# Tuanjie Scripts 
###### Based on Tuanjie 1.8.0

### 创建脚本
https://docs.unity.cn/cn/tuanjiemanual/Manual/CreatingAndUsingScripts.html
1. 脚本名$==$类名时才可以将脚本附加到GameObject
2. 不要为脚本组件定义构造函数，使用`Start()`进行初始化

### 编辑自定义变量
https://docs.unity.cn/cn/tuanjiemanual/Manual/VariablesAndTheInspector.html
1. Inspector面板展示的变量名称遵循特定的命名规则， 不一定和脚本中的变量名称完全一致
2. 将变量定义为`public`或使用[SerializeField](https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/SerializeField.html)在Inspector面板中查看并编辑变量
3. 使用[HideInInspector](https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/HideInInspector.html)在Inspector面板中隐藏变量

### 使用脚本实例化Prefab
https://docs.unity.cn/cn/tuanjiemanual/Manual/InstantiatingPrefabs.html

### 事件函数
![输入图片说明](/imgs/2026-01-26/BDrP6Dixnx80haJj.png)![事件函数执行流程图](https://docs.unity.cn/cn/tuanjiemanual/uploads/Main/monobehaviour_flowchart.svg)
- `Awake`: GameObject被激活且预制件实例化之后执行，在脚本生命周期中仅调用一次
- `OnEnable`: 启用对象之后/实例化`MonoBehaviour`之后立即调用
- `Reset`: 脚本首次附加到GameObject或者在Inspector面板中执行`reset`操作时调用
- `OnValidate`: 设置脚本自定义变量属性/反序列化时调用
- `Start`: 启用脚本实例时，在第一次调用`Update`函数之前调用，在脚本生命周期中仅调用一次
- `FixedUpdate`: 以独立于帧率的频率进行更新，用于物理系统的计算，更新间隔为[`Time.fixedDeltaTime`](https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/Time-fixedDeltaTime.html)
- `Update`: 帧回调函数，用于每帧更新
- `LateUpdate`: 在`Update`完成之后开始执行，用于
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTE5ODMyOTI0NzksODk3NjE5MzYwLDE2MT
Y4MDExNiwtMTU3MDAxMzE5OCwxOTYxNTA0NDY4LDE0OTEzOTIw
NDgsLTE5ODA1NTk3MDEsMjAxOTQxMDM2Myw3MzA2MTQyNiwtMT
g0NDU5ODAxNywtNzc3MDQ0NjcwXX0=
-->