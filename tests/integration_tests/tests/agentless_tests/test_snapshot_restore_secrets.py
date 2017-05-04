########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    upload_and_restore_snapshot
)


class TestSnapshotSecrets(AgentlessTestCase):
    maxDiff = None
    run_storage_reset = False

    def test_restore_3_4_2_secrets(self):
        # Yes, there are six private keys in this file
        # This will present a grave risk to the no-longer-existing VMs that
        # the snapshots were created on.
        key1 = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAwOXwncbf9yPp3Sgax5xT4gETjSuwAe0EPuJvnNDGk2szNq0T
pd6Dk8OB0Oq4eBUrRZVLyDQBySsgNbywdajTkIjSoWOPQIczWG2O9rwjKw/J+EZh
TW7smnhIW8JCtMG7npfgr6P027CE4MQFHNlzQz7Z27fbNEOFvq2xhjGechNbJTZO
NNJKO02mTOQQJc5jqJtDrh/sa2bZs43JdIvVWSh8JkJzgmWnjawcVrQR9NmdXqjO
pITynO3YMwdG7GZi567dN21IwLZfvrNoDqY4IFPOfpcjRspirNXuFzjb+HNjRY9Z
XpJrEVJ/9E5uhzbcTAYnBLTT5LdIVGkokhipdwIDAQABAoIBABspRXQx6J9YAzoM
x5iLvpP4KtSZ7jKXOR3RrH2cOBnR4mg0fqvAZS6NPN457reZ43nsx7rs98NnuyVV
6FLo7sFPQrlO14DyiJxO8O51F06c7odzAYhxsgceILIq7FGfZdey8wRIRdYZSNyN
PVsOk1hIpUx22vrE9zQeKP0IR5MwP7O1P/hqdCGekk+29wLlz2t8M3pIVQ4jvhqE
wEWWS63kzFxz1xWWhWli1hL9fzlvBjmhedsD4/lbIvP9BXSIecjuWVO9XtIy5s+a
DAjt+zkmvSydUmHtNpMTEt+JpAyc62vRVuUDoQO6PdTFc9OEQaUrfHdCW21hD3+2
FeizNqECgYEA8yIjJ53XakIpoyZn0+wepzeT5AemrhUp8rBzhWc/MPRL7ZEway5N
0fvTJlkkKxJ+yMuxEh++BwX3+zKRhaxaH2kax7ojAXPWCJdjSRfhH92r4xa1J5wI
mP05jZ9B31B8ZqyOfKct3dEWSj0uGK0y48E0FFv78RwT4NMTEWZqD10CgYEAyxs9
N0ytEnYDnKoq0jNWrTQB9w0DFRmEW6+v/kzP4WueBSvB7W9YqqDSNPgGkyJR9maW
4HVN4jvhqKZbFTVz15iKemk9x3qL+lDm0t6F81UiB3+Pc6SN13AXm1HHK/nxNyrn
Q700OZmVfqXV3DSP3he3gakWd5jou+3tvKfSkuMCgYEAy+mknFRYV8kXzLqoN+f/
qXUGdygnljcv0FhG+uql5/PsPloXxry2Ddfrtmzq1akUZmnXn4C5yoAqBCbcP8VW
bKOlDz/AnjY9m0UEw0fgyu4KfFIOKyNFXrJ6c5nPEHEbdK1ib49y+2eiDy+SmqWg
Wb4vZKfk/Mn0rgm5I03GxA0CgYBCZgBIQM/f1ibuI49mMpRmgTcXPfDBCBuGIdRm
TVQ0fIsnY5u9dIZHGdY+rMrxdOnYpMc0UAULLcpi6SejslrRo7O5uwgQW5bBWYts
aoTd/Pnn+6K5CpW4VZPSGhUD4m0iPOtn8MXPAs+lnK9ikuhpkdVTFSUcKigDsA/l
efPUQwKBgAHMMJXS4rd4BUo1VrQFbNwonr56c4Al93m/a3rCo1uabQfa98l/bmQH
gEGVnQ1Ca33UUp5RPhQKn7qXdBxLvCPZNfCE1iHm4oeoOKWoscAaiCdfccLl5ToQ
ZHFjT8Et96+53GMf8AMqCNR1D6619/96IwBAGo459PRpxL3EQVvr
-----END RSA PRIVATE KEY-----
'''.lstrip()

        key2 = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA33WRZc8fwfcNYKGbk/Ka8yQsi+IO5DqYAoDkGcLu19idkCj3
XQqqDkZBhbE6JOKTSwEWFa3xgmir0OR80HVSDkSACcY4bBKM/Eez+6GFdH9Yxved
VwGeCJmFaplqlbgXZ2y0/gNuTq+xQqJ2zta4CCrdQjQCOpHGk+vpweCsb4budZlX
SvP10nu4Z3bMqMMzKSdQvvcaNP0BCvwDNFtZgHswbGYO3QkqKqYzUbnCmLshC00J
YgBd/ODUF/VymdsKzzg4alutxK5SIf376UVO9IZ0bj5HyFu71Zt1HJCYDqXunt2n
jg1a2BMp4OiFDAwUpAOaqBJ3OoA3keo/joxWUQIDAQABAoIBAGNopwU2rncYk9/w
JQkdPWd7KUIVj/BiTKuYcWEwghaN7BJs1xaSHvL4uD9kh2xPS51rX0rHthAAxqbI
bupBtv5X5On0P7d8TTISJ/SCd59K49Cn6VwCgS5sNZklpO/0FJ1TE/WIyzLAIEh3
hAkiJn6jqwi/oFoz7bZylexFKhD2jgnC0fTtn8BAtYkofYuMhy2mrxsSeRuZsXkI
xBAddXLNZizLA/00Q3pbXNcO93g1La9ayZPk6JYLHc1DA4AX5T1GvF0SNVKxQmly
zIcz068Hm65mPcpXqZ6iTc/G2We8KZiB3Tc20oYQ+WAkO9lrwbsc1DSMRcGOJJYX
eHJm820CgYEA9oTnrizoEZeUdR1EbTbMNDV79O47Yh+LdeWro03eS+X78OkMBOVC
Ll0hV5Ewn/eKol4L+d27xeYpTOch27w0T33ge9dttn8Qm6oHh7PSTVT7Kry36dRa
3RiDa9sI6Et0B/Ey8J1uAuK3sO/lK708oZierxknvnbjnDHZ6ifvOx8CgYEA6A2g
oyzRtrZWeMGjyVAtHQzjfJq+pnXZHFhWFMhrP/MRoW7q3nUyrB8ndPQJMk00n2gI
NxpH+q2osuyBgEWy1loUZqOtkuswEVwXT7UkqFWAx6thDCx8QZRy67nWNdsDCSv0
eXvCpySyv43xwuO1FqoVA233uSSoDACt1hUbsI8CgYEAgNQZ40syiCcH/WArJ0wQ
0WP2AJ0TSYcksZsx5GjIOC/bRx3zGwfYWzRuPT3yBFcwCwRNC+pVu+k5Qigz6Ipl
Z/lnfDCr9EhZHJBx2PgfeixkCgSPtFI2nf62h4HzGLp9y7zAG0CagkWLK5tiz0XY
zrZcjzL9Myscbb8bm6P9AI8CgYEAuM4JjYpnJc0HBrqoVu4sT4NxNE4E4YrfMmzD
eV+30kEhXGB6WloZ1ewlv0WOgWntK7ptOH0Mr/5XaM9jvyVC7OTmdGuME4KMUHb3
9bm8jPczTVEWQ9y1xICWGVdx2ogmXcqMs6c1eWmHlXhU/rHcCUXA4G9WpzMjRhPQ
XbuHxs8CgYAIPpmL0mK5A0UMAxWvpUjw8FcWaAOfsvL5ZnQsCRsIruccnDqwh3Gp
6hguFZQCLELO8j0g/kmgJjbuAJJi6NnkM3T5KGi2T9nCYoRuQhPuEJOKDCVZz0XQ
zjNe/LgcU1cbpIVxN3TmoTd3sDg6ELvpWr5hlc3SbcSgYfY4RfWTyQ==
-----END RSA PRIVATE KEY-----
'''.lstrip()

        self._test_restore_secrets('snapshot_3.4.2.zip', key1, key2,
                                   tenant='default_tenant')

    # Skipped because the restore doesn't work due to a constraint violation
    # when the snapshot comes from 4.0
    def test_restore_4_0_0_secrets(self):
        key1 = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAvwrfhbJCU38YI6WRTTQ9KPvDL+uYF8v7XvBlzEAcxhofLJxc
