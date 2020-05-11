import os
import subprocess
import tempfile


def gen_keys():
    with tempfile.TemporaryDirectory(prefix='generate-cloud-init-ssh-host-keys') as temp_folder_name:
        def generate_keys(key_type):
            private_key_filename = os.path.join(temp_folder_name, key_type)
            subprocess.check_call(['ssh-keygen', '-q', '-N', '', '-t', key_type, '-f', private_key_filename])
            public_key_filename = '%s.pub' % private_key_filename

            with open(private_key_filename, 'rt') as private_key_file:
                private_key = private_key_file.read()
            with open(public_key_filename, 'rt') as public_key_file:
                public_key = public_key_file.read()

            return (private_key, public_key)

        keys = {}

        for key_type in ['ecdsa', 'ed25519', 'rsa']:
            keys[key_type] = generate_keys(key_type)

    return keys
