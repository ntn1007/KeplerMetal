#include <stdio.h>
int main(void) {
    volatile unsigned a = 17, b = 23;
    unsigned sum = a + b;
    printf("{\"native_cpu_execution\":true,\"sum\":%u}\n", sum);
    return sum == 40 ? 0 : 1;
}
