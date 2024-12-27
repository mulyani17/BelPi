import requests
import subprocess
import time
import datetime
import os
import pygame
import threading
import socket
import netifaces as ni
import random
import RPi.GPIO as GPIO

  

os.environ['DISPLAY'] = ':0'
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1000'  # Sesuaikan ID pengguna jika perlu


# URL Google Apps Script
url = 'https://script.google.com/macros/s/AKfycbyTLLeq8AvtVsS_Bg_nTm4AMmZLrHvAFuou5FywpRiYizBvsLEJUBGNj-aUXxMfwvgc/exec?sts=read'

# Path direktori MP3
MP3_DIRECTORY = '/home/m/Pi/'

# MP3 yang ingin dimainkan sekali saat startup
STARTUP_MP3 = os.path.join(MP3_DIRECTORY, '011_Win_Log_On')

# Variabel global untuk menyimpan proses MP3 dan data jadwal
current_mp3_process = None
schedule = []



def get_next_schedule():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"Current Time: {now}")
    for entry in schedule:
        time_str, file_no, file_name = entry
        if time_str > now:
            return f"{time_str} - {file_name}"
    return "No upcoming events"

def fetch_data():
    global schedule
    print("Mengambil data dari Google Apps Script...")
    response = requests.get(url)
    if response.status_code == 200:
        print("Berhasil mengambil data!")
        raw_data = response.text.split(';')
        schedule = []
        for item in raw_data:
            parts = item.split(',')
            if len(parts) == 3:
                try:
                    time_str, file_no, file_name = parts
                    time_str = time_str.strip()
                    file_no = file_no.strip()
                    file_name = file_name.strip()
                    if time_str and file_no and file_name:
                        schedule.append((time_str, file_no, file_name))
                except ValueError:
                    print(f"Baris tidak valid: {item}")
                    continue
        print("Data yang diambil:", schedule)
        schedule = schedule
        return schedule
    else:
        print(f"Gagal mengambil data: {response.status_code}")
        return []

def get_ip_address(interface='wlan0'):
    try:
        ip = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
        return ip
    except KeyError:
        return "IP not available"

def set_volume(volume_percent):
    """
    Mengatur volume sistem menggunakan amixer.
    volume_percent: Angka antara 0-100 untuk mengatur volume.
    """
    try:
        subprocess.run(['amixer', 'set', 'Master', f'{volume_percent}%'], check=True)
        print(f"Volume set to {volume_percent}%")
    except Exception as e:
        print(f"Failed to set volume: {e}")



