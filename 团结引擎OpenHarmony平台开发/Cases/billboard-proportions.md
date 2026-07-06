# Case: Billboard Proportions Distorted on Different Screen Aspect Ratios

## Problem

The texture billboard created by TextureManager appeared distorted (stretched or squished) when the screen aspect ratio didn't match the texture grid's aspect ratio. On portrait-mode mobile devices, the billboard was particularly compressed horizontally.

## Error Log

No error. The visual symptom was that textures on the billboard appeared stretched or the billboard didn't fill the visible screen area appropriately.

## Diagnosis Process

1. Examined the billboard size calculation in `TextureManager.CreateBillboard()`
2. Original code calculated billboard dimensions based only on the camera's visible height
3. The width was derived from the height without considering the screen's actual aspect ratio
4. On portrait screens (e.g., 1080×2400), the visible width is much less than the height-based calculation assumed
5. The texture grid's aspect ratio (cols/rows) was not properly accounted for

## Root Cause

The original size calculation assumed a relationship between billboard width and height that didn't preserve the texture grid's aspect ratio across different screen orientations:

1. **Screen aspect ratio matters**: On a portrait screen, the visible width (at a given distance) is smaller than on a landscape screen with the same FOV
2. **Grid aspect ratio matters**: A 3×2 grid (cols=3, rows=2) has a 1.5:1 aspect ratio. The billboard must respect this to avoid distorting the textures
3. **Both constraints must be satisfied simultaneously**: The billboard must fit within the visible screen area AND maintain the grid's aspect ratio

## Fix

The corrected calculation considers both the screen's visible area and the grid's aspect ratio, then picks the largest size that fits within both constraints:

```csharp
float fovRad = mainCamera.fieldOfView * Mathf.Deg2Rad;
float screenAspect = (float)Screen.width / Screen.height;
float gridAspect = (float)cols / rows;

float visibleHeight = 2f * billboardDistance * Mathf.Tan(fovRad * 0.5f);
float visibleWidth = visibleHeight * screenAspect;

// Strategy: calculate two candidate sizes, pick the one that fits
float widthByScreen = visibleWidth * billboardScreenRatio;
float heightByWidth = widthByScreen / gridAspect;  // height if width is the constraint

float heightByScreen = visibleHeight * billboardScreenRatio;
float widthByHeight = heightByScreen * gridAspect;  // width if height is the constraint

float width, height;
if (heightByWidth <= visibleHeight * billboardScreenRatio)
{
    // Width-constrained: the grid fits within the visible width
    width = widthByScreen;
    height = heightByWidth;
}
else
{
    // Height-constrained: the grid fits within the visible height
    height = heightByScreen;
    width = widthByHeight;
}
```

**Key insight**: `gridAspect = (float)cols / rows` preserves the texture grid's original proportions. The billboard dimensions are calculated to show the grid at its natural aspect ratio while fitting within the camera's visible area.

## The Same Pattern in TransparentManager

TransparentManager uses a simpler version because transparent planes are always square:

```csharp
float adaptiveSize = Mathf.Min(visibleHeight, visibleWidth) * planeScreenRatio;
```

On portrait screens, `visibleWidth < visibleHeight`, so the plane size is limited by the width. This prevents planes from extending beyond the screen's visible area.

## Lesson

**When calculating runtime UI/billboard sizes for camera-facing objects, consider both the screen's visible area (which depends on aspect ratio) and the content's own aspect ratio.** Calculate two candidate sizes (one width-constrained, one height-constrained), then pick the one where both dimensions fit within the visible area. This ensures the content fits and maintains correct proportions.
