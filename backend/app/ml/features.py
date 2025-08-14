import math

def make_features(ev: dict) -> list[float]:
    pps = ev.get("pps", 0)
    bps = ev.get("bytes", 0.0) * 8.0
    abuse = ev.get("abuse_score", 0)
    action = ev.get("cf_action", "allow")
    vector = ev.get("vector", "SYN")

    act_allow = 1.0 if action=="allow" else 0.0
    act_chal  = 1.0 if action=="challenge" else 0.0
    act_block = 1.0 if action=="block" else 0.0

    v_syn  = 1.0 if vector=="SYN" else 0.0
    v_udp  = 1.0 if vector=="UDP" else 0.0
    v_h2   = 1.0 if vector=="HTTP2" else 0.0

    ratio = (bps / (pps+1e-6))
    log_pps = math.log(pps+1)
    log_bps = math.log(bps+1)

    return [
        log_pps, log_bps, ratio, abuse,
        act_allow, act_chal, act_block,
        v_syn, v_udp, v_h2
    ]
