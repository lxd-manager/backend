from get_docker_secret import get_docker_secret

keys = get_docker_secret('fernet_keys', default='4TwkXknRnsj3GS6qCd4G3TStQUvqkxrB0eoZyzvZzYpW6MY2Ns 0vbxt28MZsqaKmIgH0YZEeQvfTy5VlbPSWzs0nOua0XrzaBViY').strip()

FERNET_KEYS = list(filter(lambda x: len(x) > 0, keys.split(' ')))
