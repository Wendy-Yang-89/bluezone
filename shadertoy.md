# ShaderToy Code

  https://www.shadertoy.com/profile/?show=shaders









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
eyJoaXN0b3J5IjpbLTE0NDcwOTQ0OSwtMTY5NTQ5NTI1OV19
-->