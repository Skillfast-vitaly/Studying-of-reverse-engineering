/*
 * Crackme 03 — «Серийный номер»
 *
 * Уровень:  средний
 * Цель:     не найти строку, а ОБРАТИТЬ алгоритм и научиться составлять
 *           верные номера самому
 * Изучаем:  чтение арифметики в ассемблере; деление через умножение на
 *           магическую константу (так в обычной сборке; в `make hard`
 *           компилятор выбрал инструкцию div — глава 18);
 *           переход от «найти пароль» к «понять проверку»
 *
 * Формат серийника: RE-NNNNNNN-C
 *   NNNNNNN — семь цифр
 *   C       — контрольная буква
 */
#include <stdio.h>
#include <string.h>
#include <ctype.h>

#define MAGIC 1337u

static int check_serial(const char *s)
{
    unsigned n = 0;

    if (strlen(s) != 12)          return 0;
    if (s[0] != 'R' || s[1] != 'E' || s[2] != '-') return 0;
    if (s[10] != '-')             return 0;

    for (int i = 3; i < 10; i++) {
        if (!isdigit((unsigned char)s[i])) return 0;
        n = n * 10u + (unsigned)(s[i] - '0');
    }

    /* Условие 1: число должно делиться на магическую константу */
    if (n % MAGIC != 0) return 0;

    /* Условие 2: контрольная буква выводится из частного */
    if (s[11] != (char)('A' + (n / MAGIC) % 26u)) return 0;

    return 1;
}

int main(void)
{
    char buf[64];

    printf("Vvedite seriynyy nomer: ");
    fflush(stdout);

    if (!fgets(buf, sizeof buf, stdin))
        return 1;
    buf[strcspn(buf, "\n")] = '\0';

    if (check_serial(buf)) {
        puts("[+] Seriynyy nomer prinyat.");
        return 0;
    }

    puts("[-] Nevernyy seriynyy nomer.");
    return 1;
}
