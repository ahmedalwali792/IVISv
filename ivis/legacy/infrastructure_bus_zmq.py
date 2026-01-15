"""
Legacy ZeroMQ proxy bus (kept under ivis.legacy).
"""
import os
import sys


def main():
    try:
        import zmq
    except Exception as exc:
        print(f"Missing ZeroMQ dependency: {exc}")
        sys.exit(1)

    xsub_endpoint = os.getenv("ZMQ_XSUB_ENDPOINT", "tcp://*:5555")
    xpub_endpoint = os.getenv("ZMQ_XPUB_ENDPOINT", "tcp://*:5556")

    ctx = zmq.Context.instance()
    xsub = ctx.socket(zmq.XSUB)
    xsub.bind(xsub_endpoint)
    xpub = ctx.socket(zmq.XPUB)
    xpub.bind(xpub_endpoint)

    print(f"[BUS-ZMQ] XSUB {xsub_endpoint} | XPUB {xpub_endpoint}")
    try:
        zmq.proxy(xsub, xpub)
    except KeyboardInterrupt:
        print("[BUS-ZMQ] Stopped")
    finally:
        xsub.close(0)
        xpub.close(0)
        ctx.term()


if __name__ == "__main__":
    main()
