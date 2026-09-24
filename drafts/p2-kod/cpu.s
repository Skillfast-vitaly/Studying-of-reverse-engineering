.intel_syntax noprefix
.text

# void my_cpuid(uint32_t leaf, uint32_t out[4])
#   rcx = leaf, rdx = out
.globl my_cpuid
.seh_proc my_cpuid
my_cpuid:
    push rbx                    # cpuid портит rbx, а он чужой
    .seh_pushreg rbx
    .seh_endprologue
    mov  r8, rdx                # out -> r8: cpuid затрёт rdx
    mov  eax, ecx               # номер листа -> eax
    xor  ecx, ecx               # подлист 0
    cpuid                       # ответ в eax, ebx, ecx, edx
    mov  [r8],      eax         # out[0]
    mov  [r8 + 4],  ebx         # out[1]
    mov  [r8 + 8],  ecx         # out[2]
    mov  [r8 + 12], edx         # out[3]
    pop  rbx
    ret
.seh_endproc

# uint64_t my_rdtsc(void)
.globl my_rdtsc
my_rdtsc:
    rdtsc                       # edx:eax = счётчик
    shl  rdx, 32                # старшая половина вверх
    or   rax, rdx               # склеить в rax
    ret

# void snapshot(REGS *out)
#   rcx = out
.globl snapshot
snapshot:
    mov  [rcx + 0x00], rax
    mov  [rcx + 0x08], rcx
    mov  [rcx + 0x10], rdx
    mov  [rcx + 0x18], rbx
    lea  rax, [rsp + 8]         # rsp до call (без адреса возврата)
    mov  [rcx + 0x20], rax
    mov  [rcx + 0x28], rbp
    mov  [rcx + 0x30], rsi
    mov  [rcx + 0x38], rdi
    mov  [rcx + 0x40], r8
    mov  [rcx + 0x48], r9
    mov  [rcx + 0x50], r10
    mov  [rcx + 0x58], r11
    mov  [rcx + 0x60], r12
    mov  [rcx + 0x68], r13
    mov  [rcx + 0x70], r14
    mov  [rcx + 0x78], r15
    ret
