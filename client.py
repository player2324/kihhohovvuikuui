import socket
import threading
import sys

class P2PNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peers = []  # Список сокетов подключенных пиров

        # Создаем серверный сокет для приема входящих соединений
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

        print(f"[*] Нода запущена на {self.host}:{self.port}")

    def start(self):
        # Поток для приема входящих подключений
        listen_thread = threading.Thread(target=self.listen_for_connections, daemon=True)
        listen_thread.start()

        # Поток для отправки сообщений из консоли
        send_thread = threading.Thread(target=self.send_messages_loop, daemon=True)
        send_thread.start()

        # Держим главный поток активным
        listen_thread.join()
        send_thread.join()

    def listen_for_connections(self):
        """Ожидание и прием подключений от других нод."""
        while True:
            try:
                conn, addr = self.server.accept()
                print(f"\n[+] Новое подключение от пира {addr[0]}:{addr[1]}")
                self.peers.append(conn)
                
                # Запускаем поток для чтения сообщений от этого пира
                peer_thread = threading.Thread(target=self.handle_peer, args=(conn, addr), daemon=True)
                peer_thread.start()
            except Exception as e:
                print(f"[-] Ошибка при приеме соединения: {e}")
                break

    def handle_peer(self, conn, addr):
        """Обработка входящих сообщений от конкретного пира."""
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"\n[{addr[0]}:{addr[1]}]: {data.decode('utf-8')}")
            except (ConnectionResetError, ConnectionAbortedError):
                break
        
        print(f"\n[-] Пир {addr[0]}:{addr[1]} отключился.")
        if conn in self.peers:
            self.peers.remove(conn)
        conn.close()

    def connect_to_peer(self, peer_host, peer_port):
        """Инициализация подключения к другой ноде."""
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((peer_host, peer_port))
            self.peers.append(conn)
            print(f"[+] Успешно подключено к пиру {peer_host}:{peer_port}")
            
            # Поток для чтения ответов от этого пира
            peer_thread = threading.Thread(target=self.handle_peer, args=(conn, (peer_host, peer_port)), daemon=True)
            peer_thread.start()
        except Exception as e:
            print(f"[-] Не удалось подключиться к {peer_host}:{peer_port}. Ошибка: {e}")

    def send_messages_loop(self):
        """Цикл отправки сообщений или команд из консоли."""
        print("Доступные команды:\n/connect [host] [port] — подключиться к пиру\n[текст] — отправить сообщение всем пирам\n")
        while True:
            try:
                msg = input()
                if not msg:
                    continue
                
                # Обработка команды подключения
                if msg.startswith("/connect"):
                    parts = msg.split()
                    if len(parts) == 3:
                        p_host = parts[1]
                        p_port = int(parts[2])
                        self.connect_to_peer(p_host, p_port)
                    else:
                        print("Использование: /connect [host] [port]")
                else:
                    # Рассылка сообщения всем подключенным пирам (Broadcast)
                    self.broadcast(msg)
            except Exception as e:
                print(f"[-] Ошибка ввода/отправки: {e}")

    def broadcast(self, message):
        """Отправка сообщения всем известным пирам."""
        encoded_msg = message.encode('utf-8')
        for peer in list(self.peers):
            try:
                peer.send(encoded_msg)
            except Exception:
                self.peers.remove(peer)
                peer.close()

if __name__ == "__main__":
    # Запуск скрипта. Передайте порт как аргумент, например: python p2p_manager.py 5001
    if len(sys.argv) < 2:
        print("Пожалуйста, укажите порт для запуска ноды. Пример: python p2p_manager.py 5001")
        sys.exit(1)
        
    PORT = int(sys.argv[1])
    HOST = '127.0.0.1'  # Для теста на одной машине используем localhost
    
    node = P2PNode(HOST, PORT)
    node.start()
