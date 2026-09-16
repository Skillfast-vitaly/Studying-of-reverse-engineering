#!/usr/bin/env python3
"""
Генератор байт-кода для crackme 05 (виртуальная машина).

Держим его в репозитории, чтобы было видно: в байт-коде нет магии, он
собирается из простого преобразования. Когда будешь решать задачу —
сюда не подглядывай, это фактически спойлер.

Запуск:  python3 tools/gen_vm_program.py > crackmes/src/05_vm_program.h
"""

PASSWORD = b"vm_obfuscation"

OP_PUSH = 0x01  # PUSH imm8      — положить константу на стек
OP_LOAD = 0x02  # LOAD imm8      — положить input[imm8] на стек
OP_XOR  = 0x03  # XOR            — b=pop, a=pop, push a^b
OP_ADD  = 0x04  # ADD            — b=pop, a=pop, push (a+b)&0xff
OP_ROTL = 0x05  # ROTL imm8      — a=pop, push циклический сдвиг влево
OP_EQ   = 0x06  # EQ             — b=pop, a=pop, если a!=b сбросить флаг ok
OP_HALT = 0x07  # HALT           — стоп

XOR_CONST = 0xA5
ROT_BITS = 3


def rotl8(value: int, bits: int) -> int:
    value &= 0xFF
    return ((value << bits) | (value >> (8 - bits))) & 0xFF


def transform(char_code: int, index: int) -> int:
    """Ровно то же, что делает байт-код: (c + i + 1) -> rotl 3 -> xor 0xA5."""
    return rotl8((char_code + index + 1) & 0xFF, ROT_BITS) ^ XOR_CONST


def build_program(password: bytes) -> list[int]:
    program: list[int] = []
    for i, ch in enumerate(password):
        program += [OP_LOAD, i]
        program += [OP_PUSH, (i + 1) & 0xFF]
        program += [OP_ADD]
        program += [OP_ROTL, ROT_BITS]
        program += [OP_PUSH, XOR_CONST]
        program += [OP_XOR]
        program += [OP_PUSH, transform(ch, i)]
        program += [OP_EQ]
    program += [OP_HALT]
    return program


def main() -> None:
    program = build_program(PASSWORD)

    print("/* Сгенерировано tools/gen_vm_program.py — не править вручную. */")
    print("#ifndef VM_PROGRAM_H")
    print("#define VM_PROGRAM_H")
    print()
    print(f"#define FLAG_LEN {len(PASSWORD)}")
    print()
    print("static const unsigned char VM_PROGRAM[] = {")
    for offset in range(0, len(program), 12):
        chunk = program[offset:offset + 12]
        print("    " + ", ".join(f"0x{b:02x}" for b in chunk) + ",")
    print("};")
    print()
    print("#endif /* VM_PROGRAM_H */")


if __name__ == "__main__":
    main()
