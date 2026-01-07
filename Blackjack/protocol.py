import struct

UDP_PORT = 13122 #client port
MAGIC_COOKIE = 0xabcddcba #magic cookie
MSG_TYPE_OFFER = 0x2 #offer
MSG_TYPE_REQUEST = 0x3 #request
MSG_TYPE_PAYLOAD = 0x4 #payload

#offer: big endian, unsigned int(4), unsigned char(1), unsigned short(2), char(32)
FORMAT_OFFER = '!IBH32s' 
#request: big endian,Cookie(4), Type(1), Rounds(1), Name(32)
FORMAT_REQUEST = '!IBB32s'
FORMAT_PAYLOAD_CLIENT = '!IB5s'
FORMAT_PAYLOAD_SERVER = '!IBBHB'

#game results
RESULT_PLAYING = 0x0
RESULT_TIE = 0x1
RESULT_LOSS = 0x2
RESULT_WIN = 0x3

def pad_string(text, length=32):
    return text.encode('utf-8')[:length].ljust(length, b'\x00')