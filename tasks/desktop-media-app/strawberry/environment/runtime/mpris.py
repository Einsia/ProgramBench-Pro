"""One bounded request to the driven application's real MPRIS2 service."""
import json
import sys
from gi.repository import Gio, GLib


def main():
    request = json.loads(sys.stdin.read())
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    iface = request['interface']
    action = request['action']
    member = request.get('member')
    if action == 'get':
        method, signature, args = 'Get', '(ss)', [iface, member]
        iface = 'org.freedesktop.DBus.Properties'
    elif action == 'get_all':
        method, signature, args = 'GetAll', '(s)', [iface]
        iface = 'org.freedesktop.DBus.Properties'
    elif action == 'set':
        method, signature = 'Set', '(ssv)'
        args = [iface, member, GLib.Variant(request['value_type'], request['value'])]
        iface = 'org.freedesktop.DBus.Properties'
    else:
        method, signature, args = member, request['signature'], request.get('args', [])
    try:
        reply = bus.call_sync('org.mpris.MediaPlayer2.strawberry', '/org/mpris/MediaPlayer2', iface, method,
                              GLib.Variant(signature, tuple(args)), None, Gio.DBusCallFlags.NONE, 15000, None)
        value = reply.unpack()
        print(json.dumps({'ok': True, 'value': value[0] if len(value) == 1 else list(value)}, ensure_ascii=False))
    except GLib.Error as error:
        name = Gio.DBusError.get_remote_error(error) or 'DBusError'
        print(json.dumps({'ok': False, 'error': name, 'message': str(error)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
