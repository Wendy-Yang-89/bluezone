##  Voronoi Noise

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

<!--stackedit_data:
eyJoaXN0b3J5IjpbMzk3MjY1MDZdfQ==
-->