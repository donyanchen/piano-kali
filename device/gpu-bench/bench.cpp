// Offscreen, single-frame latency benchmark for one identical GL/Vulkan scene.
// No swapchain, presentation, VSync, network, or user desktop modification.
#include <epoxy/gl.h>
#include <epoxy/egl.h>
#include <vulkan/vulkan.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <time.h>
#include <unistd.h>

constexpr uint32_t W=3048,H=2032;
void require(bool ok,const std::string &why) { if(!ok) throw std::runtime_error(why); }
void vkcheck(VkResult result,const char* op) { require(result==VK_SUCCESS,std::string(op)+": "+std::to_string(result)); }
#define VKCHECK(op) vkcheck(op,#op)
double now(clockid_t clock=CLOCK_MONOTONIC) { timespec ts; clock_gettime(clock,&ts); return ts.tv_sec+ts.tv_nsec*1e-9; }
std::string readtext(const std::string &path) { std::ifstream in(path); require(in.good(),"open "+path); return {std::istreambuf_iterator<char>(in),{}}; }
std::string define(std::string source,const std::string &defs) { auto pos=source.find('\n'); source.insert(pos+1,defs+"\n"); return source; }
struct Sample {double wall,cpu,gpu;};
struct Snapshot {long rss=0,pss=0;};
Snapshot memory() {
    Snapshot out; std::istringstream in(readtext("/proc/self/smaps_rollup")); std::string line;
    while(std::getline(in,line)) {long value; if(sscanf(line.c_str(),"Rss: %ld",&value)==1) out.rss=value; if(sscanf(line.c_str(),"Pss: %ld",&value)==1) out.pss=value;}
    return out;
}

