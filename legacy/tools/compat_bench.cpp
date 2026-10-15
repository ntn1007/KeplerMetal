#include "KeplerCompat.h"
#include <vector>
#include <cmath>
#include <cstdio>
#include <chrono>
#include <sys/resource.h>
using Clock=std::chrono::steady_clock;
double cpu_seconds(){rusage r;getrusage(RUSAGE_SELF,&r);return r.ru_utime.tv_sec+r.ru_stime.tv_sec+(r.ru_utime.tv_usec+r.ru_stime.tv_usec)/1e6;}
void cpu_softmax(const std::vector<float>&input,std::vector<float>&out,int rows,int cols){for(int r=0;r<rows;r++){float mx=-INFINITY;for(int j=0;j<cols;j++)mx=fmaxf(mx,input[r*cols+j]);float sum=0;for(int j=0;j<cols;j++){float v=expf(input[r*cols+j]-mx);out[r*cols+j]=v;sum+=v;}for(int j=0;j<cols;j++)out[r*cols+j]/=sum;}}
int main(){const int rows=4096,cols=1024;std::vector<float>input(rows*cols),cpu(input.size()),gpu(input.size());for(size_t i=0;i<input.size();i++)input[i]=float(int(i*17%1001)-500)*0.03125f;KCContext*c=kc_create(rows,cols);if(!c)return 1;printf("{\"device\":\"%s\",\"rows\":%d,\"columns\":%d,\"gpu_buffers_bytes\":%zu,\"scope\":\"application library using existing driver\"}\n",kc_device_name(c),rows,cols,input.size()*sizeof(float)*2);
for(int trial=0;trial<4;trial++){
auto start=Clock::now();double ct=cpu_seconds();cpu_softmax(input,cpu,rows,cols);double cpu_process=cpu_seconds()-ct;double cpu_wall=std::chrono::duration<double>(Clock::now()-start).count();
start=Clock::now();ct=cpu_seconds();double gpu_time=0;if(kc_softmax(c,input.data(),gpu.data(),&gpu_time))return 2;double gpu_process=cpu_seconds()-ct;double gpu_wall=std::chrono::duration<double>(Clock::now()-start).count();
double max_abs=0,l2error=0,l2ref=0,max_sum_error=0;size_t bad=0;for(size_t i=0;i<input.size();i++){double delta=fabs(double(cpu[i])-gpu[i]);max_abs=fmax(max_abs,delta);l2error+=delta*delta;l2ref+=double(cpu[i])*cpu[i];if(!std::isfinite(gpu[i])||delta>1e-6+1e-4*fabs(cpu[i]))bad++;}
for(int r=0;r<rows;r++){double sum=0;for(int j=0;j<cols;j++)sum+=gpu[r*cols+j];max_sum_error=fmax(max_sum_error,fabs(sum-1));}
printf("{\"trial\":%d,\"warmup\":%s,\"cpu_wall_seconds\":%.9f,\"cpu_process_seconds\":%.9f,\"gpu_wall_seconds\":%.9f,\"gpu_host_process_seconds\":%.9f,\"gpu_device_seconds\":%.9f,\"max_abs_error\":%.9g,\"relative_l2\":%.9g,\"max_row_sum_error\":%.9g,\"mismatches\":%zu}\n",trial,trial==0?"true":"false",cpu_wall,cpu_process,gpu_wall,gpu_process,gpu_time,max_abs,sqrt(l2error/l2ref),max_sum_error,bad);fflush(stdout);if(bad||max_sum_error>1e-5)return 3;
}
auto transfer_start=Clock::now();double transfer_cpu=cpu_seconds();if(kc_upload(c,input.data()))return 4;printf("{\"upload_wall_seconds\":%.9f,\"upload_host_cpu_seconds\":%.9f,\"private_buffers_bytes\":%zu}\n",std::chrono::duration<double>(Clock::now()-transfer_start).count(),cpu_seconds()-transfer_cpu,input.size()*sizeof(float)*2);
for(int trial=0;trial<4;trial++){auto start=Clock::now();double ct=cpu_seconds(),gpu_time=0;if(kc_run_resident(c,&gpu_time))return 5;double host_cpu=cpu_seconds()-ct;double wall=std::chrono::duration<double>(Clock::now()-start).count();printf("{\"mode\":\"resident\",\"trial\":%d,\"warmup\":%s,\"gpu_wall_seconds\":%.9f,\"gpu_host_process_seconds\":%.9f,\"gpu_device_seconds\":%.9f}\n",trial,trial==0?"true":"false",wall,host_cpu,gpu_time);}
transfer_start=Clock::now();transfer_cpu=cpu_seconds();if(kc_download(c,gpu.data()))return 6;double download_wall=std::chrono::duration<double>(Clock::now()-transfer_start).count(),download_cpu=cpu_seconds()-transfer_cpu;double max_abs=0;size_t bad=0;for(size_t i=0;i<input.size();i++){double delta=fabs(double(cpu[i])-gpu[i]);max_abs=fmax(max_abs,delta);if(!std::isfinite(gpu[i])||delta>1e-6+1e-4*fabs(cpu[i]))bad++;}printf("{\"mode\":\"resident_validation\",\"download_wall_seconds\":%.9f,\"download_host_cpu_seconds\":%.9f,\"max_abs_error\":%.9g,\"mismatches\":%zu}\n",download_wall,download_cpu,max_abs,bad);kc_destroy(c);return bad?7:0;}
