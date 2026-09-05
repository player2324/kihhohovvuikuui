import socket
import threading
import sounddevice as sd
import numpy as np
import sys

# Настройки звука
SAMPLE_RATE = 16000  # 16kHz — стандарт для четкой передачи голоса
CHANNELS = 1         # Моно-канал
BLOCKSIZE = 1024     # Размер звукового пакета

class P2PVoiceCall:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.target_address = None
        self.is_calling = False

        # Используем быстрый UDP-сокет для стриминга аудио данных
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))

        print(f"[*] Голосовой модуль на sounddevice запущен!")
        print(f"[*] Порт прослушивания: {self.port} (ZeroTier)")
        print("-" * 50)

    def start(self):
        # Отдельный поток для приема звука из сети
        receive_thread = threading.Thread(target=self.receive_audio_loop, daemon=True)
        receive_thread.start()
        
        # Главное интерактивное меню программы
        self.menu_loop()

    def audio_input_callback(self, indata, frames, time, status):
        """Callback-функция: вызывается автоматически, когда микрофон готов отдать порцию звука."""
        if self.is_calling and self.target_address:
            try:
                # Превращаем сырые данные микрофона в байты и шлем по UDP собеседнику
                self.sock.sendto(indata.tobytes(), self.target_address)
            except Exception:
                pass

    def receive_audio_loop(self):
        """Принимает байты звука по сети и на лету воспроизводит их в динамики."""
        # Открываем выходной аудиопоток (динамики)
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', blocksize=BLOCKSIZE) as output_stream:
            while True:
                try:
                    # Читаем байты из сетевого сокета
                    data, addr = self.sock.recvfrom(BLOCKSIZE * 2)  # int16 занимает 2 байта
                    if data:
                        # Превращаем байты обратно в аудио-массив и пишем в динамик
                        audio_array = np.frombuffer(data, dtype=np.int16)
                        output_stream.write(audio_array)
                except Exception as e:
                    print(f"\n[-] Ошибка аудиопотока: {e}")
                    break

    def menu_loop(self):
        print("Команды:\n  /call [IP] [порт] — позвонить собеседнику\n  /end              — положить трубку\n")
        
        # Открываем входной аудиопоток (микрофон) в фоновом режиме через callback
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', 
                             blocksize=BLOCKSIZE, callback=self.audio_input_callback):
            while True:
                cmd = input().strip()
                if cmd.startswith("/call"):
                    parts = cmd.split()
                    if len(parts) == 3:
                        t_ip = parts
                        t_port = int(parts)
                        self.target_address = (t_ip, t_port)
                        self.is_calling = True
                        print(f"[+] Вызов на {t_ip}:{t_port} начат. Вас слышно!")
                    else:
                        print("Использование: /call [IP] [порт]")
                        
                elif cmd == "/end":
                    self.is_calling = False
                    self.target_address = None
                    print("[*] Звонок завершен.")

if __name__ == "__main__":
    print("=== P2P LIGHT VOICE CALL ===")
    HOST = '0.0.0.0'  # Слушаем все интерфейсы (включая ZeroTier)
    
    while True:
        try:
            port_input = input("Введите ваш голосовой порт (например, 6000): ").strip()
            PORT = int(port_input)
            break
        except ValueError:
            print("Ошибка: Порт должен быть числом.")

    call_manager = P2PVoiceCall(HOST, PORT)
    call_manager.start()
