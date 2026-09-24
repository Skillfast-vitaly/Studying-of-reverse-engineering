#include <stdio.h>
#include <stdint.h>

uint64_t apply_twice(uint64_t (*fn)(uint64_t), uint64_t x);   // twice.s

uint64_t times10(uint64_t v) { return v * 10; }
uint64_t plus7(uint64_t v)   { return v + 7; }

int main(void)
{
    printf("times10 twice: %llu\n", (unsigned long long)apply_twice(times10, 3));
    printf("plus7 twice:   %llu\n", (unsigned long long)apply_twice(plus7, 3));
    return 0;
}
