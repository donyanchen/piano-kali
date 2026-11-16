#version 450
#ifndef LOOPS
#define LOOPS 0
#endif
#ifndef ALPHA
#define ALPHA 1.0
#endif
layout(location=0) out vec4 color;
void main() {
    // Match the raw framebuffer row order in both APIs; no presentation transform.
    vec3 v=vec3(gl_FragCoord.x/3048.0, gl_FragCoord.y/2032.0, 0.25);
    for(int i=0;i<LOOPS;i++)
        v=0.98*v+sin(v.zxy*1.2+float(i)*0.01)*0.01;
    color=vec4(v,ALPHA);
}
