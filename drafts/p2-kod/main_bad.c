#include <stdio.h>
#include <stdint.h>

void bad_cpuid(uint32_t leaf, uint32_t out[4]);   // bad.s

int main(void)
{
    uint32_t r[4];
    for (int i = 0; i < 3; i++) {
        bad_cpuid(0, r);
        printf("i = %d\n", i);
    }
    printf("done\n");
    return 0;
}
