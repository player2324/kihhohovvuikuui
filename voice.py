import socket
import threading
import pyaudio
import sys
import numpy as np

# Настройки аудио-потока
CHUNK = 1024              # Фиксированный размер буфера
FORMAT = pyaudio.paInt16  # 16-битный звук
CHANNELS = 1              # Моно
RATE = 44100              # CD-качество

class P2PVoiceCall:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.is_calling = False
        self.target_address = None
        
        # UDP сокет
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        
        # Инициализация PyAudio
        self.p = pyaudio.PyAudio()
        
        # Открываем потоки с жестко заданным CHUNK для стабильности в Windows
        self.speaker = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
        self.microphone = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        
        print(f"[*] Голосовой модуль запущен на порту {self.port}")
        print(f"[*] Готов принимать звонки.")
        print("-" * 50)

    def start(self):
        # Поток приема аудио и авто-ответа
        receive_thread = threading.Thread(target=self.receive_audio_loop, daemon=True)
        receive_thread.start()
        
        # Основной поток отправки
        send_thread = threading.Thread(target=self.send_audio_loop, daemon=True)
        send_thread.start()
        
        # Интерактивное меню
        self.menu_loop()

    def receive_audio_loop(self):
        """Принимает байты звука, увеличивает громкость и делает авто-ответ."""
        while True:
            try:
                # Читаем фиксированный буфер (напрямую CHUNK * 2 байта для 16-бит моно)
                data, addr = self.sock.recvfrom(4096)
                if data:
                    # ---- КОРРЕКЦИЯ ГРОМКОСТИ ----
                    # Декодируем байты в числа int16
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    # Умножаем громкость на 2.5 (поднимите до 4.0, если все еще тихо)
                    boosted_data = np.clip(audio_data * 2.5, -32768, 32767).astype(np.int16)
                    
                    # Воспроизводим полученный чистый кусок данных
                    self.speaker.write(boosted_data.tobytes())
                    
                    # ---- АВТО-ОТВЕТ (РЕШАЕТ ПРОБЛЕМУ ВТОРОГО /CALL) ----
                    if not self.is_calling:
                        self.target_address = addr
                        self.is_calling = True
                        print(f"\n[+] Входящий звонок от {addr[0]}:{addr[1]}. Соединение установлено автоматически...")
            except Exception as e:
                print(f"\n[-] Ошибка воспроизведения: {e}")
                break

    def send_audio_loop(self):
        """Постоянно проверяет флаг звонка и шлет звук микрофона собеседнику."""
        while True:
            if self.is_calling and self.target_address:
                try:
                    # Читаем строго CHUNK из микрофона
                    audio_data = self.microphone.read(CHUNK, exception_on_overflow=False)
                    # Шлем напрямую на сохраненный адрес
                    self.sock.sendto(audio_data, self.target_address)
                except Exception as e:
                    print(f"\n[-] Звонок сорвался: {e}")
                    self.is_calling = False
                    self.target_address = None
            else:
                # Если звонка нет, не нагружаем процессор
                threading.Event().wait(0.1)

    def menu_loop(self):
        """Интерактивное меню."""
        print("Команды:\n  /call [IP] [порт] — позвонить собеседнику\n  /end              — положить трубку\n")
        
        while True:
            try:
                cmd = input().strip()
                if not cmd:
                    continue
                    
                if cmd.startswith("/call"):
                    parts = cmd.split()
                    if len(parts) == 3:
                        t_ip = parts[1]
                        t_port = int(parts[2])
                        
                        self.target_address = (t_ip, t_port)
                        self.is_calling = True
                        print(f"[+] Вызываем {t_ip}:{t_port}...")
                    else:
                        print("Использование: /call [IP] [порт]")
                        
                elif cmd == "/end":
                    print("[*] Звонок завершен.")
                    self.is_calling = False
                    self.target_address = None
            except KeyboardInterrupt:
                sys.exit()

if __name__ == "__main__":
    print("=== P2P ЗВОНКИ (Фикс Громкости и Автоответ) ===")
    
    # Рекомендуется использовать '0.0.0.0', чтобы скрипт слушал все интерфейсы сразу
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
