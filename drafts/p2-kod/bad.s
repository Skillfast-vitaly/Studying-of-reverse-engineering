.intel_syntax noprefix
.text

# void bad_cpuid(uint32_t leaf, uint32_t out[4]) — ОШИБКА: rbx не сохранён
.globl bad_cpuid
bad_cpuid:
    mov  r8, rdx
    mov  eax, ecx
    xor  ecx, ecx
    cpuid
    mov  [r8],      eax
    mov  [r8 + 4],  ebx
    mov  [r8 + 8],  ecx
    mov  [r8 + 12], edx
    ret
