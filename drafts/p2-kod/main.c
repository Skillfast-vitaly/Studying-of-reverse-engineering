#include <stdio.h>
#include <string.h>
#include "cpu.h"

int main(void)
{
    uint32_t r[4];
    char vendor[13];

    // 1. Свой cpuid: имя производителя (как в главе 33)
    my_cpuid(0, r);
    memcpy(vendor + 0, &r[1], 4);   // EBX
    memcpy(vendor + 4, &r[3], 4);   // EDX
    memcpy(vendor + 8, &r[2], 4);   // ECX
    vendor[12] = 0;
    printf("vendor  %s\n", vendor);

    // 2. Свой rdtsc: сколько тактов идёт один printf
    uint64_t t0 = my_rdtsc();
    printf("hello\n");
    uint64_t t1 = my_rdtsc();
    printf("printf  %llu ticks\n", (unsigned long long)(t1 - t0));

    // 3. Снимок регистров
    REGS g;
    snapshot(&g);
    printf("rcx     %016llx\n", (unsigned long long)g.rcx);
    printf("&g      %016llx\n", (unsigned long long)(uintptr_t)&g);
    printf("rsp     %016llx\n", (unsigned long long)g.rsp);
    printf("sizeof  %d\n", (int)sizeof(REGS));
    return 0;
}
