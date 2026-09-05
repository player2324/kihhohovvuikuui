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

        print(f"\n[*] Нода успешно запущена!")
        print(f"[*] Ваш адрес для подключения других пиров: {self.host}:{self.port}")
        print("-" * 50)

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
        while True:
            try:
                conn, addr = self.server.accept()
                print(f"\n[+] Новое подключение от пира {addr}:{addr}")
                self.peers.append(conn)
                
                peer_thread = threading.Thread(target=self.handle_peer, args=(conn, addr), daemon=True)
                peer_thread.start()
            except Exception as e:
                print(f"[-] Ошибка при приеме соединения: {e}")
                break

    def handle_peer(self, conn, addr):
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"\n[{addr}:{addr}]: {data.decode('utf-8')}")
            except (ConnectionResetError, ConnectionAbortedError):
                break
        
        print(f"\n[-] Пир {addr}:{addr} отключился.")
        if conn in self.peers:
            self.peers.remove(conn)
        conn.close()

    def connect_to_peer(self, peer_host, peer_port):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((peer_host, peer_port))
            self.peers.append(conn)
            print(f"[+] Успешно подключено к пиру {peer_host}:{peer_port}")
            
            peer_thread = threading.Thread(target=self.handle_peer, args=(conn, (peer_host, peer_port)), daemon=True)
            peer_thread.start()
        except Exception as e:
            print(f"[-] Не удалось подключиться к {peer_host}:{peer_port}. Ошибка: {e}")

    def send_messages_loop(self):
        print("Доступные команды:")
        print("  /connect [IP] [порт] — подключиться к новому пиру")
        print("  [любой текст]        — отправить сообщение всем пирам\n")
        while True:
            try:
                msg = input()
                if not msg:
                    continue
                
                if msg.startswith("/connect"):
                    parts = msg.split()
                    if len(parts) == 3:
                        p_host = parts[1]  # Исправлено: берем строку IP
                        p_port = int(parts[2])  # Исправлено: берем строку порта и переводим в число
                        self.connect_to_peer(p_host, p_port)
                    else:
                        print("Использование: /connect [IP] [порт]")
                else:
                    self.broadcast(msg)
            except Exception as e:
                print(f"[-] Ошибка ввода/отправки: {e}")

    def broadcast(self, message):
        encoded_msg = message.encode('utf-8')
        for peer in list(self.peers):
            try:
                peer.send(encoded_msg)
            except Exception:
                self.peers.remove(peer)
                peer.close()


if __name__ == "__main__":
    print("=== P2P МЕНЕДЖЕР СЕТИ ===")
    
    # === ВСТАВЬТЕ СЮДА ВАШ IP ===
    # '0.0.0.0' — слушает все сети (включая ZeroTier). 

    HOST = '0.0.0.0' 
    
    # Запрашиваем порт у пользователя прямо в консоли при старте программы
    while True:
        try:
            port_input = input("Введите порт для этой ноды (например, 5001): ").strip()
            PORT = int(port_input)
            break
        except ValueError:
            print("Ошибка: Порт должен быть числом. Попробуйте еще раз.")

    node = P2PNode(HOST, PORT)
    node.start()
