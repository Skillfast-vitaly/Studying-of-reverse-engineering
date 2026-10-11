/*
 * Задача 06 — «Протокол без описания» (клиент)
 *
 * Официальный клиент к серверу 06_proto_server.exe: здоровается,
 * задаёт два вопроса и прощается. Описания протокола нет — только
 * эта программа, сервер и трафик между ними (приложение П9).
 *
 * Сначала запусти сервер, потом клиент. Сборка в w64devkit:
 *   gcc -O0 -Wall -o 06_proto_client.exe 06_proto_client.c -lws2_32
 */
#include <winsock2.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#define PORT     7777
#define MAX_DATA 255

static int recv_all(SOCKET s, uint8_t *buf, int n)
{
    int got = 0;
    while (got < n) {
        int r = recv(s, (char *)buf + got, n - got, 0);
        if (r <= 0)
            return 0;
        got += r;
    }
    return 1;
}

static int send_frame(SOCKET s, uint8_t type, const uint8_t *data, int n)
{
    uint8_t frame[3 + MAX_DATA];
    uint16_t len = htons((uint16_t)(n + 1));
    memcpy(frame, &len, 2);
    frame[2] = type;
    if (n > 0)
        memcpy(frame + 3, data, n);
    return send(s, (const char *)frame, n + 3, 0) == n + 3;
}

/* Читает один кадр: тип в *type, данные в data, их число в *n. */
static int read_frame(SOCKET s, uint8_t *type, uint8_t *data, int *n)
{
    uint8_t hdr[3];
    if (!recv_all(s, hdr, 3))
        return 0;
    uint16_t len;
    memcpy(&len, hdr, 2);
    len = ntohs(len);
    if (len == 0 || len - 1 > MAX_DATA)
        return 0;
    *type = hdr[2];
    *n = len - 1;
    return recv_all(s, data, *n);
}

int main(void)
{
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        printf("WSAStartup: oshibka\n");
        return 1;
    }

    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    if (s == INVALID_SOCKET ||
        connect(s, (struct sockaddr *)&addr, sizeof addr) == SOCKET_ERROR) {
        printf("Net svyazi s serverom. Snachala zapusti 06_proto_server.exe\n");
        return 1;
    }

    uint8_t type, data[MAX_DATA + 1];
    int n;

    const char *name = "p9cli/1.0";
    send_frame(s, 0x01, (const uint8_t *)name, (int)strlen(name));
    if (!read_frame(s, &type, data, &n) || type != 0x81 || n < 1) {
        printf("Server otvetil ne tak\n");
        return 1;
    }
    uint8_t key = data[0];
    printf("%.*s\n", n - 1, (const char *)data + 1);

    for (uint8_t q = 1; q <= 2; q++) {
        send_frame(s, 0x02, &q, 1);
        if (!read_frame(s, &type, data, &n))
            return 1;
        for (int i = 0; i < n; i++)
            data[i] ^= key;
        printf("Otvet na vopros %d: %.*s\n", q, n, (const char *)data);
    }

    send_frame(s, 0x03, NULL, 0);
    if (read_frame(s, &type, data, &n))
        printf("%.*s\n", n, (const char *)data);

    closesocket(s);
    WSACleanup();
    return 0;
}
