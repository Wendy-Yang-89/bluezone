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
- Intialization
	- `Awake`: GameObject被激活且预制件实例化之后执行，在脚本生命周期中仅调用一次
	- `OnEnable`: 启用对象之后/实例化`MonoBehaviour`之后立即调用
	- `Reset`: 脚本首次附加到GameObject或者在Inspector面板中执行`reset`操作时调用
	- `OnValidate`: 设置脚本自定义变量属性/反序列化时调用
	- `Start`: 启用脚本实例时，在第一次调用`Update`函数之前调用，在脚本生命周期中仅调用一次
- Per-Frame Update
	- `FixedUpdate`: 以独立于帧率的频率进行更新，用于物理系统的计算，更新间隔为[`Time.fixedDeltaTime`](https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/Time-fixedDeltaTime.html)
	- `Update`: 帧回调函数，用于每帧更新
	- `LateUpdate`: 在`Update`完成之后开始执行，用于跟随第三人称摄像机的更新
- Built-In Rendering Pipeline
	- `OnPreCull`：在摄像机剔除场景之前调用。剔除操作将确定摄像机可以看到哪些对象。正好在进行剔除之前调用 OnPreCull。
	-  `OnBecameVisible`/`OnBecameInvisible`：对象变为对任何摄像机可见/不可见时调用。
	-  `OnWillRenderObject`：如果对象可见，则为每个摄像机调用**一次**。
	-   `OnPreRender`：在摄像机开始渲染场景之前调用。
	-  `OnRenderObject`：所有常规场景渲染完成之后调用。此时，可以使用 [GL](https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/GL.html) 类或 [Graphics.DrawMeshNow](https://docs.unity.cn/cn/tuanjiemanual/ScriptReference/Graphics.DrawMeshNow.html) 来绘制自定义几何形状。
	-  `OnPostRender`：在摄像机完成场景渲染后调用。
	-   `OnRenderImage`：在场景渲染完成后调用以允许对图像进行后处理，请参阅[后期处理效果](https://docs.unity.cn/cn/tuanjiemanual/Manual/PostProcessingOverview.html)。
	-   `OnGUI`：每帧调用多次以响应 GUI 事件。首先处理布局和重新绘制事件，然后为每个输入事件处理布局和键盘/鼠标事件。
	-   `OnDrawGizmos` : 用于在场景视图中绘制辅助图标以实现可视化。
- Co-Routine
	-	Update 函数返回后将运行正常协程更新。协程是一个可暂停执行 (yield) 直到给定的 YieldInstruction 达到完成状态的函数。 协程的不同用法：

-   *yield** 在下一帧上调用所有 Update 函数后，协程将继续。
-   **yield WaitForSeconds** 在为帧调用所有 Update 函数后，在指定的时间延迟后继续。
-   **yield WaitForFixedUpdate** 在所有脚本上调用所有 FixedUpdate 后继续。如果协同程序在 FixedUpdate 之前生成，那么它会在当前帧的 FixedUpdate 之后继续运行。
-   **yield WWW** 在 WWW 下载完成后继续。
-   **yield StartCoroutine** 将协程链接起来，并会等待 MyFunc 协程先完成。

1. 同一`MonoBehaviour`子类不同实例之间调用事件函数的顺序不能指定
2. 不同`MonoBehaviour`子类实例之间调用事件函数的顺序可以通过`Project Settings > Script Execution Order`指定

<!--stackedit_data:
eyJoaXN0b3J5IjpbMTA2OTM3NTY2NSwtMzIyMjY2MjQyLC0xMD
QwNjU1NjcyLDg5NzYxOTM2MCwxNjE2ODAxMTYsLTE1NzAwMTMx
OTgsMTk2MTUwNDQ2OCwxNDkxMzkyMDQ4LC0xOTgwNTU5NzAxLD
IwMTk0MTAzNjMsNzMwNjE0MjYsLTE4NDQ1OTgwMTcsLTc3NzA0
NDY3MF19
-->