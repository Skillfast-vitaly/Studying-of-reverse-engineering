/*
 * Crackme 04 — «Сопротивление отладчику»
 *
 * Уровень:  средний
 * Цель:     пройти проверку, несмотря на защиту от отладки
 * Изучаем:  ptrace(PTRACE_TRACEME), /proc/self/status → TracerPid,
 *           почему «просто пропатчить if» здесь не сработает
 *
 * ВАЖНАЯ ИДЕЯ: программа не ругается «обнаружен отладчик». Она молча
 * портит ключ расшифровки. Под gdb правильный пароль НЕ подойдёт, и это
 * выглядит так, будто ты ошибся паролем. Такая «тихая» защита встречается
 * в реальном софте и специально сбивает с толку.
 */
#include <stdio.h>
#include <string.h>
#include <sys/ptrace.h>

static const unsigned char ENC[] = {
    0x4c, 0x48, 0x4e, 0x5d, 0x5f, 0x59, 0x63, 0x55, 0x4f, 0x63,
    0x52, 0x53, 0x48, 0x63, 0x59, 0x52, 0x53, 0x49, 0x5b, 0x54
};

/* Приём 1: процесс может быть трассируем только ОДНИМ трассировщиком.
 * Если под нами уже сидит gdb — PTRACE_TRACEME вернёт -1. */
static int check_traceme(void)
{
    return ptrace(PTRACE_TRACEME, 0, NULL, NULL) == -1;
}

/* Приём 2: ядро само раскрывает трассировщика в /proc/self/status. */
static int check_tracerpid(void)
{
    FILE *f = fopen("/proc/self/status", "r");
    char line[256];
    int pid = 0;

    if (!f)
        return 0;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "TracerPid:\t%d", &pid) == 1)
            break;
    }
    fclose(f);
    return pid != 0;
}

int main(void)
{
    char buf[64];
    char secret[sizeof ENC + 1];
    unsigned char key = 0x3C;

    /* Ключ портится, а не ветвление. Патчить надо здесь.
     *
     * Порядок проверок важен: PTRACE_TRACEME делает нашего РОДИТЕЛЯ
     * трассировщиком, после чего TracerPid в /proc/self/status станет
     * ненулевым даже без отладчика. Поэтому сначала читаем TracerPid,
     * и только потом вызываем TRACEME. */
    if (check_tracerpid())
        key ^= 0x22;
    if (check_traceme())
        key ^= 0x11;

    printf("Введите пароль: ");
    fflush(stdout);

    if (!fgets(buf, sizeof buf, stdin))
        return 1;
    buf[strcspn(buf, "\n")] = '\0';

    for (size_t i = 0; i < sizeof ENC; i++)
        secret[i] = (char)(ENC[i] ^ key);
    secret[sizeof ENC] = '\0';

    if (strcmp(buf, secret) == 0) {
        puts("[+] Верно. Доступ разрешён.");
        return 0;
    }

    puts("[-] Неверно.");
    return 1;
}
