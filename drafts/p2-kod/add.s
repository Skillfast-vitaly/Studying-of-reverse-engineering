.intel_syntax noprefix          # синтаксис Intel, как в x64dbg
.text                           # дальше идёт код

.globl add3                     # имя видно другим файлам
add3:                           # uint64_t add3(a, b, c)
    mov  rax, rcx               # rax = a
    add  rax, rdx               # rax = a + b
    add  rax, r8                # rax = a + b + c
    ret                         # ответ уже в rax
