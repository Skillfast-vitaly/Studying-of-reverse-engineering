// cpu.h — наши функции на ассемблере (живут в cpu.s)
#pragma once
#include <stdint.h>

// Снимок регистров общего назначения — в том порядке,
// в котором их сохраняет snapshot()
typedef struct {
    uint64_t rax, rcx, rdx, rbx, rsp, rbp, rsi, rdi;
    uint64_t r8,  r9,  r10, r11, r12, r13, r14, r15;
} REGS;

void     my_cpuid(uint32_t leaf, uint32_t out[4]); // EAX, EBX, ECX, EDX
uint64_t my_rdtsc(void);                           // счётчик тактов
void     snapshot(REGS *out);                      // все 16 регистров
