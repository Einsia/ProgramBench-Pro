"""Independent SQLCipher 4 document decoding; checks encryption, HMAC and password."""
import hashlib
import hmac
import struct


def decrypt(data, password):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    page_size, reserved = 4096, 80
    if len(data) < page_size or len(data) % page_size or data.startswith(b'SQLite format 3\0'):
        raise AssertionError('not a complete encrypted database')
    salt = data[:16]
    key = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, 256000, 32)
    mac_key = hashlib.pbkdf2_hmac('sha512', key, bytes(b ^ 0x3a for b in salt), 2, 32)
    output = bytearray()
    for index, offset in enumerate(range(0, len(data), page_size), 1):
        page = data[offset:offset + page_size]
        start = 16 if index == 1 else 0
        ciphertext = page[start:page_size-reserved]
        iv = page[page_size-reserved:page_size-reserved+16]
        wanted = hmac.new(mac_key, ciphertext + iv + struct.pack('<I',index), hashlib.sha512).digest()
        if not hmac.compare_digest(wanted, page[-64:]):
            raise AssertionError('encrypted page authentication failed for this password')
        decoder = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        clear = decoder.update(ciphertext) + decoder.finalize()
        output.extend((b'SQLite format 3\0' if index==1 else b'') + clear + bytes(reserved))
    if output[16:18] != b'\x10\x00' or output[20] != reserved:
        raise AssertionError('decrypted database header is invalid')
    return bytes(output)
