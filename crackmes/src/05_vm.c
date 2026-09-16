/*
 * Crackme 05 — «Виртуальная машина»
 *
 * Уровень:  продвинутый
 * Цель:     понять, что проверка выполняется не процессором, а самодельной
 *           виртуальной машиной, восстановить её систему команд и обратить
 *           преобразование
 * Изучаем:  распознавание диспетчера ВМ (цикл + switch по опкоду),
 *           восстановление набора инструкций, обращение преобразования
 *
 * Это упрощённая модель того, как работают коммерческие протекторы
 * (VMProtect, Themida): настоящая логика превращается в байт-код, а в
 * бинарнике остаётся только интерпретатор. Дизассемблер покажет тебе
 * интерпретатор, а не алгоритм проверки, — алгоритм придётся вытащить
 * из данных.
 */
#include <stdio.h>
#include <string.h>

#include "05_vm_program.h"

enum {
    OP_PUSH = 0x01,   /* PUSH imm8 */
    OP_LOAD = 0x02,   /* LOAD imm8 — байт введённой строки */
    OP_XOR  = 0x03,
    OP_ADD  = 0x04,
    OP_ROTL = 0x05,   /* ROTL imm8 */
    OP_EQ   = 0x06,
    OP_HALT = 0x07
};

#define STACK_SIZE 64

static unsigned char rotl8(unsigned char v, unsigned bits)
{
    bits &= 7;
    if (bits == 0)
        return v;
    return (unsigned char)((v << bits) | (v >> (8 - bits)));
}

/* Диспетчер виртуальной машины. Именно этот цикл ты увидишь в objdump. */
static int vm_run(const unsigned char *input)
{
    unsigned char stack[STACK_SIZE];
    size_t pc = 0;
    int sp = 0;
    int ok = 1;

    while (pc < sizeof VM_PROGRAM) {
        unsigned char op = VM_PROGRAM[pc++];

        switch (op) {
        case OP_PUSH:
            if (sp >= STACK_SIZE) return 0;
            stack[sp++] = VM_PROGRAM[pc++];
            break;

        case OP_LOAD:
            if (sp >= STACK_SIZE) return 0;
            stack[sp++] = input[VM_PROGRAM[pc++]];
            break;

        case OP_XOR: {
            if (sp < 2) return 0;
            unsigned char b = stack[--sp];
            unsigned char a = stack[--sp];
            stack[sp++] = a ^ b;
            break;
        }

        case OP_ADD: {
            if (sp < 2) return 0;
            unsigned char b = stack[--sp];
            unsigned char a = stack[--sp];
            stack[sp++] = (unsigned char)(a + b);
            break;
        }

        case OP_ROTL: {
            if (sp < 1) return 0;
            unsigned char bits = VM_PROGRAM[pc++];
            unsigned char a = stack[--sp];
            stack[sp++] = rotl8(a, bits);
            break;
        }

        case OP_EQ: {
            if (sp < 2) return 0;
            unsigned char b = stack[--sp];
            unsigned char a = stack[--sp];
            if (a != b)
                ok = 0;
            break;
        }

        case OP_HALT:
            return ok;

        default:
            return 0;
        }
    }
    return 0;
}

int main(void)
{
    char buf[64];

    printf("Введите флаг: ");
    fflush(stdout);

    if (!fgets(buf, sizeof buf, stdin))
        return 1;
    buf[strcspn(buf, "\n")] = '\0';

    if (strlen(buf) != FLAG_LEN) {
        puts("[-] Неверно.");
        return 1;
    }

    if (vm_run((const unsigned char *)buf)) {
        puts("[+] Верно. Флаг принят.");
        return 0;
    }

    puts("[-] Неверно.");
    return 1;
}
