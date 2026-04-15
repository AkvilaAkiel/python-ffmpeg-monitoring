import subprocess
import re
import sys
import os
import concurrent.futures
import threading
from datetime import datetime

# --- НАЛАШТУВАННЯ ШЛЯХІВ ---
# Отримуємо абсолютний шлях до папки, де лежить цей скрипт
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Шукаємо channels.txt завжди поруч зі скриптом
CHANNELS_FILE = os.path.join(SCRIPT_DIR, "channels.txt")

def capture_screenshot(channel_name, url):
    # Генеруємо ім'я файлу з точним часом (наприклад: Setanta_2026-04-15_17-30-05.jpg)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Очищаємо ім'я каналу від спецсимволів, щоб Windows не лаявся на ім'я файлу
    safe_name = "".join([c for c in channel_name if c.isalnum() or c in ' _-']).rstrip()
    filename = f"error_{safe_name}_{timestamp}.jpg"
    
    screenshot_path = os.path.join(SCRIPT_DIR, filename)
    
    # Швидка команда FFmpeg для захоплення 1 кадру (-vframes 1)
    cmd = [
        'ffmpeg', '-y', # -y перезаписує файл, якщо такий є
        '-i', url,
        '-vframes', '1',
        '-q:v', '2', # Висока якість JPEG
        screenshot_path
    ]
    
    # Запускаємо без виводу логів, щоб не смітити в консолі
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"📸 Збережено скриншот аварії: {filename}")

def monitor_stream(channel_name, url):
    """
    Основна функція моніторингу для одного потоку.
    Працює в окремому процесі/потоці.
    """
    print(f"📡 [{channel_name}] Запуск моніторингу: {url}")
    
    # Базовий початок команди FFmpeg
    command = ['ffmpeg']
    
    # --- ДИНАМІЧНА "БРОНЯ" ЗАЛЕЖНО ВІД ПРОТОКОЛУ ---
    if url.startswith('http'):
        # HTTP/HLS: дозволяємо агресивний реконект
        command.extend([
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-rw_timeout', '10000000'
        ])
    elif url.startswith('srt'):
        # SRT: специфічні параметри (без HTTP-реконектів, які ламають логіку)
        command.extend([
            '-timeout', '10000000'
        ])
    # Для udp:// базові параметри
        
    # --- ЯДРО АНАЛІЗУ ---
    # fps=1 (економія CPU), blackdetect з м'якшими допусками для "брудного" сигналу
    command.extend([
        '-i', url,
        '-vf', 'fps=1,blackdetect=d=5:pix_th=0.08:pic_th=0.97',
        '-an', # вимикаємо звук
        '-f', 'null', '-' # не зберігаємо відео
    ])

    # Запускаємо процес
    process = subprocess.Popen(
        command,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace' # Захист від падіння Python через невідомі символи в логах
    )

    # --- РЕГУЛЯРНІ ВИРАЗИ ДЛЯ ПАРСИНГУ ЛОГІВ ---
    black_start_pattern = re.compile(r'black_start:([\d.]+)')
    black_end_pattern = re.compile(r'black_end:([\d.]+)')
    frame_pattern = re.compile(r'frame=\s*(\d+)')
    corrupt_pattern = re.compile(r'corrupt input|timestamp discontinuity|Stream ends prematurely', re.IGNORECASE)

    corrupt_error_count = 0 

    try:
        # Читаємо логи FFmpeg у реальному часі
        for line in process.stderr:
            # 1. ПУЛЬС
            frame_match = frame_pattern.search(line)
            if frame_match:
                frame_num = int(frame_match.group(1))
                if frame_num % 60 == 0 and frame_num > 0:
                    print(f"💓 [{channel_name}] Пульс: проаналізовано {frame_num} секунд...")

            # 2. ЧОРНИЙ ЕКРАН (Контентна проблема)
            start_match = black_start_pattern.search(line)
            if start_match:
                print(f"🚨 [{channel_name}] [CONTENT ERROR] Чорний екран на таймкоді: {start_match.group(1)}s")
                # РОБИМО СКРИНШОТ
                threading.Thread(target=capture_screenshot, args=(channel_name, url)).start()

            end_match = black_end_pattern.search(line)
            if end_match:
                print(f"✅ [{channel_name}] [CONTENT OK] Картинка відновилася: {end_match.group(1)}s")
                
            # 3. ДЕГРАДАЦІЯ ПОТОКУ (Проблема кодека/втрата пакетів)
            if corrupt_pattern.search(line):
                corrupt_error_count += 1
                if corrupt_error_count == 5:
                    print(f"⚠️ [{channel_name}] [STREAM DEGRADATION] Сигнал сильно пошкоджений!")
                elif corrupt_error_count % 50 == 0:
                    print(f"⚠️ [{channel_name}] [STREAM DEGRADATION] Потік нестабільний. Помилок: {corrupt_error_count}")
                
        # Чекаємо завершення процесу
        process.wait()
        
        # 4. МЕРЕЖЕВА ПОМИЛКА (Мертвий лінк / Сервер лежить)
        if process.returncode != 0:
            print(f"\n❌ [{channel_name}] [NETWORK ERROR] Мертвий лінк або сервер впав. (Код: {process.returncode})")

    except KeyboardInterrupt:
        process.terminate()

def main():
    print("="*50)
    print("🖥️  QA GOD MODE: Stream Monitor v1.0")
    print("="*50)

    # Перевіряємо, чи існує файл конфігурації
    if not os.path.exists(CHANNELS_FILE):
        print(f"❌ Файл {CHANNELS_FILE} не знайдено!")
        print("Будь ласка, створи його в тій самій папці та додай канали у форматі 'Назва,Посилання'")
        return

    channels = []
    # Читаємо файл
    with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue # Пропускаємо порожні рядки та коментарі
            
            # Розділяємо ім'я та посилання по першій комі
            parts = line.split(',', 1)
            if len(parts) == 2:
                channels.append((parts[0].strip(), parts[1].strip()))
            else:
                channels.append(("Unknown Channel", line.strip()))

    if not channels:
        print("❌ Список каналів порожній.")
        return

    print(f"🚀 Завантажено {len(channels)} каналів для моніторингу. Запускаємо потоки... (Натисни Ctrl+C для зупинки)\n")

    # Створюємо пул потоків (Multithreading). max_workers дорівнює кількості каналів.
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(channels)) as executor:
            # Запускаємо функцію monitor_stream для кожного каналу паралельно
            futures = [executor.submit(monitor_stream, name, url) for name, url in channels]
            # Чекаємо, поки всі потоки завершать роботу (натискання Ctrl+C або падіння всіх лінків)
            concurrent.futures.wait(futures)
    except KeyboardInterrupt:
        print("\n🛑 Моніторинг зупинено користувачем. Закриваємо всі процеси...")

if __name__ == "__main__":
    main()