'''Semantic note timing and tempo of Standard MIDI files, independent of track layout and tick resolution.'''
import struct
from collections import defaultdict, deque


def project(data):
    assert data[:4] == b'MThd' and len(data) >= 14, 'not a Standard MIDI file'
    header = struct.unpack_from('>I', data, 4)[0]
    assert 6 <= header <= len(data) - 8, 'truncated MIDI header'
    fmt, count, division = struct.unpack_from('>HHH', data, 8)
    assert fmt in (0, 1) and count and 0 < division < 0x8000, 'unsupported MIDI timing or format'
    offset = 8 + header
    events = []
    tempos = []
    for track in range(count):
        assert offset + 8 <= len(data) and data[offset:offset + 4] == b'MTrk', 'missing MIDI track'
        size = struct.unpack_from('>I', data, offset + 4)[0]
        offset += 8
        assert offset + size <= len(data), 'truncated MIDI track'
        chunk = data[offset:offset + size]
        offset += size
        position = 0

        def read(n):
            nonlocal position
            assert position + n <= len(chunk), 'truncated MIDI event'
            value = chunk[position:position + n]
            position += n
            return value

        def variable():
            value = 0
            for _ in range(4):
                byte = read(1)[0]
                value = (value << 7) | (byte & 127)
                if byte < 128:
                    return value
            raise AssertionError('invalid MIDI variable length')

        tick = 0
        running = None
        while position < len(chunk):
            tick += variable()
            assert position < len(chunk), 'MIDI event has no status'
            status = chunk[position]
            if status < 128:
                assert running is not None, 'MIDI data has no running status'
                status = running
            else:
                read(1)
                running = status if status < 0xf0 else None
            if status == 0xff:
                kind = read(1)[0]
                payload = read(variable())
                if kind == 0x51:
                    assert len(payload) == 3 and int.from_bytes(payload, 'big'), 'invalid MIDI tempo'
                    tempos.append((round(tick / division, 8), int.from_bytes(payload, 'big')))
            elif status in (0xf0, 0xf7):
                read(variable())
            else:
                command = status & 0xf0
                assert command in range(0x80, 0xf0, 0x10), 'invalid MIDI status'
                payload = read(1 if command in (0xc0, 0xd0) else 2)
                assert all(byte < 128 for byte in payload), 'invalid MIDI event data'
                if command in (0x80, 0x90):
                    events.append((tick, track, status & 15, payload[0], payload[1] if command == 0x90 else 0))
    active = defaultdict(deque)
    notes = []
    for tick, track, channel, key, velocity in sorted(events, key=lambda e: (e[0], e[1])):
        address = (track, channel, key)
        if velocity:
            active[address].append((tick, velocity))
        else:
            assert active[address], 'MIDI note-off has no note-on'
            start, volume = active[address].popleft()
            assert tick > start, 'MIDI note has no positive duration'
            notes.append([round(start / division, 8), round((tick - start) / division, 8), key, volume])
    assert not any(active.values()) and notes, 'MIDI has missing note-offs or no notes'
    tempo_map = sorted(set(tempos)) or [(0.0, 500000)]
    assert len({tick for tick, _ in tempo_map}) == len(tempo_map), 'conflicting MIDI tempos'
    return {'notes': sorted(notes), 'tempos': [[tick, value] for tick, value in tempo_map]}
