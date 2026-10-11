/*
 * Задача 06 — «Протокол без описания» (сервер)
 *
 * Уровень:  средний
 * Цель:     по трафику и машинному коду восстановить протокол и написать
 *           свой клиент — такой, который спросит то, чего наш не спрашивает
 * Изучаем:  кадры поверх TCP, порядок байтов в сети, разбор сообщения
 *           после recv, switch по типу сообщения, ключ сессии и XOR
 *
 * Сервер слушает только 127.0.0.1 — адрес «сам себе». Из сети к нему
 * не подключиться: весь разговор идёт внутри твоего ПК (приложение П9).
 * Клиентов обслуживает по одному, пока не нажмёшь Ctrl+C.
 *
 * Сборка в w64devkit:
 *   gcc -O0 -Wall -o 06_proto_server.exe 06_proto_server.c -lws2_32
 */
#include <winsock2.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#define PORT     7777
#define MAX_DATA 255

/* Каждое сообщение — «кадр»: 2 байта длины в порядке байтов сети
 * (старший байт первым), 1 байт типа, потом данные. Длина считает
 * байт типа и данные. */
enum {
    T_HELLO   = 0x01,   /* клиент: своё имя */
    T_ASK     = 0x02,   /* клиент: номер вопроса, 1 байт */
    T_BYE     = 0x03,   /* клиент: прощается */
    T_WELCOME = 0x81,   /* сервер: ключ сессии (1 байт) и приветствие */
    T_ANSWER  = 0x82,   /* сервер: ответ, зашифрованный XOR с ключом */
    T_BYE_OK  = 0x83,   /* сервер: прощается */
    T_ERROR   = 0xEE    /* сервер: не понял */
};

/* recv может вернуть меньше, чем просили: TCP — поток байтов,
 * а не сообщения. Поэтому читаем в цикле, пока не наберём n байт. */
static int recv_all(SOCKET s, uint8_t *buf, int n)
{
    int got = 0;
    while (got < n) {
        int r = recv(s, (char *)buf + got, n - got, 0);
        if (r <= 0)
            return 0;               /* клиент ушёл или ошибка */
        got += r;
    }
    return 1;
}

static int send_frame(SOCKET s, uint8_t type, const uint8_t *data, int n)
{
    uint8_t frame[3 + MAX_DATA];
    uint16_t len = htons((uint16_t)(n + 1));    /* в сеть — старший байт первым */
    memcpy(frame, &len, 2);
    frame[2] = type;
    if (n > 0)
        memcpy(frame + 3, data, n);
    return send(s, (const char *)frame, n + 3, 0) == n + 3;
}

static const char *answer_for(uint8_t question)
{
    switch (question) {
    case 1:  return "Pogoda: yasno, +5";
    case 2:  return "Fakt dnya: TCP ne znaet granic soobshchenij";
    case 3:  return "Ty nashel skrytyj vopros! Kod: P9-OK";
    default: return NULL;
    }
}

/* Один клиент: читаем кадры, пока он не попрощается или не уйдёт. */
static void serve(SOCKET s, uint8_t key)
{
    uint8_t hdr[3], data[MAX_DATA], out[MAX_DATA];

    for (;;) {
        if (!recv_all(s, hdr, 3))
            return;
        uint16_t len;
        memcpy(&len, hdr, 2);
        len = ntohs(len);
        /* Всё, что пришло из сети, — враг, пока не проверено:
         * длина не может быть нулём и не может быть больше буфера. */
        if (len == 0 || len - 1 > MAX_DATA)
            return;
        int n = len - 1;
        if (!recv_all(s, data, n))
            return;

        switch (hdr[2]) {
        case T_HELLO: {
            if (n > 64)
                n = 64;
            printf("[server] klient predstavilsya: %.*s, klyuch sessii 0x%02X\n",
                   n, (const char *)data, key);
            out[0] = key;
            int m = snprintf((char *)out + 1, MAX_DATA - 1, "Privet, %.*s!",
                             n, (const char *)data);
            send_frame(s, T_WELCOME, out, 1 + m);
            break;
        }
        case T_ASK: {
            const char *ans = (n == 1) ? answer_for(data[0]) : NULL;
            if (ans == NULL) {
                printf("[server] neponyatnyj vopros\n");
                send_frame(s, T_ERROR, (const uint8_t *)"Net takogo voprosa", 18);
                break;
            }
            printf("[server] vopros %d\n", data[0]);
            int m = (int)strlen(ans);
            for (int i = 0; i < m; i++)
                out[i] = (uint8_t)(ans[i] ^ key);
            send_frame(s, T_ANSWER, out, m);
            break;
        }
        case T_BYE:
            /* Отвечаем и ждём, пока клиент сам закроет соединение:
             * следующий recv вернёт 0, и цикл кончится. */
            printf("[server] klient poproshchalsya\n");
            send_frame(s, T_BYE_OK, (const uint8_t *)"Poka!", 5);
            break;
        default:
            printf("[server] neizvestnyj tip 0x%02X\n", hdr[2]);
            send_frame(s, T_ERROR, (const uint8_t *)"Ne ponyal", 9);
            break;
        }
    }
}

int main(void)
{
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        printf("WSAStartup: oshibka\n");
        return 1;
    }

    SOCKET ls = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);      /* 127.0.0.1 */

    if (ls == INVALID_SOCKET ||
        bind(ls, (struct sockaddr *)&addr, sizeof addr) == SOCKET_ERROR ||
        listen(ls, 1) == SOCKET_ERROR) {
        printf("Ne mogu zanyat port %d, oshibka %d\n", PORT, WSAGetLastError());
        return 1;
    }
    printf("Server zhdet na 127.0.0.1:%d (Ctrl+C - vyhod)\n", PORT);
    fflush(stdout);

    for (uint8_t session = 0; ; session++) {
        SOCKET s = accept(ls, NULL, NULL);
        if (s == INVALID_SOCKET)
            continue;
        serve(s, (uint8_t)(0x5A + 0x11 * session));
        closesocket(s);
        fflush(stdout);
    }
}