struct GLBench {
    EGLDisplay display; EGLContext context; EGLSurface surface;
    GLuint program,texture,fbo,vao,query; bool ui;
    std::string renderer;
    GLuint shader(GLenum type,const std::string &source) {
        GLuint s=glCreateShader(type); const char* p=source.c_str(); glShaderSource(s,1,&p,nullptr); glCompileShader(s);
        GLint ok; glGetShaderiv(s,GL_COMPILE_STATUS,&ok); char log[8192]={}; glGetShaderInfoLog(s,sizeof(log),nullptr,log); require(ok,log); return s;
    }
    GLBench(const std::string &workload):ui(workload=="ui") {
        auto get_platform=(PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
        require(get_platform!=nullptr,"EGL_EXT_platform_base missing");
        display=get_platform(EGL_PLATFORM_SURFACELESS_MESA,EGL_DEFAULT_DISPLAY,nullptr);
        EGLint major,minor; require(eglInitialize(display,&major,&minor),"eglInitialize");
        require(eglBindAPI(EGL_OPENGL_API),"eglBindAPI");
        EGLint attrs[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
        EGLConfig config; EGLint count; require(eglChooseConfig(display,attrs,&config,1,&count) && count,"eglChooseConfig");
        EGLint ca[]={EGL_CONTEXT_MAJOR_VERSION,4,EGL_CONTEXT_MINOR_VERSION,5,EGL_CONTEXT_OPENGL_PROFILE_MASK,EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT,EGL_NONE};
        context=eglCreateContext(display,config,EGL_NO_CONTEXT,ca); require(context!=EGL_NO_CONTEXT,"eglCreateContext");
        EGLint sa[]={EGL_WIDTH,1,EGL_HEIGHT,1,EGL_NONE}; surface=eglCreatePbufferSurface(display,config,sa);
        require(eglMakeCurrent(display,surface,surface,context),"eglMakeCurrent");
        renderer=(const char*)glGetString(GL_RENDERER);
        require(renderer.find("llvmpipe")==std::string::npos,"software renderer rejected");
        std::string defs="#define LOOPS "+std::string(workload=="alu"?"64":"0")+"\n#define ALPHA "+(ui?"0.35":"1.0");
        GLuint vs=shader(GL_VERTEX_SHADER,readtext("scene.vert")); GLuint fs=shader(GL_FRAGMENT_SHADER,define(readtext("scene.frag"),defs));
        program=glCreateProgram(); glAttachShader(program,vs); glAttachShader(program,fs); glLinkProgram(program);
        GLint ok; glGetProgramiv(program,GL_LINK_STATUS,&ok); require(ok,"GL program link"); glDeleteShader(vs); glDeleteShader(fs);
        glUseProgram(program); glGenVertexArrays(1,&vao); glBindVertexArray(vao);
        glGenTextures(1,&texture); glBindTexture(GL_TEXTURE_2D,texture); glTexStorage2D(GL_TEXTURE_2D,1,GL_RGBA8,W,H);
        glGenFramebuffers(1,&fbo); glBindFramebuffer(GL_FRAMEBUFFER,fbo); glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
        require(glCheckFramebufferStatus(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE,"GL framebuffer");
        glDisable(GL_DITHER); glDisable(GL_DEPTH_TEST); glDisable(GL_CULL_FACE); glViewport(0,0,W,H);
        glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA); if(ui) glEnable(GL_BLEND);
        glGenQueries(1,&query); glFinish(); require(glGetError()==GL_NO_ERROR,"GL setup error");
    }
    double frame() {
        glBeginQuery(GL_TIME_ELAPSED,query); glDisable(GL_SCISSOR_TEST); glClearColor(.05,.05,.05,1); glClear(GL_COLOR_BUFFER_BIT);
        if(ui) {
            glEnable(GL_SCISSOR_TEST);
            for(int layer=0;layer<2;layer++) for(uint32_t y=0;y<32;y++) for(uint32_t x=0;x<32;x++) {
                uint32_t left=x*W/32,bottom=y*H/32;
                glScissor(left,bottom,(x+1)*W/32-left,(y+1)*H/32-bottom); glDrawArrays(GL_TRIANGLES,0,3);
            }
        } else glDrawArrays(GL_TRIANGLES,0,3);
        glEndQuery(GL_TIME_ELAPSED); glFinish(); GLuint64 ns; glGetQueryObjectui64v(query,GL_QUERY_RESULT,&ns);
        return ns*1e-6;
    }
    std::vector<uint8_t> pixels() { std::vector<uint8_t> data(size_t(W)*H*4); glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,data.data()); require(glGetError()==GL_NO_ERROR,"GL readback"); return data; }
    ~GLBench() { eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT); eglDestroySurface(display,surface); eglDestroyContext(display,context); eglTerminate(display); }
};

