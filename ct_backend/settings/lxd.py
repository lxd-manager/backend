import os

LXD_CRT = os.environ.get('LXD_CRT', 'certs/lxd.crt')
LXD_KEY = os.environ.get('LXD_KEY', 'certs/lxd.key')

LXD_CA_CERT = os.environ.get('LXD_CA_CERT', 'certs/fakelerootx1.pem')

if LXD_CA_CERT == 'False':
    LXD_CA_CERT = False
elif LXD_CA_CERT == 'True':
    LXD_CA_CERT = True