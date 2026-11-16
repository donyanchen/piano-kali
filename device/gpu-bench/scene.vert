#version 450
#ifdef VULKAN
#define VERTEX_ID gl_VertexIndex
#else
#define VERTEX_ID gl_VertexID
#endif
void main() {
    vec2 p=vec2((VERTEX_ID << 1) & 2, VERTEX_ID & 2);
    gl_Position=vec4(p*2.0-1.0,0.0,1.0);
}
