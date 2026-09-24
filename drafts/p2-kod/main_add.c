#include <stdio.h>
#include <stdint.h>

uint64_t add3(uint64_t a, uint64_t b, uint64_t c);   // живёт в add.s

int main(void)
{
    uint64_t r = add3(1, 20, 300);
    printf("add3(1, 20, 300) = %llu\n", (unsigned long long)r);
    return 0;
}
