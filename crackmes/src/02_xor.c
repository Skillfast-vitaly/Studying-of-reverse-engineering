/*
 * Crackme 02 — «XOR»
 *
 * Уровень:  начальный
 * Цель:     найти пароль статическим анализом
 * Изучаем:  почему поиск строк перестаёт работать; чтение .rdata в hex;
 *           распознавание однобайтового XOR в дизассемблере
 *
 * Пароль хранится зашифрованным. Ключ лежит рядом — в коде функции
 * расшифровки. Это классическая «защита через запутывание»: она не добавляет
 * стойкости, а лишь заставляет открыть дизассемблер.
 */
#include <stdio.h>
#include <string.h>

/* Зашифрованный пароль. Поиск строк этого уже не покажет. */
static const unsigned char ENC[] = {
    0x22, 0x35, 0x28, 0x05, 0x32, 0x33, 0x3e, 0x3f, 0x29,
    0x05, 0x34, 0x35, 0x2e, 0x32, 0x33, 0x34, 0x3d
};

#define KEY 0x5A

/* Расшифровка «на лету»: открытый пароль ни секунды не лежит в файле,
 * но появляется в памяти процесса — запомни это, пригодится в notes/06. */
static void decrypt(char *out, size_t n)
{
    for (size_t i = 0; i < n; i++)
        out[i] = (char)(ENC[i] ^ KEY);
    out[n] = '\0';
}

int main(void)
{
    char buf[64];
    char secret[sizeof ENC + 1];

    printf("Vvedite parol: ");
    fflush(stdout);

    if (!fgets(buf, sizeof buf, stdin))
        return 1;
    buf[strcspn(buf, "\n")] = '\0';

    decrypt(secret, sizeof ENC);

    if (strcmp(buf, secret) == 0) {
        puts("[+] Verno. Dostup razreshon.");
        return 0;
    }

    puts("[-] Neverno.");
    return 1;
}