struct VKBench {
    VkInstance instance; VkPhysicalDevice physical; VkDevice device; VkQueue queue; uint32_t family;
    VkImage image; VkDeviceMemory image_memory; VkImageView view; VkRenderPass renderpass; VkFramebuffer framebuffer;
    VkPipelineLayout layout; VkPipeline pipeline; VkCommandPool pool; VkCommandBuffer command; VkFence fence; VkQueryPool queries;
    VkPhysicalDeviceMemoryProperties memory_properties; VkPhysicalDeviceProperties properties;
    bool ui; std::string renderer;
    uint32_t memory_type(uint32_t mask,VkMemoryPropertyFlags flags) {
        for(uint32_t i=0;i<memory_properties.memoryTypeCount;i++) if((mask&(1u<<i)) && (memory_properties.memoryTypes[i].propertyFlags&flags)==flags) return i;
        throw std::runtime_error("Vulkan memory type missing");
    }
    VkShaderModule shader(const std::string &file) {
        std::string bytes=readtext(file); std::vector<uint32_t> words(bytes.size()/4); memcpy(words.data(),bytes.data(),bytes.size());
        VkShaderModuleCreateInfo ci={VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO}; ci.codeSize=bytes.size(); ci.pCode=words.data();
        VkShaderModule result; VKCHECK(vkCreateShaderModule(device,&ci,nullptr,&result)); return result;
    }
    VKBench(const std::string &workload):ui(workload=="ui") {
        VkApplicationInfo app={VK_STRUCTURE_TYPE_APPLICATION_INFO}; app.pApplicationName="sheng matched GPU benchmark"; app.apiVersion=VK_API_VERSION_1_1;
        VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&app; VKCHECK(vkCreateInstance(&ici,nullptr,&instance));
        uint32_t count; VKCHECK(vkEnumeratePhysicalDevices(instance,&count,nullptr)); std::vector<VkPhysicalDevice> devices(count); VKCHECK(vkEnumeratePhysicalDevices(instance,&count,devices.data()));
        physical=VK_NULL_HANDLE;
        for(auto d:devices) { VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(d,&p); if(p.vendorID==0x5143) {physical=d;break;} }
        require(physical!=VK_NULL_HANDLE,"Qualcomm hardware Vulkan device missing");
        vkGetPhysicalDeviceProperties(physical,&properties); renderer=properties.deviceName; require(renderer.find("Turnip")!=std::string::npos,"not Turnip");
        vkGetPhysicalDeviceMemoryProperties(physical,&memory_properties);
        vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,nullptr); std::vector<VkQueueFamilyProperties> families(count); vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,families.data());
        family=UINT32_MAX; for(uint32_t i=0;i<count;i++) if((families[i].queueFlags&VK_QUEUE_GRAPHICS_BIT) && families[i].timestampValidBits>=32) { family=i;break; }
        require(family!=UINT32_MAX,"graphics timestamp queue missing");
        float priority=1; VkDeviceQueueCreateInfo qci={VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; qci.queueFamilyIndex=family; qci.queueCount=1; qci.pQueuePriorities=&priority;
        VkDeviceCreateInfo dci={VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&qci; VKCHECK(vkCreateDevice(physical,&dci,nullptr,&device)); vkGetDeviceQueue(device,family,0,&queue);
        VkImageCreateInfo image_ci={VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO}; image_ci.imageType=VK_IMAGE_TYPE_2D; image_ci.format=VK_FORMAT_R8G8B8A8_UNORM; image_ci.extent={W,H,1}; image_ci.mipLevels=1; image_ci.arrayLayers=1; image_ci.samples=VK_SAMPLE_COUNT_1_BIT; image_ci.tiling=VK_IMAGE_TILING_OPTIMAL; image_ci.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
        VKCHECK(vkCreateImage(device,&image_ci,nullptr,&image)); VkMemoryRequirements req; vkGetImageMemoryRequirements(device,image,&req);
        VkMemoryAllocateInfo ai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; ai.allocationSize=req.size; ai.memoryTypeIndex=memory_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT); VKCHECK(vkAllocateMemory(device,&ai,nullptr,&image_memory)); VKCHECK(vkBindImageMemory(device,image,image_memory,0));
        VkImageViewCreateInfo vci={VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO}; vci.image=image; vci.viewType=VK_IMAGE_VIEW_TYPE_2D; vci.format=image_ci.format; vci.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}; VKCHECK(vkCreateImageView(device,&vci,nullptr,&view));
        VkAttachmentDescription attachment={}; attachment.format=image_ci.format; attachment.samples=VK_SAMPLE_COUNT_1_BIT; attachment.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR; attachment.storeOp=VK_ATTACHMENT_STORE_OP_STORE; attachment.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE; attachment.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE; attachment.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED; attachment.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        VkAttachmentReference reference={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL}; VkSubpassDescription sub={}; sub.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS; sub.colorAttachmentCount=1; sub.pColorAttachments=&reference;
        VkSubpassDependency dep={}; dep.srcSubpass=VK_SUBPASS_EXTERNAL; dep.dstSubpass=0; dep.srcStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT; dep.dstStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT; dep.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT; dep.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        VkRenderPassCreateInfo rpci={VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO}; rpci.attachmentCount=1; rpci.pAttachments=&attachment; rpci.subpassCount=1; rpci.pSubpasses=&sub; rpci.dependencyCount=1; rpci.pDependencies=&dep; VKCHECK(vkCreateRenderPass(device,&rpci,nullptr,&renderpass));
        VkFramebufferCreateInfo fbci={VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO}; fbci.renderPass=renderpass; fbci.attachmentCount=1; fbci.pAttachments=&view; fbci.width=W; fbci.height=H; fbci.layers=1; VKCHECK(vkCreateFramebuffer(device,&fbci,nullptr,&framebuffer));
        VkPipelineLayoutCreateInfo lci={VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO}; VKCHECK(vkCreatePipelineLayout(device,&lci,nullptr,&layout));
        VkShaderModule vs=shader("scene.vert.spv"),fs=shader(workload+".frag.spv");
        VkPipelineShaderStageCreateInfo stages[2]={}; for(int i=0;i<2;i++) {stages[i].sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO; stages[i].stage=i==0?VK_SHADER_STAGE_VERTEX_BIT:VK_SHADER_STAGE_FRAGMENT_BIT; stages[i].module=i==0?vs:fs; stages[i].pName="main";}
        VkPipelineVertexInputStateCreateInfo vertex={VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO}; VkPipelineInputAssemblyStateCreateInfo assembly={VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO}; assembly.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
        VkViewport viewport={0,0,float(W),float(H),0,1}; VkRect2D scissor={{0,0},{W,H}};
        VkPipelineViewportStateCreateInfo vp={VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO}; vp.viewportCount=1; vp.pViewports=&viewport; vp.scissorCount=1; vp.pScissors=&scissor;
        VkPipelineRasterizationStateCreateInfo raster={VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO}; raster.polygonMode=VK_POLYGON_MODE_FILL; raster.cullMode=VK_CULL_MODE_NONE; raster.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE; raster.lineWidth=1;
        VkPipelineMultisampleStateCreateInfo ms={VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO}; ms.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT;
        VkPipelineColorBlendAttachmentState blend={}; blend.blendEnable=ui; blend.srcColorBlendFactor=blend.srcAlphaBlendFactor=VK_BLEND_FACTOR_SRC_ALPHA; blend.dstColorBlendFactor=blend.dstAlphaBlendFactor=VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA; blend.colorBlendOp=blend.alphaBlendOp=VK_BLEND_OP_ADD; blend.colorWriteMask=15;
        VkPipelineColorBlendStateCreateInfo bc={VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO}; bc.attachmentCount=1; bc.pAttachments=&blend;
        VkDynamicState ds=VK_DYNAMIC_STATE_SCISSOR; VkPipelineDynamicStateCreateInfo dynamic={VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO}; dynamic.dynamicStateCount=1; dynamic.pDynamicStates=&ds;
        VkGraphicsPipelineCreateInfo pci={VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO}; pci.stageCount=2; pci.pStages=stages; pci.pVertexInputState=&vertex; pci.pInputAssemblyState=&assembly; pci.pViewportState=&vp; pci.pRasterizationState=&raster; pci.pMultisampleState=&ms; pci.pColorBlendState=&bc; pci.pDynamicState=&dynamic; pci.layout=layout; pci.renderPass=renderpass;
        VKCHECK(vkCreateGraphicsPipelines(device,VK_NULL_HANDLE,1,&pci,nullptr,&pipeline)); vkDestroyShaderModule(device,vs,nullptr); vkDestroyShaderModule(device,fs,nullptr);
        VkCommandPoolCreateInfo cpci={VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; cpci.queueFamilyIndex=family; cpci.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT; VKCHECK(vkCreateCommandPool(device,&cpci,nullptr,&pool));
        VkCommandBufferAllocateInfo cbai={VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; cbai.commandPool=pool; cbai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; cbai.commandBufferCount=1; VKCHECK(vkAllocateCommandBuffers(device,&cbai,&command));
        VkFenceCreateInfo fci={VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; VKCHECK(vkCreateFence(device,&fci,nullptr,&fence));
        VkQueryPoolCreateInfo qpci={VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO}; qpci.queryType=VK_QUERY_TYPE_TIMESTAMP; qpci.queryCount=2; VKCHECK(vkCreateQueryPool(device,&qpci,nullptr,&queries));
    }
    void begin() {VKCHECK(vkResetCommandBuffer(command,0)); VkCommandBufferBeginInfo info={VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; info.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT; VKCHECK(vkBeginCommandBuffer(command,&info));}
    void submit() {VKCHECK(vkEndCommandBuffer(command)); VKCHECK(vkResetFences(device,1,&fence)); VkSubmitInfo info={VK_STRUCTURE_TYPE_SUBMIT_INFO}; info.commandBufferCount=1; info.pCommandBuffers=&command; VKCHECK(vkQueueSubmit(queue,1,&info,fence)); VKCHECK(vkWaitForFences(device,1,&fence,VK_TRUE,10000000000ULL));}
    double frame() {
        begin(); vkCmdResetQueryPool(command,queries,0,2); vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,queries,0);
        VkClearValue clear={}; clear.color={{.05f,.05f,.05f,1.f}}; VkRenderPassBeginInfo rp={VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO}; rp.renderPass=renderpass; rp.framebuffer=framebuffer; rp.renderArea={{0,0},{W,H}}; rp.clearValueCount=1; rp.pClearValues=&clear;
        vkCmdBeginRenderPass(command,&rp,VK_SUBPASS_CONTENTS_INLINE); vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_GRAPHICS,pipeline);
        if(ui) {
            for(int layer=0;layer<2;layer++) for(uint32_t y=0;y<32;y++) for(uint32_t x=0;x<32;x++) {
                uint32_t left=x*W/32,bottom=y*H/32; VkRect2D rect={{int32_t(left),int32_t(bottom)},{(x+1)*W/32-left,(y+1)*H/32-bottom}};
                vkCmdSetScissor(command,0,1,&rect); vkCmdDraw(command,3,1,0,0);
            }
        } else {VkRect2D rect={{0,0},{W,H}}; vkCmdSetScissor(command,0,1,&rect); vkCmdDraw(command,3,1,0,0);}
        vkCmdEndRenderPass(command); vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,queries,1); submit();
        uint64_t times[2]; VKCHECK(vkGetQueryPoolResults(device,queries,0,2,sizeof(times),times,sizeof(uint64_t),VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT));
        return (times[1]-times[0])*double(properties.limits.timestampPeriod)*1e-6;
    }
    std::vector<uint8_t> pixels() {
        VkBuffer buffer; VkDeviceMemory mem; VkBufferCreateInfo bci={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; bci.size=size_t(W)*H*4; bci.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT; VKCHECK(vkCreateBuffer(device,&bci,nullptr,&buffer));
        VkMemoryRequirements req; vkGetBufferMemoryRequirements(device,buffer,&req); VkMemoryAllocateInfo ai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; ai.allocationSize=req.size; ai.memoryTypeIndex=memory_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT); VKCHECK(vkAllocateMemory(device,&ai,nullptr,&mem)); VKCHECK(vkBindBufferMemory(device,buffer,mem,0));
        begin(); VkImageMemoryBarrier barrier={VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER}; barrier.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT; barrier.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT; barrier.oldLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL; barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL; barrier.srcQueueFamilyIndex=barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED; barrier.image=image; barrier.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&barrier);
        VkBufferImageCopy copy={}; copy.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1}; copy.imageExtent={W,H,1}; vkCmdCopyImageToBuffer(command,image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,buffer,1,&copy); submit();
        std::vector<uint8_t> data(size_t(W)*H*4); void* mapping; VKCHECK(vkMapMemory(device,mem,0,data.size(),0,&mapping)); memcpy(data.data(),mapping,data.size()); vkUnmapMemory(device,mem); vkDestroyBuffer(device,buffer,nullptr); vkFreeMemory(device,mem,nullptr); return data;
    }
    ~VKBench() {
        vkDeviceWaitIdle(device); vkDestroyQueryPool(device,queries,nullptr); vkDestroyFence(device,fence,nullptr);
        vkDestroyCommandPool(device,pool,nullptr); vkDestroyPipeline(device,pipeline,nullptr); vkDestroyPipelineLayout(device,layout,nullptr);
        vkDestroyFramebuffer(device,framebuffer,nullptr); vkDestroyRenderPass(device,renderpass,nullptr); vkDestroyImageView(device,view,nullptr);
        vkDestroyImage(device,image,nullptr); vkFreeMemory(device,image_memory,nullptr); vkDestroyDevice(device,nullptr); vkDestroyInstance(instance,nullptr);
    }
};