6LFPp5GcE3JDI1C/tABkNDIyQHLicKFm2oQTJIRmJFTIvdmMe2HhWB/y7mqjD8Xe
tsky8mpNoDZGNmlAW9UjpNRRs92bj7tohCFtmYzVIrX3k0ZtD8ZfrTEWhssvbnak
rfcRwBodZAszBuNerc5+pajspg4ILd0q0jRF2hZ/7symcZ9JhEYNvFIIpk/Fmhw9
0ihdPfFBNDSbM7Q+tbzw4VgPQx2YFN1IaxPtpEpnZsIE+0Fn9Y1rG17e9JT1RDBU
WYs+O6Ctc+0dsKkJ0Y+Y0SyJdBhNZpWEHTBYlwIDAQABAoIBAQCT6iFCbNB5wW+5
OdoUgpvP/Y4Urj6mPiM0UMEgsYsVvufgLHirGY3o2g6T5+Yfk8e54Iu09iB+UfUM
64qtKZGAtpo3CwYaKDRi21gUWThIbHwwHC3iLEmr866Cm0MlobxY3d+pIVLZBn4J
fTrhAtjPCIGFTIqRlveePSOa/uTIG3Q/nYUdl+Okopx9xBw9DjztrfZVJstvfsZH
acA+LJ7yjkrNXcO179pHTm0qUGeQzyMQd/p2RWPJFi7ItMbwhxlFEqXX56kD5Jdg
vzD/d6f59Zh9eCS0k71isi0f4Mni75y1LyvE9VEPYkgTTJsdNvucL0Mm2+qif2mQ
gmpWTfghAoGBAPrrNNVi7lhbPc8ZzQryNuTjHb6Vv2FyXeQWv/NL4I7q65e2iJCI
F8W/TeLpnh3E5C9fB8LX+TvTsFaqM6Oe96J0ruBYViV5raLiph5AgbLlt99dJ/zm
EWWLgvCZzfshnWbMsK050CKskSIhJqlmCtL37oukuaK7Ec3hncoNPe3/AoGBAMLp
Qrv+sjloDtJzSXUnhRqHr8V8L2ff22tTmuclZUaslffPm176MMmwZuKkyMEmtN9/
hu30XN6Qjm4hu7WYHebUkzDckULLmUA14q4kwYPml69srLzv3IXWcVwYAx96pkVr
XFUE0yR+ydfrrfkkCEn8RlAm9E+4THQeKHqKXEVpAoGAaWsUIWqVFI4Q48fFO4oT
wgohXwbvBvPTupZMQt1oFONh47WOnppu0mfTQzg/c+ZasARO8G9oiNghR+fuFhod
lCVNq3exicEbUEnE3QTg+NZGcBNlT30hZfY9JvSXc6DlzmDFAaI+bbLurtYatiTm
+0eq8wRb8aCClGrrrg3uLOUCgYA0qWeBebhXsFjI3aNMRwg8ecqw9fOtAhu7rNQe
fckWRk0irnIRQFHsPIAf3lvra/TUqhUft7Vb4PzKnsyjrNzvYCIAwqdwv6fBZI3B
dWbfp272U8t8JOaVNrJcKpS1baL9AJvq0Knno2YPs7rGpMikjMfGoi/CVk451Wgk
a7uweQKBgQCQ3SIDC3bxyonCUoJGGn17lBEhrdO1GxEVCTiTC0jSUnjqxO5Vuxfg
owL1ibG2nfzMrTtT7W7up0xdl5zCWcE7OARpjwdGtrE7T6c4KuCZq5SbDJM3kX2a
9STkq+nOY/zaJMBhuLYaWz3LypL1S8iwtaPW1IC+XNbaIPDSmzbynw==
-----END RSA PRIVATE KEY-----
'''.lstrip()

        key2 = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAvf38fo4DE+huvfpfgScFftzruYQOtG0+e85MNfFFpTBGQBNB
ZYGZFQuL1pq+rWABX5FxxrrSh+/ENyokx3HDihQPjd/eZq31vVGRhKRjpQWfhmoU
D67w28a84O67TtanhL2iGfUugB1Y/ekylf74wJwfX0fzWNl5k6x30ZjGusxQuNrj
J/PN7Jm9nw/Gywfep7VYIPL1vt8eL+4/UNpx3eO76QflFdMFTEVs8qElq76qyzxw
cnKN7quCfnIkwrGecqnP8Dr6V1BTkDSZX8H/DEg6KJgJjUhwp+BvZN4EZJ44EjxI
zNttamh9pgbztzVArQydgA0VpgndCtrIQ+x6OQIDAQABAoIBAHmFQMC5mKJdIqgE
wp1bFhrEt0lbfARPc43Ar+I4xjEYJXbKWiPQttdNIU5Mf/Vo2LgF0V4pFIu6Aii+
nfOrgkSI/EHklN3cGrfSul66vrlIVXal1tsJLCmGfjzotYmBpngyysILnoh3PPp6
884Y3YZk1XQeEzobL7YStDitnT7QYcOn9+0nSSxCDb6frGfi2mO4nTC6TQv0O3Wv
EhmwHlVx8vFCJC1QpKQZL8Y86RM06Rez8fVJ/R5mLhMUj9If0/taMLObiFzPSTYx
xeIQ0ryngL+Jk2cGMQPooZN9hrDGSI0ZfrEcodE6mHkxRcUbqcaCGx/9rN1DSUuS
p/z8MAECgYEA55M1PK7CCJgB9DvtkUTbkqJjVLH57BYVO3DUx4ioGM/CbSRtdwp7
BtFIg5aE7Ip/yTmYGCJ/du/61g4L3+nGqmXIeiI3B5K32oEy4ekAnVAwYn6cl09c
W8QUkbwEFf2rn15+BdXILcneHrc0LmXjgA9Pu0RxyRctP9aGKPy0awECgYEA0gf+
CSJFF4X+C4LuWl193M5NCV+ovf1zU474yJ+90rZntWwH0yVFDMdju4XhCWhk5wmE
62oAx5MyNz9FBBtzi6KT8eSPxy9mWF0yYMeiY55yj9ZhGa8zR1WZb6HYg2cf+hD2
b8BY0M6yJ5pyxcRrGpw5VnOXmug+yhY4+LzzpzkCgYEApRBe8CQ5FlsTeX2F9vg3
8qthViuOU2PiOn5QjPGxsA3XLmi6xhFoZBGlOHZ/xQNr1okBCqL8bFDeYNmeSTqf
azIl1jixNOq1tkBFfpXQ5FEWS/6nq4rb8GUxrDdySiKIxI5cEdiyWUD83LQFs9TY
dp1zXa6J1KZ6kHhfJLQL/gECgYByyrF6doOCrtZBnmb9drmytAKAzAqjBGJC2hJ5
PG14O/+Eta21JlqN+HA27p4nESqM57QBIqeYbIf2kBr9eq91Mv9fJse6Wtq6Ev3U
zWegwNnmaYoaipohM9Svoap/bx6YAytduqgQP9g5Mv3lv0u2eIoSCQ1kOekPdIPg
1wzoaQKBgQDPXQiOUEsIpzlQe0M3VwdBSfBXfwWqahQF5xiFPBXnfIbNNgIGQ1ho
RIIj1rTFvkK4/gMRnJDtxkLom5Xlg85PLu1ZPV1hMnchgj715NMOdRBnbN15VfZX
0eDF4U9cPtfd6qSmBSdihgBt3m4QxN58q15vvJj2GS6L9bBqSvT5rg==
-----END RSA PRIVATE KEY-----
'''.lstrip()

        self._test_restore_secrets('snapshot_4.0.zip', key1, key2)

    def test_restore_4_0_1_secrets(self):
        key1 = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAyjd+tmiFpuqTbCojnEIP6Oco5wHRC2rBQhZYdfpzPsaxlLUk
