import socket
import threading
import sys
import numpy as np
import sounddevice as sd

# Настройки звука
RATE = 44100              # Частота дискретизации (CD-качество)
CHANNELS = 1              # Моно
CHUNK = 1024              # Размер буфера данных
VOLUME_MULTIPLIER = 3.0   # Множитель громкости (сделайте больше, если тихо)

class P2PVoiceCall:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.is_calling = False
        self.target_address = None
        
        # Создаем UDP сокет
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        
        # Очередь для входящего звука, чтобы избежать задержек воспроизведения
        self.audio_queue = []
        self.queue_lock = threading.Lock()
        
        print(f"[*] Голосовой модуль запущен на порту {self.port}")
        print(f"[*] Готов принимать звонки.")
        print("-" * 50)

    def start(self):
        # 1. Поток для чтения сети и автоответа
        receive_thread = threading.Thread(target=self.receive_audio_loop, daemon=True)
        receive_thread.start()
        
        # 2. Поток для записи микрофона и отправки в сеть
        send_thread = threading.Thread(target=self.send_audio_loop, daemon=True)
        send_thread.start()
        
        # 3. Запуск аудио-потока вывода (speaker) через sounddevice
        # Callback-функция берет куски звука из нашей очереди и играет их
        def playback_callback(outdata, frames, time, status):
            with self.queue_lock:
                if self.audio_queue:
                    data = self.audio_queue.pop(0)
                    if len(data) == len(outdata):
                        outdata[:] = data
                        return
                outdata.fill(0)

        speaker_stream = sd.OutputStream(
            samplerate=RATE, channels=CHANNELS, dtype='int16', 
            blocksize=CHUNK, callback=playback_callback
        )
        
        with speaker_stream:
            # Запускаем интерактивное меню в главном потоке
            self.menu_loop()

    def receive_audio_loop(self):
        """Принимает байты из сети, усиливает их и кладет в очередь на воспроизведение."""
        while True:
            try:
                # Читаем сырые байты из UDP-сокета
                data, addr = self.sock.recvfrom(4096)
                if data:
                    # Преобразуем байты в массив чисел int16
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # ---- ПРОГРАММНОЕ УСИЛЕНИЕ ГРОМКОСТИ ----
                    boosted_data = np.clip(audio_data * VOLUME_MULTIPLIER, -32768, 32767).astype(np.int16)
                    
                    # Изменяем форму массива под требования sounddevice (CHUNK, 1)
                    boosted_data = boosted_data.reshape(-1, CHANNELS)
                    
                    # Добавляем в очередь на воспроизведение
                    with self.queue_lock:
                        self.audio_queue.append(boosted_data)
                    
                    # ---- АВТО-ОТВЕТ ----
                    if not self.is_calling:
                        self.target_address = addr
                        self.is_calling = True
                        print(f"\n[+] Входящий звонок от {addr[0]}:{addr[1]}. Соединение установлено автоматически...")
            except Exception as e:
                print(f"\n[-] Ошибка сети/приема: {e}")
                break

    def send_audio_loop(self):
        """Захватывает звук с микрофона и отправляет по UDP, если идет звонок."""
        # Открываем микрофон на постоянное чтение
        mic_stream = sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype='int16', blocksize=CHUNK)
        with mic_stream:
            while True:
                if self.is_calling and self.target_address:
                    try:
                        # Читаем кусок звука из микрофона
                        audio_chunk, overflowed = mic_stream.read(CHUNK)
                        # Отправляем байты по UDP
                        self.sock.sendto(audio_chunk.tobytes(), self.target_address)
                    except Exception as e:
                        print(f"\n[-] Звонок сорвался при отправке: {e}")
                        self.is_calling = False
                        self.target_address = None
                else:
                    # Экономим процессор, если никто не говорит
                    threading.Event().wait(0.05)

    def menu_loop(self):
        """Интерактивное меню управления звонком."""
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
                    with self.queue_lock:
                        self.audio_queue.clear()
            except KeyboardInterrupt:
                sys.exit()

if __name__ == "__main__":
    print("=== P2P ЗВОНКИ (sounddevice вместо pyaudio) ===")
    
    # 0.0.0.0 слушает все интерфейсы, включая локалку и ZeroTier
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

