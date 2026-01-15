"""
Legacy dev-only TCP message bus. Kept under ivis.legacy for clarity.
"""
import socket
import threading


class SimpleBus:
    """
    TCP Message Broker for local development (legacy).
    """
    def __init__(self, host="0.0.0.0", port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        self.clients = []
        self.running = True
        try:
            from ivis_logging import setup_logging

            self.logger = setup_logging("bus")
        except Exception:
            import logging

            self.logger = logging.getLogger("bus")
        self.logger.info("[BUS] Listening on %s:%s", host, port)

    def broadcast(self, sender_socket, message):
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.sendall(message)
                except:
                    self.remove(client)

    def remove(self, connection):
        if connection in self.clients:
            self.clients.remove(connection)

    def handle_client(self, conn, addr):
        self.logger.info("[BUS] New connection: %s", addr)
        self.clients.append(conn)
        while self.running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                self.broadcast(conn, data)
            except:
                break
        self.remove(conn)
        conn.close()

    def start(self):
        while self.running:
            try:
                conn, addr = self.server.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.daemon = True
                thread.start()
            except KeyboardInterrupt:
                self.stop()
                break

    def stop(self):
        self.running = False
        self.server.close()
        self.logger.info("[BUS] Stopped")


if __name__ == "__main__":
    bus = SimpleBus()
    bus.start()
