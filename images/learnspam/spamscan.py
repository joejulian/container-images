#!/usr/bin/env python

from imaplib import IMAP4, IMAP4_SSL

import email
import os
import subprocess
import sys

VERSION = "0.1.0"


if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print(VERSION)
    sys.exit(0)


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1", "on")

admin_user = os.getenv('SPAMSCAN_USER')
if admin_user is None:
    print("missing environment variable, SPAMSCAN_USER")
    sys.exit(1)

admin_pass = os.getenv('SPAMSCAN_PASSWORD')
if admin_pass is None:
    print("missing environment variable, SPAMSCAN_PASSWORD")
    sys.exit(1)

imap_host  = os.getenv('SPAMSCAN_HOST', default='imap')
rspamd_controller  = os.getenv('SPAMSCAN_RSPAMD_CONTROLLER', default='rspamd-controller')
rspamd_password = os.getenv('SPAMSCAN_RSPAMD_PASSWORD', default='rspamd-password')
use_ssl = str2bool(os.getenv('SPAMSCAN_USE_SSL', default='false'))
use_tls = str2bool(os.getenv('SPAMSCAN_USE_TLS', default='true'))

paths = {
        "spam": '*/Learn/Spam',
        "ham":  '*/Learn/Ham'
        }

try:
    if use_ssl:
        imap = IMAP4_SSL(imap_host)
    else:
        imap = IMAP4(imap_host)
except Exception as err:
    print("error establishing imap connection to {}: {}".format(imap_host, err))
    sys.exit(1)

if use_tls:
    imap.starttls()

try:
    imap.login(admin_user, admin_pass)
except Exception as err:
    print("failed to log in to imap: {}", err)
    sys.exit(1)

for etype in paths.keys():
    imap_list = imap.list(paths[etype])
    if imap_list[1] is None:
        continue

    for mail in imap_list[1]:
        try:
            mail = mail.decode('latin-1').split(' ')[-1]
            result = imap.select(mail)
        except Exception as err:
            print("failed to get list of {} folders from {}: {}".format(etype, mail, err))
            continue
        if result[0] == 'OK':
            try:
                typ, data = imap.search(None, 'ALL')
            except:
                continue
            for num in data[0].split():
                msgtype, msgdata = imap.fetch(num, '(RFC822)')
                # rspamc -h rspamd-controller -c [spam,ham] -v -P rspamd-password
                message_id = email.message_from_bytes(msgdata[0][1]).get('message-id')
                if message_id:
                    print('Learning {} from {}'.format(etype, message_id))
                rspamc = subprocess.Popen(
                        ['rspamc', '-h', rspamd_controller, '-P', rspamd_password, '-v', 'learn_'+etype],
                        stdin = subprocess.PIPE,
                        stdout = subprocess.PIPE)
                rspamc.stdin.write(msgdata[0][1])
                out = rspamc.communicate()
                print(out[0].decode("utf-8"))
                imap.store(num, '+FLAGS', '\\Deleted')
            imap.expunge()
        else:
            print('Opening {0} failed: {1}'.format(mail, result[1][0].decode('latin-1')))

rspamc = subprocess.Popen(
        ['rspamc', '-h', rspamd_controller, '-P', rspamd_password, '-v', 'stat'],
        stdin = subprocess.PIPE,
        stdout = subprocess.PIPE)
out = rspamc.communicate()
print(out[0].decode("utf-8"))
