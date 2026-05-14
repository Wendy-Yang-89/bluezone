## Perlin Noise

https://www.shadertoy.com/view/WXdyWl

```c++
vec2 N22(vec2 p)
{
    vec3 a = fract(p.xyx * vec3(123.34, 234.34, 345.65));
    a += dot(a, a + 34.45);
    return fract(vec2(a.x * a.y, a.y * a.z));
}

vec2 get_gradient(vec2 pos)
{
    float twoPi = 6.283185;
    float angle = N22(pos).x * twoPi;
    return vec2(cos(angle), sin(angle));
}

float perlin_noise(vec2 uv, float cellDensity)
{
    vec2 gridCoord = uv * cellDensity;
    vec2 cellId = floor(gridCoord);
    vec2 localCoord = fract(gridCoord);
    
    vec2 smoothLocalCoord = localCoord * localCoord * (3.0 - 2.0 * localCoord);
    
    vec2 lt = cellId + vec2(0.0, 1.0);
    vec2 rt = cellId + vec2(1.0, 1.0);   
    vec2 lb = cellId + vec2(0.0, 0.0);
    vec2 rb = cellId + vec2(1.0, 0.0);
    
    float ltDot = dot(gridCoord - lt, get_gradient(lt));
    float rtDot = dot(gridCoord - rt, get_gradient(rt));
    float lbDot = dot(gridCoord - lb, get_gradient(lb));
    float rbDot = dot(gridCoord - rb, get_gradient(rb));
    
    float noise_value = mix(
        mix(lbDot, rbDot, smoothLocalCoord.x),
        mix(ltDot, rtDot, smoothLocalCoord.x),
        smoothLocalCoord.y
    );
    
    return (0.5 + 0.5 * (noise_value / 0.7));
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord/iResolution.xy;

    // Time varying pixel color
    vec3 col = 0.5 + 0.5*cos(iTime+uv.xyx+vec3(0,2,4));

    // Output to screen
    fragColor = vec4(vec3(perlin_noise(uv + iTime * 0.1, 7.0f)),1.0);
}
```
<!--stackedit_data:
eyJoaXN0b3J5IjpbMjA4NjQ1NzQ2MF19
-->