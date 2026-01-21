# ShaderToy Code

  https://www.shadertoy.com/profile/?show=shaders

#### Voronoi Noise

https://www.shadertoy.com/view/w3ccWS

```cpp

#define VORONOI_FIRST 0

  

// deterministic random generator

vec2 N22(vec2 p)

{

vec3 a = fract(p.xyx * vec3(123.4, 234.34, 345.65));

a += dot(a, a + 34.45);

return fract(vec2(a.x * a.y, a.y * a.z));

}

  

void mainImage( out vec4 fragColor, in vec2 fragCoord )

{

// Normalize to [-1, 1]

// vec2 uv = (2.0 * fragCoord - iResolution.xy) / iResolution.xy;

// Normalize to [-1, 1] along the shortest side

vec2 uv = (2.0 * fragCoord - iResolution.xy) / min(iResolution.x, iResolution.y);

// for visualizing the generated seeds

float m = 0.0;

float t = iTime;

// color display

vec3 col = vec3(0.0);

// initialize a distance far enough beftore searching the nearest distance

float minDist = 100.;

float cellIndex = 0.0;

vec2 cellIndex2 = vec2(0.0);

  

if (VORONOI_FIRST == 1) {

// Algorithm 1

// cons:

// 1. non-uniform seed distribution

// 2. inefficient distance search algorithm (all seeds need to be traversed)

// traverse each seed in screen

for (float i = 0.; i < 50.; i++) {

// generate random value for seed of index i

vec2 n = N22(vec2(i));

// generate seed position in animation

vec2 p = sin(n * t);

// calcualte distance between each fragment with the seed of index i

float d = length(uv - p);

// draw a circle (center = p, inner radius = 0.01, outer radius = 0.02)

m += smoothstep(0.02, 0.01, d);

// find the nearest distance between each fragment with seeds

if (d < minDist) {

// update the nearest distance and cellIndex

minDist = d;

cellIndex = i;

}

}

// visualize the generated seeds

// col = vec3(m);

// visualize the voronoi diagram by nearest distance

col = vec3(minDist);

// visualize the voronoi diagram by nearest cell

// col = vec3(cellIndex / 50.);

}

else {

// Algorithm 2

// pros:

// 1. uniformly distributed seeds in the lattice

// 2. more efficient (only search for seeds from neighboring grids rather than all seeds)

// control the cell density

uv *= 5.;

// get local coordinates in the cell of each fragment

vec2 gv = fract(uv); // [0.0, 1.0]

// get cell id of each fragment

vec2 id = floor(uv);

// traverse all neighboring cells

for (float y = -1.; y <= 1.; y++) {

for (float x = -1.; x <= 1.; x++) {

// get the relative offsets from the current cell with id as index

vec2 offs = vec2(x, y);

  

// id + offs equals the actual neighboring cell index

// generate random offsets based on the cell index

vec2 n = N22(id + offs);

// generate animated offsets

vec2 p = sin(n * t) * 0.5 + 0.5 + offs; // scale generated randon vector into [0.0, 1.0]

  

// calcualte distance between each fragment with the current seed

// seed position: id + p

// fragment position: id + gv

// Several distance function

// 1. euclidean distance

float ed = length(gv - p);

// 2. manhattan distance

float md = abs(gv.x - p.x) + abs(gv.y - p.y);

// 3. chebyshev distance

float cd = max(abs(gv.x - p.x), abs(gv.y - p.y));

// blend between different distance calculation

float d = mix(ed, md, sin(t) * 0.5 + 0.5);

// draw a circle (center = p, inner radius = 0.01, outer radius = 0.02)

m += smoothstep(0.02, 0.01, d);

  

// find the nearest distance between each fragment with seeds

if (d < minDist) {

// update the nearest distance and cellIndex

minDist = d;

cellIndex2 = id + offs;

}

}

}

  

col = vec3(m);

col = vec3(minDist);

// col.rg = cellIndex2 * .2;

}

  

// Output to screen

fragColor = vec4(col,1.0);

}

```

#### Value Noise

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

#### Perlin Noise

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

#### Simplex Noise

https://www.shadertoy.com/view/w3VyzR

```c++
// The MIT License
// Copyright © 2013 Inigo Quilez
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// https://www.youtube.com/c/InigoQuilez
// https://iquilezles.org


// Simplex Noise (http://en.wikipedia.org/wiki/Simplex_noise), a type of gradient noise
// that uses N+1 vertices for random gradient interpolation instead of 2^N as in regular
// latice based Gradient Noise.

// All noise functions here:
//
// https://www.shadertoy.com/playlist/fXlXzf&from=0&num=12


vec2 hash(vec2 p)
{
     p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
     return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

float simplexNoise(vec2 p)
{
    // for transforming coords from simplex to hybercube
    // const float k1 = 0.366025404;
    float t = 3.0;
    float k1 = (sqrt(t) - 1.0) / 2.0;
    
    // for transforming coords from hybercube to simplex
    // const float k2 = 0.211324865;
    float k2 = (3.0 - sqrt(t)) / 6.0;
    
    // p: coordinates in simplex coordinate system
    // coord: cell coordiantes in hybercube system
    vec2 coord = floor(p + (p.x + p.y) * k1);
    
    // offsets from vertex0 to p in simplex coordinate system
    // off0 = p - ((ix, iy) - (ix + iy) * k2);
    vec2 off0 = p - (coord - (coord.x + coord.y) * k2);
    
    // used to decide which simplex point p falls in
    // local.x < local.y, simplex = 0;
    // local.x >= local.y, simplex = 1;
    float simplex = step(off0.y, off0.x);
    
    // local.x < local.y, simplex = 0, offsets = (0.0, 1.0);
    // local.x >= local.y, simplex = 1, offsets = (1.0, 0.0);
    vec2 offsets = vec2(simplex, 1.0 - simplex);
    
    // offsets from vertex1 to p in simplex coordinate system
    // off1 = p - ((ix, iy) + offsets - (ix + iy + 1) * k2) = off0 - offsets + k2;
    vec2 off1 = off0 - offsets + k2;
    
    // offsets from vertex2 to p in simplex coordinate system
    // off2 = p - ((ix, iy) + (1, 1) - (ix + iy + 2) * k2) = off0 - 1 + 2 * k2;
    vec2 off2 = off0 - 1.0 + 2.0 * k2;
    
    // calculate radially symmetric kernels based on distance
    vec3 h = max(0.5 - vec3(dot(off0, off0), dot(off1, off1), dot(off2, off2)), 0.0);
    
    // sum all weighted dot-product of offsets and gradients
    vec3 noise = h * h * h * h * vec3(dot(off0, hash(coord + 0.0)), dot(off1, hash(coord + offsets)), dot(off2, hash(coord + 1.0)));
        
         
    return dot(noise, vec3(70.0));
}


void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord/iResolution.xy;
    
    uv = uv*vec2(iResolution.x/iResolution.y,1.0);
    // uv += iTime*0.25;

    // // Time varying pixel color
    //  col = 0.5 + 0.5*cos(iTime+uv.xyx+vec3(0,2,4));
    
    float n = simplexNoise(16.0 * uv);
    n = n * 0.5 + 0.5;
    
    vec3 col = vec3(n);

    // Output to screen
    fragColor = vec4(col,1.0);
}
```


<!--stackedit_data:
eyJoaXN0b3J5IjpbLTE2OTU0OTUyNTldfQ==
-->