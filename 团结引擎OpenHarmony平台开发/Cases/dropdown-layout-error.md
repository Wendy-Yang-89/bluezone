# Case: TMP Dropdown EndLayoutGroup Error

## Problem

When creating TMP_Dropdown at runtime via `UIBuilder.CreateDropdown()`, an error was thrown:

```
EndLayoutGroup: LayoutGroup != null
```

This error appeared repeatedly in the console when the UI was first constructed.

## Error Log

```
EndLayoutGroup: LayoutGroup != null
UnityEngine.UI.VerticalLayoutGroup:OnDisable()
```

## Diagnosis Process

1. Traced the error to the Dropdown's template child objects
2. Found that TMP_Dropdown has a `template` RectTransform that contains a ScrollRect + VerticalLayoutGroup
3. When the Dropdown is instantiated from a prefab, the template may be active by default
4. An active template with VerticalLayoutGroup interferes with the parent ScrollView's VerticalLayoutGroup
5. Unity's layout system tries to process both, leading to mismatched layout group stack

## Root Cause

Two issues:

1. **Template inactive children not found**: `GetComponentInChildren<TextMeshProUGUI>()` (without `true`) only searches active children. The Dropdown template's item text is typically inactive, so style wasn't being applied.

2. **Active template breaks layout**: When the Dropdown template GameObject is active, its internal VerticalLayoutGroup participates in the parent layout computation. This causes `EndLayoutGroup` errors because the layout system's group stack becomes inconsistent.

## Fix

```csharp
// 1. Search inactive children for template text
TextMeshProUGUI tmpTmpText = templateGO.GetComponentInChildren<TextMeshProUGUI>(true);

// 2. Always ensure template is inactive after setup
templateGO.SetActive(false);
```

The `SetActive(false)` at the end ensures the template's internal layout groups don't participate in the parent layout, even if the prefab had the template active.

## Lesson

**TMP_Dropdown's template must remain inactive unless the dropdown is open.** When constructing dropdowns programmatically, always force `template.SetActive(false)` after setup, regardless of the prefab's initial state. Also use `GetComponentInChildren<T>(true)` to search inactive children.
