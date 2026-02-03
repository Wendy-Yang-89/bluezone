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
2. 将jiao'b
<!--stackedit_data:
eyJoaXN0b3J5IjpbLTE3MDQzNDc5OTldfQ==
-->