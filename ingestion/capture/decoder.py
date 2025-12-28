# FILE: ingestion/capture/decoder.py
# ------------------------------------------------------------------------------
class Decoder:
    def decode(self, packet):
        if packet is None or packet.payload is None:
            return None
        if packet.payload.size == 0:
            return None
        return packet.payload
