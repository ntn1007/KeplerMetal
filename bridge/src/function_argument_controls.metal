#include <metal_stdlib>
#include <metal_command_buffer>
using namespace metal;
struct PlainTable{device uint*values [[id(0)]];};
struct MainTable{
 command_buffer commands [[id(0)]];compute_pipeline_state pipeline [[id(1)]];
 device uint*v0 [[id(2)]];device uint*v1 [[id(3)]];
 constant uint*parameters [[id(4)]];device uint*counter [[id(5)]];
};
struct SwappedTable{
 compute_pipeline_state pipeline [[id(0)]];command_buffer commands [[id(1)]];
 device uint*v0 [[id(2)]];device uint*v1 [[id(3)]];
 constant uint*parameters [[id(4)]];device uint*counter [[id(5)]];
};
kernel void control_plain(device PlainTable*a [[buffer(0)]],uint i [[thread_position_in_grid]]){if(!i)a->values[0]=42;}
kernel void control_swapped(device SwappedTable*a [[buffer(0)]],uint i [[thread_position_in_grid]]){if(!i)a->v0[0]=17;}
kernel void control_dual(device MainTable*a [[buffer(0)]],device PlainTable*b [[buffer(1)]],uint i [[thread_position_in_grid]]){if(!i)b->values[0]=a->v0[0];}
vertex float4 control_vertex(uint i [[vertex_id]]){return float4(float(i),0.0f,0.0f,1.0f);}
