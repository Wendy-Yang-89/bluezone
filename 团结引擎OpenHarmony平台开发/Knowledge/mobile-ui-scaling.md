# Mobile UI Scaling: CanvasScaler ScaleWithScreenSize

## The Problem

When building for mobile platforms (OHOS, Android, iOS), the default Unity UI scaling (`ConstantPixelSize`) results in tiny UI elements on high-DPI screens. A 12pt font that's readable on desktop becomes nearly invisible on a 400+ DPI mobile display.

## Approaches Considered

### Approach 1: Per-Element UI_SCALE (Rejected)

```csharp
private float UI_SCALE => IsMobilePlatform() ? 2.5f : 1.0f;
// Apply to each element individually:
tmpText.fontSize = fontSize * UI_SCALE;
rectTransform.sizeDelta = new Vector2(150 * UI_SCALE, 30 * UI_SCALE);
```

**Problems**:
- Must apply scale to every single UI element (font size, sizeDelta, padding, spacing, etc.)
- Easy to forget a field, resulting in inconsistent UI
- Does not adapt to different screen sizes/resolutions — only applies a fixed multiplier
- Maintenance burden: every new UI element must remember to use UI_SCALE

### Approach 2: CanvasScaler.ScaleWithScreenSize (Chosen)

```csharp
CanvasScaler canvasScaler = canvasGO.GetComponent<CanvasScaler>();
if (IsMobilePlatform())
{
    float mobileScaleFactor = 3.0f;
    canvasScaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
    canvasScaler.referenceResolution = new Vector2(
        Screen.width / mobileScaleFactor,
        Screen.height / mobileScaleFactor
    );
    canvasScaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
    canvasScaler.matchWidthOrHeight = 0.5f;
}
```

**How it works**:
1. `ScaleWithScreenSize` mode scales the entire Canvas based on the ratio between the reference resolution and the actual screen resolution
2. `referenceResolution` defines the "design resolution" — the resolution at which UI elements are 1:1 scale
3. The Canvas is automatically scaled up/down so that the reference resolution fits the actual screen
4. All child elements inherit this scaling — no per-element work needed

**Why `referenceResolution = new Vector2(Screen.width / 3.0, Screen.height / 3.0)`**:
- On a 1080×2400 screen, reference resolution becomes 360×800
- The Canvas is scaled ~3x, making all UI elements 3x larger
- This matches the per-element `UI_SCALE = 2.5f` approach approximately, but with better adaptivity
- The `mobileScaleFactor` of 3.0 was chosen empirically to match the visual size of the desktop version

**Why `matchWidthOrHeight = 0.5f`**:
- 0.0 = match width only (good for landscape)
- 1.0 = match height only (good for portrait)
- 0.5 = balanced scaling that preserves approximate aspect ratio
- On phones in portrait mode, this prevents extreme stretching in either direction

## Desktop Configuration

```csharp
canvasScaler.uiScaleMode = CanvasScaler.ScaleMode.ConstantPixelSize;
canvasScaler.scaleFactor = 1.0f;
```

On desktop, screens are large enough and DPI is low enough that 1:1 pixel size works well. No scaling needed.

## Element Layout

All UI elements use `LayoutElement.preferredHeight = 10` (this is the preferred size in the layout system; with `flexibleHeight = 0`, it acts as the exact height). The `ContentSizeFitter` and `VerticalLayoutGroup` handle vertical arrangement automatically. Since `ScaleWithScreenSize` scales the entire Canvas, these small pixel values are multiplied by the Canvas scale factor on mobile.

## Key Takeaway

**Use `CanvasScaler.ScaleWithScreenSize` for mobile UI scaling instead of per-element multipliers.** It's simpler, more maintainable, and automatically adapts to different screen resolutions and aspect ratios.
