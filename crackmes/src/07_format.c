/*
 * Задача 07 — «Формат файла без описания»
 *
 * Уровень:  средний
 * Цель:     по байтам файла и по машинному коду восстановить формат
 *           и написать свою программу, файлы которой эта примет
 * Изучаем:  разбор двоичного файла, числа младшим байтом вперёд,
 *           длина перед строкой, контрольная сумма и её формула в коде
 *
 * Программа ведёт таблицу рекордов в файле rekordy.dat в текущей папке.
 * Других файлов она не трогает и в сеть не ходит.
 *
 *   07_format.exe add IMYA OCHKI   — добавить запись
 *   07_format.exe list             — показать таблицу
 *
 * Сборка в w64devkit:  gcc -O0 -Wall -o 07_format.exe 07_format.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define FILE_NAME   "rekordy.dat"
#define MAX_RECORDS 50
#define MAX_NAME    32

struct record {
    char name[MAX_NAME + 1];
    uint32_t score;
};

static struct record table[MAX_RECORDS];
static int count;

static uint32_t checksum(const uint8_t *data, size_t n)
{
    uint32_t h = 0;
    for (size_t i = 0; i < n; i++)
        h = h * 31 + data[i];
    return h;
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void wr32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

/* 1 — прочитано, 0 — файла нет, -1 — файл испорчен */
static int load(void)
{
    static uint8_t buf[8 + MAX_RECORDS * (1 + MAX_NAME + 4) + 4];
    FILE *f = fopen(FILE_NAME, "rb");
    if (f == NULL)
        return 0;
    size_t n = fread(buf, 1, sizeof buf, f);
    fclose(f);

    if (n < 12 || memcmp(buf, "RKD1", 4) != 0)
        return -1;
    if (buf[4] != 1 || buf[5] != 0)                 /* версия 1 */
        return -1;
    int c = buf[6] | buf[7] << 8;
    if (c > MAX_RECORDS)
        return -1;
    if (checksum(buf, n - 4) != rd32(buf + n - 4))
        return -1;

    size_t pos = 8;
    for (int i = 0; i < c; i++) {
        if (pos >= n - 4)
            return -1;
        int len = buf[pos++];
        if (len == 0 || len > MAX_NAME || pos + len + 4 > n - 4)
            return -1;
        memcpy(table[i].name, buf + pos, len);
        table[i].name[len] = '\0';
        pos += len;
        table[i].score = rd32(buf + pos);
        pos += 4;
    }
    if (pos != n - 4)
        return -1;
    count = c;
    return 1;
}

static int save(void)
{
    static uint8_t buf[8 + MAX_RECORDS * (1 + MAX_NAME + 4) + 4];
    memcpy(buf, "RKD1", 4);
    buf[4] = 1; buf[5] = 0;
    buf[6] = (uint8_t)count; buf[7] = (uint8_t)(count >> 8);
    size_t pos = 8;
    for (int i = 0; i < count; i++) {
        size_t len = strlen(table[i].name);
        buf[pos++] = (uint8_t)len;
        memcpy(buf + pos, table[i].name, len);
        pos += len;
        wr32(buf + pos, table[i].score);
        pos += 4;
    }
    wr32(buf + pos, checksum(buf, pos));
    pos += 4;

    FILE *f = fopen(FILE_NAME, "wb");
    if (f == NULL)
        return 0;
    size_t w = fwrite(buf, 1, pos, f);
    fclose(f);
    return w == pos;
}

int main(int argc, char **argv)
{
    int st = load();
    if (st < 0) {
        printf("Fajl %s isporchen, otkazyvayus ego chitat\n", FILE_NAME);
        return 1;
    }

    if (argc == 2 && strcmp(argv[1], "list") == 0) {
        if (count == 0)
            printf("Tablica pusta\n");
        for (int i = 0; i < count; i++)
            printf("%2d. %-*s %u\n", i + 1, MAX_NAME, table[i].name, (unsigned)table[i].score);
        return 0;
    }

    if (argc == 4 && strcmp(argv[1], "add") == 0) {
        size_t len = strlen(argv[2]);
        if (len == 0 || len > MAX_NAME) {
            printf("Imya ot 1 do %d bukv\n", MAX_NAME);
            return 1;
        }
        if (count >= MAX_RECORDS) {
            printf("Tablica polna\n");
            return 1;
        }
        strcpy(table[count].name, argv[2]);
        table[count].score = (uint32_t)strtoul(argv[3], NULL, 10);
        count++;
        if (!save()) {
            printf("Ne mogu zapisat %s\n", FILE_NAME);
            return 1;
        }
        printf("Zapisano. Zapisej: %d\n", count);
        return 0;
    }

    printf("Ispolzovanie:\n  07_format add IMYA OCHKI\n  07_format list\n");
    return 1;
}
