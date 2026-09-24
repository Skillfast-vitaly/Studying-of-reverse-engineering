.intel_syntax noprefix
.text

# uint64_t apply_twice(uint64_t (*fn)(uint64_t), uint64_t x)
# вернуть fn(fn(x))
.globl apply_twice
.seh_proc apply_twice
apply_twice:
    push rbx                    # rbx чужой: сохранить
    .seh_pushreg rbx
    sub  rsp, 32                # 32 байта теневого пространства
    .seh_stackalloc 32
    .seh_endprologue

    mov  rbx, rcx               # fn -> rbx: переживёт вызов
    mov  rcx, rdx               # первый аргумент = x
    call rbx                    # rax = fn(x)
    mov  rcx, rax               # первый аргумент = fn(x)
    call rbx                    # rax = fn(fn(x))

    add  rsp, 32                # вернуть стек
    pop  rbx                    # вернуть rbx как было
    ret
.seh_endproc
