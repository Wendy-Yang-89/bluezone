# Scripts for Auto Import TMP Essentials
1. 创建Editor脚本AutoImportTMPEssentials.cs
```csharp
using UnityEditor;
using TMPro;

public class AutoImportTMPEssentials : Editor
{
    [MenuItem("Tools/Auto Import TMP Essentials")]
    public static void ImportTMPEssentials()
    {
        // 直接导入TMP基础资源
        TMP_PackageUtilities.ImportProjectResourcesMenu();
    }
}
```
2. 将脚本放置在`Editor`路径下，否则不会被识别为Editor脚本
3. 点击`Tools > Auto Import TMP Essentials`可以自动导入TMP  Essentials包，并且不会重复导入，不需要等到创建一个使用TMP的UI组件时再选择导入


<!--stackedit_data:
eyJoaXN0b3J5IjpbMTczNjQxMDQ2MV19
-->