kJ5KXwpxYgWBPnPDLuKJhty5g3MBzwxuB8Y1xk1gU7isaBjrXkOCtJz/1o3zDz1a
ttxgY0JHRxn8lCiQXUHwBKE5l2fb8LlpKSPxKcRGeHHMpfoBSD5aLW8Eiz95GF79
vLtjMz/JWQrHLCikVAxRSx+kFUkpIMRK5AcPYF+/BQ3Hz5NNHaJ3H5i2Sl/2L0g/
F4HyGXwYNb/WWWYyITaYQ5fXpETetuypRE4jMZcOe/dq67XkjT1xAr9C+svfEgox
LjXxG3tfxDzo6bPZxO+XgM888Iwzqd0tysZ/DwIDAQABAoIBACftRSum/5yxfGJC
/7z+nj2SRtU12pyye24dE2JYDSE8AhwmmA2l83FIkpKUG6zFFqjPOfBS7J4zuwuy
nJcUX9HDvV1KfWAga3i1Q719slYeuPstVhf881sl3wT+8IwgZkDDoCyJ2OE4NIkX
Utg4rIleo7tsXMf40P/+r7eA0BjeGYfp36GgiTQS6GiHfy96re4vWWaMHw/k4y/5
1YE+7YJAfxMdcZhv0gIkZUo6OObz3ufYya0tU6cAARezaFZ6UF61tWYehIxtzrW5
WkdRM3OzW2yjUQd+aLiKfimxsJA9fGtWolQNJBlbRz6hr7UXKTk4HB5T56kbryaj
lEIeIYECgYEA71+FKXcUQLR6jU7CJt7QMGxMxPEsFWQeoKpPFXbNxwSf29LPGdmb
AmFCDLKyYvInENoIjGOrb1uVGLD+/RtYU+VfUXIiyhwZHmq4xg2fwrRxA8aDrzWj
gd1KOo9urCSlFIg13j8QvWicp8mJSAyrXwIyYZvcOiTnTH+jw8e+qP8CgYEA2ENE
0/cl7mmjrAbNvGpFl0LixXLtguaVOXgtuJIXhFGo6YjjBxuwY7QZXTy3aoH9bdh1
t32mie/Di0afc/37X5ktsHdTIWpeptNc9VJ3uCbqZEoDK8oGWlHf7fWm9Zn4Anhc
AbBm9a/gDVPeKAydhelAT1PQ8Zpve2q+dgG3mfECgYEA0zhBQ059A399qFT3wt7X
a/MUZq+8y39V+0VslS8I8vUkrg89ibzXJ+l0I8pG2EJ+sEMESgTk0FVKocgEqIjJ
jvYV/sMs6ZSToaBgPPrmnyMjmkZAConVJpGCn1vTN3j6Zbyvc9XISqoVmYSfa4Eq
cqJ4nGKwmGnZ40m50tbdaTcCgYAPC0brc+LoneKr4eFH/SCQMC/0SlVpaL7yu4B6
uXb3VnLopAQfB3cSyIGHMeUUfKxzir5NoGkIaWxx8NzAxedJtC8wemyHA45IDqYF
ztHTNqnRhjCISEp+1/k65X7S0P4mtda4q1vONYjhhHcM1CvVF+/IVO1REUw2Cqvr
K51pEQKBgQDrfTAgLDPGHMl6vMMyLErKe9lM4EGMALedBBlHS4yA8RWpnSb5ecf1
bPChbfwYQi7YyibEVjM7eYvPBVEBymDGYk8qUg2CAmAg1qXnojX32z2xiXbcWi71
LVAAn6YcNX0cXR1E8NjwCwLINTOXbeBSrNRgCVgZE9cIeGrzttR9Qg==
-----END RSA PRIVATE KEY-----
'''.lstrip()

        key2 = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEApmxOJNUXi78hOVCxH9QAUTfef7o8BBNGH5Yf4/emeeSGqsPm
JNCUthW/LmdVWAMOA+jfD/yYc5xEiyZthSqNJ6Y/CWA+9Z7rSunL03EAXxU3OWz2
2i0c/XW0yLnJKIrCTGPVyNYlzyaewFuJ4ACPpXZJziOXD0VIkfDcWM12rYe6fy5E
a6ZkvUVeOlL8r2hnNi8/Mm88TyPC9UXeCwFBzWRC3n8ywmVdmy88/E7PgJPCb4y9
Nd5Ml6NW5j8PVdysI0PWyCsOC4BIAS/sfzQH5cVWmvmFdclbgLTgCooOLFNiwDPK
N/389BKXhEujohzWLiyJhzIy+Rx2NRPld6hgeQIDAQABAoIBAEf8eSC9e93a4sgj
+znFPg3jmL6vE96/Z4mqKkk1ijEXhJjA+//YqTrJ1VSBJg1X5OwUAsirflYjthJq
oN0FNuF7q7CmjRU5lJVm49+l9X8rciPI2k4tTWjlTTm2AykiPEFGveaNmvUrw2d5
MP5Pv9LWg75C7siQM3/NK8LNvRP5+wxyEeTnCPnUNcvgWE0Jkw/pgIhLCKfifpW8
hFWZGyiTNx9q518vZkBSlkpZlxfSZMJTN2CEIEX116+G3XBzTXZRLREswYzK5gNf
0BJWcauMR7Bj3fIsAKwF0u2EmIbIY2TCqCbKsTGMDhmD8Zec6rSg4FlH00xl85xm
EHUwvAECgYEA2OdKAloCLNWbFbZ+6AyyQ/4k8yQafv9QMmhTlBTbmYjHLKY+EnlC
dFLWINSFG5Yxeehgy/BqSqE7iev2peX0MajkxdgF3F/cs0nb48O1hrJdlodS4bss
52H75+nPIuEPfb/bd4ouf7dKkyyceRbSs0qnjpZy3lAcKcVhZe/fJWECgYEAxGuq
6RvIk6XympWeE25aYrVzzozfOXl7uoXWovK9E22gl+lqtsoIT+i5bM72vAfGMV30
xKBXf/mZ7IAOty3MGuIgna+mc6b5oqzM1SqMTawSpxLuuAwoeYnEW3h52BUb/uQK
532PsnGUwynTjLFgS2d6iDIp4wROuGvaZ+B9+hkCgYAiOm19bYLGXHb6uC/Sop5H
CIYAMIRV4ihfrAL0bU4yLllv/FPzSltoS+IqkB7pOYxZNoh/5lJ/sG3a1/e2OlGM
vKBNcEeMfTwwtskSakHtHZyTMourv4PYh6fe8xCS6n0tVOdnN9EaqmwESZfvq+BY
FsHWSHucBXxMQy+ZjH7kQQKBgC2S5bbskV9gs6eWa3UKt8ILY/Fa0jhdrY2bnC92
rtQhLY/RwsbinYcc8lkCtFDwZNXzfOVaZrL00PgExmVOJPtf2D1+EdrntSg/e89B
7gffkvxc8jKV75YzlvG6RFsUmshLVRRdF8hJfkDCJamRRkx4l/+d1AYua61yqNxN
RC2RAoGAN1IFKDA1BclTUM+GxbQHjBaec5sWTsFIJ1mHbiqswM5Ra7K7wVSKnPvL
gM4iD5creUx9Xq/BAF5cSTIzWIouifkDT5l/R1aGMQJcE/K5ns+SCIrUoTOR7PCO
dQlnLmh5qCayfwLy9JIGzZ3CyRkfQf8dOPXrsjjhrudsbb26AQQ=
-----END RSA PRIVATE KEY-----
'''.lstrip()

        self._test_restore_secrets('snapshot_4.0.1.zip', key1, key2)

    def _test_restore_secrets(self, snapshot, key1, key2, tenant=None):
        upload_and_restore_snapshot(snapshot, 'snapshot_abc123', tenant)

        correct_data = {
            'vm1': {
                'agent': {
                    'get_secret': 'cfyagent_key___etc_cloudify_id_rsa',
                },
            },
            'vm2': {
                'agent': {
                    'get_secret': 'cfyagent_key___etc_cloudify_something.pem',
                },
            },
            'some_sort_of_thing': {
                'runtime_properties': {
                     'prop1': '/etc/cloudify/id_rsa',
                     'prop2': '/etc/cloudify/something.pem',
                     'prop3': '/etc/cloudify/agent_key.pem',
                },
                'node_properties': {
                    'notkey': '/etc/cloudify/agent_key.pem',
                    'something': {
                        'get_secret': 'cfyagent_key___etc_cloudify_id_rsa',
                    },
                },
                'start_operation_inputs': {
                    'an_input': {
                        'get_secret': 'cfyagent_key___etc_cloudify_id_rsa',
                    },
                    'fabric_env': {'key_path': '/etc/cloudify/something.pem'},
                    'not_a_key': '/etc/cloudify/agent_key.pem',
                    'otherput': {
                        'get_secret': (
                            'cfyagent_key___etc_cloudify_something.pem'
                        ),
                    },
                    'script_path': 'scripts/something.sh',
                },
            },
            'secrets': {
                'cfyagent_key___etc_cloudify_something.pem': key1,
                'cfyagent_key___etc_cloudify_id_rsa': key2,
            },
        }

        nodes_and_instances = []
        nodes_and_instances.extend(self.client.node_instances.list())
        nodes_and_instances.extend(self.client.nodes.list())
        for node in nodes_and_instances:
            if 'node_id' in node:
                node_id = node['node_id']
                props = node['runtime_properties']
                instance = True
            else:
                node_id = node['id']
                props = node['properties']
                instance = False

            if node_id in ('vm1', 'vm2'):
                self.assertEquals(
                    props['cloudify_agent']['key'],
                    correct_data[node_id]['agent'],
                )

            elif node_id == 'some_sort_of_thing':
                if instance:
                    self.assertEquals(
                        props,
                        correct_data[node_id]['runtime_properties'],
                    )
                else:
                    self.assertEquals(
                        props,
                        correct_data[node_id]['node_properties'],
                    )

                    operations = node['operations']
                    start_op = operations[
                        'cloudify.interfaces.lifecycle.start']
                    self.assertEquals(
                        start_op['inputs'],
                        correct_data[node_id]['start_operation_inputs'],
                    )

        secrets = self.client.secrets.list()

        secrets = {
            secret['key']: self.client.secrets.get(secret['key'])['value']
            for secret in secrets
        }
        self.assertEquals(
            secrets,
            correct_data['secrets'],
        )
