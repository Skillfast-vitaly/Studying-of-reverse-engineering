# p9_razbor.py — свой разборщик записи трафика для протокола задачи 06.
# Читает файл .pcap (Wireshark: File -> Save As, тип "Wireshark/tcpdump/... - pcap"),
# находит пакеты TCP с портом 7777, собирает поток каждой стороны
# и раскладывает его на кадры: длина (2 байта, порядок сети), тип, данные.
import struct
import sys

PORT = 7777

def packets(path):
    """Отдаёт по одному: байты пакета, начиная с заголовка IP."""
    data = open(path, 'rb').read()
    magic = data[:4]
    if magic in (b'\xd4\xc3\xb2\xa1', b'\x4d\x3c\xb2\xa1'):
        e = '<'                                  # файл записан младшим байтом вперёд
    elif magic in (b'\xa1\xb2\xc3\xd4', b'\xa1\xb2\x3c\x4d'):
        e = '>'
    else:
        sys.exit('eto ne pcap (pcapng nado peresohranit kak pcap)')
    linktype = struct.unpack_from(e + 'I', data, 20)[0]
    pos = 24                                     # заголовок файла — 24 байта
    while pos + 16 <= len(data):
        incl_len = struct.unpack_from(e + 'I', data, pos + 8)[0]
        pkt = data[pos + 16:pos + 16 + incl_len]  # заголовок записи — 16 байт
        pos += 16 + incl_len
        if linktype == 0:                        # Null/Loopback: 4 байта, семейство
            yield pkt[4:]
        elif linktype == 1 and pkt[12:14] == b'\x08\x00':   # Ethernet, внутри IPv4
            yield pkt[14:]

streams = {'C': b'', 'S': b''}                   # что сказал клиент и что сервер
for ip in packets(sys.argv[1]):
    if ip[0] >> 4 != 4 or ip[9] != 6:            # нужен IPv4 и TCP (протокол 6)
        continue
    ihl = (ip[0] & 0x0F) * 4                     # длина заголовка IP
    tcp = ip[ihl:]
    sport, dport = struct.unpack_from('>HH', tcp, 0)
    if PORT not in (sport, dport):
        continue
    doff = (tcp[12] >> 4) * 4                    # длина заголовка TCP
    total = struct.unpack_from('>H', ip, 2)[0]    # длина всего пакета IP
    payload = ip[ihl + doff:total]
    who = 'C' if dport == PORT else 'S'
    print('%5d -> %-5d  flagi %02x  dannyh %3d' % (sport, dport, tcp[13], len(payload)))
    streams[who] += payload

def frames(stream):
    pos = 0
    while pos + 3 <= len(stream):
        length = struct.unpack_from('>H', stream, pos)[0]
        yield stream[pos + 2], stream[pos + 3:pos + 2 + length]
        pos += 2 + length

key = None
print()
for t, d in frames(streams['S']):
    if t == 0x81:
        key = d[0]
for who, name in (('C', 'klient'), ('S', 'server')):
    for t, d in frames(streams[who]):
        if t == 0x81:
            text = 'klyuch 0x%02x, %s' % (d[0], d[1:].decode())
        elif t == 0x82 and key is not None:
            text = bytes(b ^ key for b in d).decode()
        else:
            text = d.hex(' ') if t == 0x02 else d.decode(errors='replace')
        print('%s: tip 0x%02x  %s' % (name, t, text))
