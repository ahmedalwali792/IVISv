# ------------------------------------------------------------------------------
# FILE: infrastructure/bus_zmq.py
# ------------------------------------------------------------------------------
import os
import sys

from ivis_logging import setup_logging


def main():
    logger = setup_logging("bus")
    try:
        import zmq
    except Exception as exc:
        logger.error("Missing ZeroMQ dependency: %s", exc)
        sys.exit(1)

    xsub_endpoint = os.getenv("ZMQ_XSUB_ENDPOINT", "tcp://*:5555")
    xpub_endpoint = os.getenv("ZMQ_XPUB_ENDPOINT", "tcp://*:5556")

    ctx = zmq.Context.instance()
    xsub = ctx.socket(zmq.XSUB)
    xsub.bind(xsub_endpoint)
    xpub = ctx.socket(zmq.XPUB)
    xpub.bind(xpub_endpoint)

    logger.info("[BUS-ZMQ] XSUB %s | XPUB %s", xsub_endpoint, xpub_endpoint)
    try:
        zmq.proxy(xsub, xpub)
    except KeyboardInterrupt:
        logger.info("[BUS-ZMQ] Stopped")
    finally:
        xsub.close(0)
        xpub.close(0)
        ctx.term()


if __name__ == "__main__":
    main()
