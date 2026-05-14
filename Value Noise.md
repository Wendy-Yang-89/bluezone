## Value Noise

https://www.shadertoy.com/view/W3tyWl

```c++
float N21(vec2 p)
{
    return fract(sin(p.x *100. + p.y * 6574.) * 5647.);
}

float N21_2(vec2 p)
{
    return fract(sin(p.x *131.13 + p.y * 6574.31231) * 5641.3212) - 1.;
}


float SmoothNoise(vec2 uv)
{
    vec2 lv = fract(uv);
    vec2 id = floor(uv);
    
    lv = lv * lv * (3.0 - 2.0 * lv);
    
    float bl = N21_2(id);
    float br = N21_2(id + vec2(1.0, 0.0));
    float b = mix(bl, br, lv.x);
    
    float tl = N21_2(id + vec2(0.0, 1.0));
    float tr = N21_2(id + vec2(1.0, 1.0));
    float t = mix(tl, tr, lv.x);
    
    return mix(b, t, lv.y);
}

// octave pf noise / a layer of noise
float SmoothNoise2(vec2 uv)
{
    float c = abs(SmoothNoise(uv * 4.0));
    // octave pf noise / a layer of noise
    
    c += abs(SmoothNoise(uv * 8.0)) * 0.5;
    c += abs(SmoothNoise(uv * 16.0)) * 0.25;
    c += abs(SmoothNoise(uv * 32.0)) * 0.125;
    c += abs(SmoothNoise(uv * 64.0)) * 0.0625;

    return c / 2.;
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord/iResolution.xy;
    
    uv += iTime * 0.1;

    float c = SmoothNoise2(uv);
        
    vec3 col = vec3(c);
    
    // Output to screen
    fragColor = vec4(col, 1.0);
}
```
<!--stackedit_data:
eyJoaXN0b3J5IjpbMTAwNjc2OTBdfQ==
-->