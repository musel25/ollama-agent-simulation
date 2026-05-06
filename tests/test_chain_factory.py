from shared.chain import make_web3
from shared.config import Config


def test_make_web3_uses_cfg_rpc_url():
    cfg = Config(rpc_url="http://nowhere:9999")
    w3 = make_web3(cfg)
    assert w3.provider.endpoint_uri == "http://nowhere:9999"
