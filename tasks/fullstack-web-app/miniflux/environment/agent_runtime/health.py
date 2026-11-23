#!/usr/bin/python3 -I
"""Harbor must test reference readiness with the actual solving identity."""
import os
import pwd


if __name__ == '__main__':
    agent = pwd.getpwnam('agent')
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(agent.pw_gid)
        os.setuid(agent.pw_uid)
    if os.geteuid() != agent.pw_uid:
        raise SystemExit('blackbox-health must run as the solving user agent')
    os.execv('/usr/bin/python3', ['python3', '-I', '-B', '/opt/blackbox/runtime/blackbox_health.py'])
