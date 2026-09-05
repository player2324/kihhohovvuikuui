import socket
import threading
import pyaudio
import sys

# Настройки аудио-потока (качество звука)
CHUNK = 1024              # Размер буфера чтения звука
FORMAT = pyaudio.paInt16  # Глубина звука (16 бит)
CHANNELS = 1              # Моно-звук
RATE = 44100              # Частота дискретизации (CD-качество)

class P2PVoiceCall:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        
        # Для аудио используем UDP сокет (он быстрее и не падает при потере пакетов)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        
        # Инициализируем аудиокарту
        self.p = pyaudio.PyAudio()
        
        # Поток воспроизведения (то, что мы слышим от собеседника)
        self.speaker = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
        # Поток записи (то, что улавливает наш микрофон)
        self.microphone = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        
        print(f"[*] Голосовой модуль запущен на порту {self.port}")
        print(f"[*] Готов принимать звонки через ZeroTier интерфейс.")
        print("-" * 50)

    def start(self):
        # Запускаем прием аудио во входящем потоке
        receive_thread = threading.Thread(target=self.receive_audio_loop, daemon=True)
        receive_thread.start()
        
        # Запускаем отправку аудио в интерактивном режиме
        self.menu_loop()

    def receive_audio_loop(self):
        """Постоянно принимает байты звука из сети и отправляет в динамики."""
        while True:
            try:
                data, addr = self.sock.recvfrom(CHUNK * 4)
                if data:
                    self.speaker.write(data)
            except Exception as e:
                print(f"\n[-] Ошибка воспроизведения: {e}")
                break

    def send_audio_loop(self, target_ip, target_port):
        """Захватывает звук с микрофона и шлет на IP собеседника."""
        print(f"[+] Звонок начат с {target_ip}:{target_port}. Говорите...")
        self.is_calling = True
        
        while self.is_calling:
            try:
                # Читаем данные с микрофона
                audio_data = self.microphone.read(CHUNK, exception_on_overflow=False)
                # Отправляем напрямую по UDP собеседнику
                self.sock.sendto(audio_data, (target_ip, target_port))
            except Exception as e:
                print(f"\n[-] Звонок сорвался: {e}")
                break
        print("[*] Звонок завершен.")

    def menu_loop(self):
        """Интерактивное меню для управления звонком."""
        print("Команды:\n  /call [IP] [порт] — позвонить собеседнику\n  /end              — положить трубку\n")
        send_thread = None
        
        while True:
            cmd = input().strip()
            if cmd.startswith("/call"):
                parts = cmd.split()
                if len(parts) == 3:
                    target_ip = parts[1]
                    target_port = int(parts[2])
                    
                    # Запускаем поток отправки голоса
                    self.is_calling = True
                    send_thread = threading.Thread(target=self.send_audio_loop, args=(target_ip, target_port), daemon=True)
                    send_thread.start()
                else:
                    print("Использование: /call [IP] [порт]")
                    
            elif cmd == "/end":
                self.is_calling = False
                if send_thread:
                    send_thread.join()

if __name__ == "__main__":
    print("=== P2P ЗВОНКИ (ZeroTier/Локалка) ===")
    
    # 0.0.0.0 автоматически слушает все ваши IP, включая выданный в ZeroTier
    HOST = '0.0.0.0'
    
    while True:
        try:
            port_input = input("Введите голосовой порт для себя (например, 6000): ").strip()
            PORT = int(port_input)
            break
        except ValueError:
            print("Ошибка: Порт должен быть числом.")

    call_manager = P2PVoiceCall(HOST, PORT)
    call_manager.start()
