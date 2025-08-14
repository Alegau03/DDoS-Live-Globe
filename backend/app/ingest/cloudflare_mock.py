import random, time
from typing import Iterator

VECTORS = ["SYN","UDP","HTTP2"]

def random_ip():
    return ".".join(str(random.randint(1,254)) for _ in range(4))

def generate_events() -> Iterator[dict]:
    while True:
        src_ip = random_ip()
        dst_ip = random_ip()
        pps = int(random.lognormvariate(12, 0.6))
        bps = float(pps * random.randint(60, 240))
        action = random.choices(["allow","challenge","block"], weights=[0.6, 0.25, 0.15])[0]
        vector = random.choice(VECTORS)
        yield {
            "ts": int(time.time()),
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "bytes": bps/8,
            "pps": pps,
            "cf_action": action,
            "vector": vector,
            "client_country": random.choice(["US","CN","IT","DE","BR","GB","FR","JP","IN","RU"]),
            "client_asn": random.randint(10000, 65000)
        }
        time.sleep(random.uniform(0.05, 0.4))