template<class Backend> void run(const std::string &api,const std::string &workload,double seconds,const std::string &prefix) {
    Backend b(workload); std::vector<Sample> samples; samples.reserve(20000);
    double warm=now(); do { b.frame(); } while(now()-warm<1.0);
    Snapshot before=memory(); double start=now();
    do {
        double cpu=now(CLOCK_PROCESS_CPUTIME_ID),wall=now(); double gpu=b.frame();
        double end=now(); double cpu_end=now(CLOCK_PROCESS_CPUTIME_ID);
        samples.push_back({(end-wall)*1000,(cpu_end-cpu)*1000,gpu});
    } while(now()-start<seconds);
    double elapsed=now()-start; Snapshot after=memory();
    // Readback and disk writing are outside all timings and memory snapshots.
    auto data=b.pixels(); std::ofstream image(prefix+".rgba",std::ios::binary); require(image.good(),"open image output "+prefix); image.write((const char*)data.data(),data.size()); image.close(); require(image.good(),"write image output");
    std::ofstream out(prefix+".json"); require(out.good(),"open JSON output "+prefix); out<<std::fixed<<std::setprecision(6);
    out<<"{\"api\":\""<<api<<"\",\"workload\":\""<<workload<<"\",\"renderer\":\""<<b.renderer<<"\",\"width\":"<<W<<",\"height\":"<<H<<",\"frames\":"<<samples.size()<<",\"elapsed_s\":"<<elapsed<<",\"rss_kib\":"<<after.rss<<",\"pss_kib\":"<<after.pss<<",\"warm_rss_kib\":"<<before.rss<<",\"samples\":[";
    for(size_t i=0;i<samples.size();i++) {auto s=samples[i]; if(i) out<<","; out<<"["<<s.wall<<","<<s.cpu<<","<<s.gpu<<"]";} out<<"]}\n"; out.close(); require(out.good(),"write JSON output");
    std::cout<<api<<" "<<workload<<" "<<b.renderer<<" frames="<<samples.size()<<" fps="<<samples.size()/elapsed<<" rss_MiB="<<after.rss/1024.0<<"\n";
}
int main(int argc,char**argv) {
    try {
        require(argc==5,"usage: bench gl|vk fill|ui|alu seconds output-prefix");
        std::string api=argv[1],workload=argv[2]; require(workload=="fill"||workload=="ui"||workload=="alu","invalid workload");
        if(api=="gl") run<GLBench>(api,workload,atof(argv[3]),argv[4]); else if(api=="vk") run<VKBench>(api,workload,atof(argv[3]),argv[4]); else throw std::runtime_error("invalid API");
        return 0;
    } catch(const std::exception &e) {std::cerr<<"ERROR: "<<e.what()<<"\n"; return 1;}
}
