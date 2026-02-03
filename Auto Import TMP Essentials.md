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
2. 将脚本放置在`Editor`路径下，否则不会被
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTM2ODQ4Njg5OV19
-->