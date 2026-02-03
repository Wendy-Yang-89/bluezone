# Scripts for Auto Import TMP Essentials

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
<!--stackedit_data:
eyJoaXN0b3J5IjpbNjU0MzUyNTkwXX0=
-->