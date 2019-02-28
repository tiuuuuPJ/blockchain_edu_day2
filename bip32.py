import hashlib
import hmac
import random
import base58
from secp256k1 import PrivateKey, PublicKey


class Bip32:
    def check_seed(self, seed):
        length = len(seed)
        if not isinstance(seed, bytes):
            raise TypeError("seed must be bytes")
        if length < 16 or 64 < length or length % 4 != 0:
            raise ValueError("specified seed size is not allowed")
        return seed

    def __init__(self, seed, network="mainnet"):
        self.seed = seed
        self.network = network

    @classmethod
    def create_without_seed(network="mainnet"):
        seed = random.getrandbits(256).to_bytes(int(32), "little")
        return Bip32(seed, network)

    def gen_masterpriv(self):
        I64 = hmac.HMAC(key=b"Bitcoin seed", msg=self.seed,
                        digestmod=hashlib.sha512).digest()
        return ExtKey(self.network, b"\x00", b"\x00\x00\x00\x00", b"\x00\x00\x00\x00", I64[32:], I64[:32], True, False)

    def derive_from_path(self, path):
        indexes = path.split("/")
        for index in indexes:
            print(index)
            if index == "m":
                extkey = self.gen_masterpriv()
                continue

            if index[-1] == "H":
                is_hardened = True
                index = index[:-1]

            childindex = int(index, 10)
            extkey = extkey.derive_priv(childindex, is_hardened)

        return extkey.serialize()


class ExtKey:
    def __init__(self, network: str, depth: bytes, fingerprint: bytes, childnumber: bytes, chaincode: bytes, keydata: bytes, is_private: bool, is_hardened: bool):
        version = None
        if is_private:
            if network == "mainnet":
                version = bytes.fromhex("0488ADE4")
            elif network == "testnet":
                version = bytes.fromhex("04358394")
        elif not is_private:
            if network == "mainnet":
                version = bytes.fromhex("0488B21E")
            elif network == "testnet":
                version = bytes.fromhex("043587CF")
        if version is None:
            BaseException("cannot determine version")

        self.network = network
        self.version = version
        self.depth = depth
        self.fingerprint = fingerprint
        self.childnumber = childnumber
        self.chaincode = chaincode
        self.keydata = keydata
        self.is_private = is_private
        self.is_hardened = is_hardened

    def serialize(self):
        ret = bytearray()
        ret.extend(self.version)
        ret.extend(self.depth)
        ret.extend(self.fingerprint)
        ret.extend(self.childnumber)
        ret.extend(self.chaincode)
        if self.is_private:
            ret.extend(b"\0")
        ret.extend(self.keydata)
        return base58.b58encode_check(bytes(ret))

    def neuter(self):
        if not self.is_private:
            print("this is already neutered.")
            return self

        pubkeydata = PrivateKey(self.keydata, raw=True).pubkey.serialize()

        return ExtKey(self.network, self.depth, self.fingerprint, self.childnumber, self.chaincode, pubkeydata, False, self.is_hardened)

    def derive_priv(self, childindex: int, is_hardened: bool):
        if not self.is_private:
            raise BaseException("cannot derive privatekey from publickey")

        par_pub = self.neuter().keydata
        ba = bytearray()
        if is_hardened:
            ba.extend(b"\x00" + self.keydata)
        else:
            ba.extend(par_pub)

        ba.extend(childindex.to_bytes(4, 'little'))
        I64 = hmac.HMAC(key=self.chaincode, msg=bytes(ba),
                        digestmod=hashlib.sha512).digest()

        n = int(
            "0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
        new_priv = (int.from_bytes(I64[:32], 'little') +
                    int.from_bytes(self.keydata, 'little')) % n
        new_priv = new_priv.to_bytes(32, 'little')
        depth = int.from_bytes(self.depth, 'little') + 1

        new_fingerprint = hashlib.sha256(par_pub).digest()
        new_fingerprint = hashlib.new(
            "ripemd160", new_fingerprint).digest()[:4]

        return ExtKey(self.network, depth.to_bytes(1, 'little'), new_fingerprint, childindex.to_bytes(4, 'little'), I64[32:], new_priv, True, is_hardened)

    def derive_pub(self, childindex: int, is_hardened):
        if self.is_private:
            return self.neuter().derive_pub_from_pub(childindex, is_hardened)
        else:
            return self.derive_pub_from_pub(childindex, is_hardened)

    def derive_pub_from_pub(self, childindex: int, is_hardened: bool):
        if is_hardened:
            BaseException("cannot derive hardened pubkey from pubkey")

        ba = bytearray()
        ba.extend(self.keydata)
        ba.extend(childindex.to_bytes(4, 'little'))
        I64 = hmac.HMAC(key=self.chaincode, msg=bytes(ba),
                        digestmod=hashlib.sha512).digest()

        n = int(
            "0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
        new_priv = (int.from_bytes(I64[:32], 'little') +
                    int.from_bytes(self.keydata, 'little')) % n
        new_priv = new_priv.to_bytes(32, 'little')
        depth = int.from_bytes(self.depth, 'little') + 1

        new_fingerprint = hashlib.sha256(self.keydata).digest()
        new_fingerprint = hashlib.new(
            "ripemd160", new_fingerprint).digest()[:4]

        return ExtKey(self.network, depth.to_bytes(1, 'little'), new_fingerprint, childindex.to_bytes(4, 'little'), I64[32:], new_priv, True, is_hardened)


if __name__ == '__main__':
    seed = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    bip32 = Bip32(seed)
    print(bip32.derive_from_path("m/0H"))