/*
 * Crackme 01 — «Открытый текст»
 *
 * Уровень:  вводный
 * Цель:     найти пароль, НЕ запуская программу
 * Изучаем:  секцию .rodata, утилиту strings, поиск строк в дизассемблере
 *
 * Пароль лежит в бинарнике как есть. Так выглядит подавляющее большинство
 * «защит» в учебных задачах и, к сожалению, в некоторых реальных программах.
 */
#include <stdio.h>
#include <string.h>

static const char *SECRET = "rev_is_fun_2024";

int main(void)
{
    char buf[64];

    printf("Введите пароль: ");
    fflush(stdout);

    if (!fgets(buf, sizeof buf, stdin))
        return 1;
    buf[strcspn(buf, "\n")] = '\0';

    if (strcmp(buf, SECRET) == 0) {
        puts("[+] Верно. Доступ разрешён.");
        return 0;
    }

    puts("[-] Неверно.");
    return 1;
}