def play_mp3(file_name):
    global schedule  # Pastikan 'schedule' bisa diakses
    now = datetime.datetime.now()
    next_schedule_time = None  # Beri nilai awal untuk variabel
    global current_mp3_process, schedule
    set_volume(100)

    if current_mp3_process:
        print("Stopping current MP3")
        current_mp3_process.terminate()
        current_mp3_process.wait()
        
    file_path = os.path.join(MP3_DIRECTORY, file_name + ".mp3")

    if os.path.isfile(file_path):
        print(f"Playing file: {file_path}")
        current_mp3_process = subprocess.Popen(['/usr/bin/mpg123', file_path])
    else:
        folder_path = os.path.join(MP3_DIRECTORY, file_name)
        if os.path.isdir(folder_path):
            mp3_files = [f for f in os.listdir(folder_path) if f.endswith('.mp3')]
            if mp3_files:
                print(f"Playing all MP3 files in random order from folder: {folder_path}")
                random.shuffle(mp3_files)
                set_volume(50)
                putar = True
                for mp3_file in mp3_files:
                    file_path = os.path.join(folder_path, mp3_file)
                    print(f"Playing: {file_path}")
                    current_mp3_process = subprocess.Popen(['/usr/bin/mpg123',file_path])

                    while current_mp3_process.poll() is None:
                        now = datetime.datetime.now()
                        if schedule:
                            
                            # Ambil jadwal berikutnya
                            upcoming_schedules = [
                                datetime.datetime.strptime(entry[0], "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                                for entry in schedule if datetime.datetime.strptime(entry[0], "%H:%M").replace(year=now.year, month=now.month, day=now.day) > now
                            ]

                            if upcoming_schedules:
                                next_schedule_time = min(upcoming_schedules)  # Ambil jadwal terdekat
                                print(f"Next schedule time: {next_schedule_time}")

                            # Logika berikutnya menggunakan 'next_schedule_time'
                            if next_schedule_time and (next_schedule_time - now <= datetime.timedelta(minutes=1)) and (next_schedule_time > now):
                                print(f"Time is within one minute of the next schedule: {next_schedule_time}")
                                # Lakukan sesuatu sesuai jadwal
                                print(f"Stopping playback for schedule at {next_schedule_time}.")
                                putar = False
                                current_mp3_process.terminate()
                                break
                            else:
                                print("Time is not within one minute of the next schedule.")
                                print(f"Next : {next_schedule_time}, Now : {now}, Datetima : {datetime.timedelta(minutes=1)} ")
                            time.sleep(30)

def schedule_job():
    global schedule, current_mp3_process
    played_schedules = set()

    while True:
        now = datetime.datetime.now()
        
        # Filter jadwal yang belum lewat
        upcoming_schedule = [
            (time_str, file_no, file_name) for (time_str, file_no, file_name) in schedule
            if datetime.datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day) > now
        ]

        if not upcoming_schedule:
            print("No upcoming schedules. Exiting.")
            break

        next_time_str, file_no, file_name = upcoming_schedule[0]
        next_schedule_time = datetime.datetime.strptime(next_time_str, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
               
            
        # Tunggu hingga waktu jadwal berikutnya
        sleep_duration = (next_schedule_time - now).total_seconds()
        if sleep_duration > 0:
            print(f"Waiting for the next schedule at {next_schedule_time}.")
            time.sleep(sleep_duration)
        
        # Mainkan MP3 sesuai jadwal
        print(f"Executing schedule: {next_schedule_time} - {file_name}")
        play_mp3(file_name)
        played_schedules.add((next_time_str, file_no, file_name))

        # Hapus jadwal yang sudah dimainkan
        schedule = [entry for entry in schedule if entry not in played_schedules]
        
def stop_all_mp3():
    """Fungsi untuk menghentikan semua MP3."""
    global current_mp3_process
    if current_mp3_process:
        print("Stopping current MP3 playback...")
        current_mp3_process.terminate()
        current_mp3_process.wait()
        current_mp3_process = None


def run_gui():
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # Fullscreen mode
    pygame.display.set_caption("Jam dan Jadwal Berikutnya")

    font_large = pygame.font.SysFont("Stencil", 300)  # Memperbesar ukuran font jam
    font_small = pygame.font.SysFont("Helvetica", 72)
    font_credit = pygame.font.SysFont("Helvetica", 32)
    font_title = pygame.font.SysFont("Arial Black", 110)  # Font untuk judul

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((0, 0, 0))  # Background hitam
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        next_schedule = get_next_schedule()

        # Render teks
        title_surface = font_title.render("SMA Al-Azhar Syifa Budi Solo", True, (255, 255, 255))
        time_surface = font_large.render(current_time, True, (255, 255, 255))
        schedule_surface = font_small.render(f"Next: {next_schedule}", True, (255, 255, 255))
        ip_surface = font_credit.render(f"IP: {get_ip_address()}", True, (255, 255, 255))
        credit_surface = font_credit.render("created by [M] ft https://chatgpt.com", True, (255, 255, 255))  # Kredit dalam dua baris

        # Menghitung posisi agar teks rata tengah
        screen_width, screen_height = screen.get_size()
        title_rect = title_surface.get_rect(center=(screen_width / 2, screen_height / 2 - 200))
        time_rect = time_surface.get_rect(center=(screen_width / 2, screen_height / 2 - 50))
        schedule_rect = schedule_surface.get_rect(center=(screen_width / 2, screen_height / 2 + 75))
        ip_rect = ip_surface.get_rect(center=(screen_width / 2, screen_height / 2 + 130))  # Mengurangi jarak
        credit_rect = credit_surface.get_rect(center=(screen_width / 2, screen_height - 50))

        # Menggambar teks di layar
        screen.blit(title_surface, title_rect)
        screen.blit(time_surface, time_rect)
        screen.blit(schedule_surface, schedule_rect)
        screen.blit(ip_surface, ip_rect)
        screen.blit(credit_surface, credit_rect)
        
        
        pygame.display.flip()
        clock.tick(30)  # 30 FPS

    pygame.quit()
    
def play_startup_mp3():
    """Mainkan MP3 Win Logon saat startup."""
    play_mp3(STARTUP_MP3)

def play_previous_schedule():
    now = datetime.datetime.now()

    # Filter jadwal yang sudah lewat
    past_schedules = [
        datetime.datetime.strptime(entry[0], "%H:%M").replace(year=now.year, month=now.month, day=now.day)
        for entry in schedule if datetime.datetime.strptime(entry[0], "%H:%M").replace(year=now.year, month=now.month, day=now.day) < now
    ]

    if past_schedules:
        # Ambil jadwal sebelumnya (jadwal terakhir sebelum sekarang)
        previous_schedule_time = max(past_schedules)
        print(f"Previous schedule time: {previous_schedule_time.strftime('%H:%M')}")

        # Cari nama file berdasarkan jadwal sebelumnya
        for time_str, file_no, file_name in schedule:
            if time_str == previous_schedule_time.strftime("%H:%M"):
                print(f"Playing schedule: {file_name} (File No: {file_no})")
                # Panggil fungsi play_mp3 di sini
                play_mp3(file_name)
                return
    else:
        print("No previous schedules found.")

# Fungsi utama untuk menginisialisasi jadwal dan memutar jadwal sebelumnya
def fetch_and_play():
    """
    Ambil data jadwal, lalu mainkan jadwal yang terlewat jika diperlukan.
    """
    fetch_data()  # Mengambil data dari Google Apps Script
    play_startup_mp3()  # Mainkan MP3 startup
    play_previous_schedule()  # Mainkan jadwal sebelumnya jika ada


# Panggil fungsi ini saat sistem startup
fetch_and_play()

#play_mp3(STARTUP_MP3)
time.sleep(0)
#fetch_data()
threading.Thread(target=schedule_job, daemon=True).start()
run_gui()


