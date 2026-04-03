# Development Practice Notes for the Unity Engine OpenHarmony Platform

### 1. Shader Stripping & Variant Loss
The "Pink Screen" (Error Shader) on OpenHarmony devices occurs when the Vulkan driver fails to find the corresponding pre-compiled shader binary variant.
-   **Always Included Shaders (Panel)**:
    -   **Path**: `Edit > Project Settings > Graphics > Always Included Shaders`.
    -   **Action**: Manually add Shaders that are loaded via script (e.g., `Shader.Find`) and lack static material references in any scene.
    -   **Trade-off**: This includes **all** variants of the shader, which can significantly bloat the build size if not used sparingly.
-   **Shader Variant Collections (SVC) - Professional Workflow**:
    -   **Auto-Capture**: Run the game in the Editor, go through all core features, then go to `Edit > Project Settings > Graphics > Shader Loading` and click **`Save to asset`**.
    -   **Preloading**: Add the SVC asset to the `Preloaded Shaders` list in `Edit > Project Settings > Graphics > Shader Loading`.
    -   **Warmup Script**:
		```csharp
		public ShaderVariantCollection myCollection;
		void Start() {
		    if (!myCollection.isWarmedUp) {
		        myCollection.WarmUp(); // 运行时提前编译，防止切换时卡顿
		    }
		}
		```

### 2. Editor vs. Runtime Behavior Differences 
This is the #1 cause of the "Works in Editor, Crashes on Mobile" issue. 

#### Destroy() vs DestroyImmediate() 
| Function | Use Case | Behavior | 
|----------|----------|----------| 
| `Destroy()` | Play Mode (Playing) | **Asynchronous**. Cleans up uniformly at the end of the current frame, safe and does not invalidate references. | 
| `DestroyImmediate()` | Edit Mode (Edit Mode) | **Synchronous**. Immediately removes the object from memory. **Mandatory** in non-playing Editor state; otherwise, Unity will throw errors for uncleaned objects. |

#### **Example Script**:
```csharp
private void OnDestroy()
	if (material!= null)
	{
	    if (Application.isEditor && !Application.isPlaying)
	    {
	        DestroyImmediate(material);
	    }
	    else
	    {
	        Destroy(material);
	    }
	    material= null;
	    Debug.Log("material has been destroyed!");
	}
}
```

#### OnValidate()
OnValidate() is triggered when values in the Inspector are modified or the script is loaded. 

#### Prohibited Operations - Instantiate - Destroy - AddComponent - SendMessage - Any operations that may disrupt the Undo system ### Packaging Notes It is an **editor-only message** and is excluded from builds. If logic (e.g., calculating critical values) is placed inside, the value may remain at the default **0** after build. ### Safe Implementation Wrap code with `#if UNITY_EDITOR` and use `EditorApplication.delayCall` to execute complex UI or resource operations.


1. 使用脚本在运行时切换shader时应注意最终编译打包成应用的时候引擎可能会优化掉在编译时未使用到的shader/ shader variant
解决方案：1. 显示设置某些shader不被优化掉 2 . 关闭引擎的stripping
2. 需要注意引擎在编辑器内运行时和在打包应用内运行时的区别
	- 什么时候使用Destroy，什么时候使用DestroyImmediate
	- OnValidate 的作用，打包时要注意什么，什么函数不能再OnValidate中执行
3. 编译调试时经常遇到的问题
4. 什么时候使用引用 什么时候使用实例化
5. 当打包引用中的渲染结果与编辑器内运行时或Windows平台应用不一致时应注意是否是不同平台上的quality settings有差异
6. 
<!--stackedit_data:
eyJoaXN0b3J5IjpbNjA0NzUyMzE5LDExOTg1OTg2NzQsMjExNz
IxMDMwMF19
-->