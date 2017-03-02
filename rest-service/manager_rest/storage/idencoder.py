from .. import config


class IDEncoder(object):

    def __init__(self):
        if not config.instance.security_encoding_alphabet:
            config.instance.load_configuration()
        self._alphabet = config.instance.security_encoding_alphabet
        self._block_size = config.instance.security_encoding_block_size
        self._min_length = config.instance.security_encoding_min_length
        if len(set(self._alphabet)) < 2:
            raise AttributeError('Alphabet must contain at least 2 chars.')
        self.alphabet = self._alphabet
        self.block_size = self._block_size
        self.mask = (1 << self._block_size) - 1
        self.mapping = range(self._block_size)

    def encode(self, n, min_length=None):
        n += 1  # handle `0` as input
        min_length = min_length if min_length else self._min_length
        return self.enbase(self.encode_num(n), min_length)

    def decode(self, n):
        decoded_id = self.decode_num(self.debase(n))
        return decoded_id - 1

    def encode_num(self, n):
        return (n & ~self.mask) | self._encode_num(n & self.mask)

    def _encode_num(self, n):
        result = 0
        for i, b in enumerate(reversed(self.mapping)):
            if n & (1 << i):
                result |= (1 << b)
        return result

    def decode_num(self, n):
        return (n & ~self.mask) | self._decode_num(n & self.mask)

    def _decode_num(self, n):
        result = 0
        for i, b in enumerate(reversed(self.mapping)):
            if n & (1 << b):
                result |= (1 << i)
        return result

    def enbase(self, x, min_length=None):
        min_length = min_length if min_length else self._min_length
        result = self._enbase(x)
        padding = self.alphabet[0] * (min_length - len(result))
        return '%s%s' % (padding, result)

    def _enbase(self, x):
        n = len(self.alphabet)
        if x < n:
            return self.alphabet[x]
        return self._enbase(int(x / n)) + self.alphabet[int(x % n)]

    def debase(self, x):
        n = len(self.alphabet)
        result = 0
        for i, c in enumerate(reversed(x)):
            result += self.alphabet.index(c) * (n ** i)
        return result


id_encoder = None


def get_encoder():
    global id_encoder
    if not id_encoder:
        id_encoder = IDEncoder()
    return id_encoder
