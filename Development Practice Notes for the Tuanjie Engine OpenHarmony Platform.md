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

##### **Example Script**:
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

##### Prohibited Operations 
- Instantiate 
- Destroy 
- AddComponent 
- SendMessage 
- Any operations that may disrupt the **Undo** system 
- **Do not** call `EditorUtility.SetDirty` inside OnValidate() or modify properties that may trigger re-serialization, as this will cause an infinite loop.

##### Packaging Notes 
It is an **editor-only message** and is excluded from builds. If logic (e.g., calculating critical values) is placed inside, the value may remain at the default **0** after build. 

##### Safe Implementation 
Wrap code with `#if UNITY_EDITOR` and use `EditorApplication.delayCall` to execute complex UI or resource operations.

### 3. Reference vs. Instantiation 

#### Reference (SharedMaterial) 
- Behavior: Points directly to the asset files on disk. 
- Risk: If you modify `renderer.sharedMaterial.color` in a script, it **permanently alters your project files**! The changes will persist even after exiting `Play Mode`. 

#### Instantiation (Material) 
- Behavior: When accessing `renderer.material` (without `shared`), Unity creates a new copy of the material in memory. 
- Risk: **Memory leak**. A new copy is generated on each access. If you do not manually `Destroy` it in `OnDestroy`, video memory will gradually be exhausted.

### 5. Quality Settings 与平台差异

在鸿蒙平台上，渲染表现不一致通常检查这三个地方：

-   **URP Asset 覆盖**：在 `Quality Settings` 中，每个等级（Low/Med/High）可以指定不同的 `URP Asset`。检查你的 OH 平台等级是否关联了正确的 Asset。
    
-   **Shadow Distance**：移动端默认阴影距离通常很短（如 20-50），如果你的场景很大，远处看就是黑的，这常被误认为光照坏了。
    
-   **Color Space**：确保 OH 平台和 PC 平台统一使用 **Linear（线性色空间）**。如果一个是 Gamma 一个是 Linear，画面亮度会差出好几倍。
<!--stackedit_data:
eyJoaXN0b3J5IjpbMTc4MDAwODc3MCwyMDQ1NDMzMzgwLDExOT
g1OTg2NzQsMjExNzIxMDMwMF19
-->