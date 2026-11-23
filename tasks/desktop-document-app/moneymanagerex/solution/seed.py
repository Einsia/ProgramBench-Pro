#!/usr/bin/env python3
"""First-run settings of the reference installation (the product's own settings file, mmexini.db3).

The product asks for usage statistics on its first start, looks for updates and news online and shows random money
tips below its lists. The answers are written once, into the private settings file, before the first start; nothing is
changed afterwards.
"""
import pathlib
import sqlite3
import sys

path = pathlib.Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
if not path.exists():
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE SETTING_V1(SETTINGID integer not null primary key, '
               'SETTINGNAME TEXT COLLATE NOCASE NOT NULL UNIQUE, SETTINGVALUE TEXT)')
    db.executemany('INSERT INTO SETTING_V1(SETTINGNAME, SETTINGVALUE) VALUES (?, ?)',
                   [('SENDUSAGESTATS', 'FALSE'), ('UPDATECHECK', 'FALSE'), ('CHECKNEWS', 'FALSE'),
                    ('IGNORE_SHOW_MONEYTIPS', 'FALSE')])
    db.commit()
    db.close()
