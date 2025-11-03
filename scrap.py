import json
import pandas as pd
import time
from datetime import datetime, timedelta
import urllib.parse
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

COOKIES_FILE = "cookie.json"
TARGET_URL = "https://x.com/"
HASIL_FILE = "hasil_scraping.csv"

options = Options()
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--start-maximized")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Parameter pencarian
keyword = "Mark Zuckerberg" #sesuaikan keyword
start_date = "2025-01-1" 
end_date = "2025-01-30"
jumlah_tweet = 10000  # sesuaikan jumlah tweet yang ingin diambil
query = f"{keyword}"


def normalize_and_add_cookie(driver, raw):
    cookie = {"name": raw.get("name"), "value": raw.get("value")}
    if raw.get("domain"):
        cookie["domain"] = raw.get("domain")
    if raw.get("path"):
        cookie["path"] = raw.get("path")
    exp = raw.get("expirationDate") or raw.get("expires") or raw.get("expiry")
    if exp:
        try:
            cookie["expiry"] = int(float(exp))
        except:
            pass
    if raw.get("httpOnly") is not None:
        cookie["httpOnly"] = bool(raw.get("httpOnly"))
    if raw.get("secure") is not None:
        cookie["secure"] = bool(raw.get("secure"))

    try:
        driver.add_cookie(cookie)
        print("Added cookie:", cookie["name"])
    except Exception as e:
        print(f"Failed to add cookie {cookie.get('name')}: {e}")

def check_page_error():
    """Cek apakah halaman menunjukkan error Twitter"""
    try:
        err = driver.find_elements(By.XPATH, "//*[contains(text(), 'Something went wrong')]")
        if err:
            print("Halaman error terdeteksi! Reload otomatis...")
            driver.refresh()
            time.sleep(8)
            return True
    except:
        pass
    return False

def safe_scroll():
    """Scroll pelan dan acak untuk menghindari deteksi bot"""
    driver.execute_script("window.scrollBy(0, window.innerHeight / 1.5);")
    time.sleep(random.uniform(3, 6))

# ---------------------------
# Login & mulai scraping
# ---------------------------

try:
    driver.get(TARGET_URL)
    time.sleep(3)

    with open(COOKIES_FILE, "r") as f:
        raw_cookies = json.load(f)
    for rc in raw_cookies:
        normalize_and_add_cookie(driver, rc)

    driver.refresh()
    time.sleep(5)
    print("Login selesai. URL sekarang:", driver.current_url)

    query_encoded = urllib.parse.quote_plus(query)
    search_url = f"https://x.com/search?q={query_encoded}&src=typed_query"
    driver.get(search_url)
    time.sleep(5)

    tweets_seen = set()
    tweets = []
    retry_counter = 0

    while len(tweets) < jumlah_tweet:
        if check_page_error():
            retry_counter += 1
            if retry_counter > 5:
                print("Terlalu banyak error. Hentikan proses.")
                break
            continue

        elements = driver.find_elements(By.XPATH, '//article[@data-testid="tweet"]')

        if not elements:
            print("Tidak ada tweet terdeteksi, scroll lagi...")
            safe_scroll()
            continue

        for l in elements:
            try:
                konten = l.text.strip()
                if konten and konten not in tweets_seen:
                    tweets_seen.add(konten)

                    spans = l.find_elements(By.XPATH, ".//span")
                    texts = [s.text for s in spans if s.text.strip()]
                    full_text = " ".join(texts)

                    username = l.find_element(By.XPATH, ".//div[@dir='ltr']//span").text
                    waktu = l.find_element(By.XPATH, ".//time").get_attribute("datetime")

                    waktu_obj = datetime.fromisoformat(waktu.replace("Z", "+00:00"))
                    waktu_wib = waktu_obj + timedelta(hours=7)
                    waktu_str = waktu_wib.strftime("%d-%m-%Y %H:%M")

                    tweets.append({
                        "username": username,
                        "tweet": full_text,
                        "waktu": waktu_str
                    })

                    print(f"Tweet ke-{len(tweets)} dari @{username}")

                    if len(tweets) % 50 == 0:
                        df = pd.DataFrame(tweets)
                        df.to_csv(HASIL_FILE, index=False)
                        print(f"Disimpan sementara: {len(df)} tweet")

                    if len(tweets) >= jumlah_tweet:
                        break

            except Exception as e:
                print(f"Gagal baca tweet: {e}")
                continue

        safe_scroll()

    # Simpan hasil akhir
    df = pd.DataFrame(tweets)
    df.to_csv(HASIL_FILE, index=False)
    print(f"\nBerhasil menyimpan total {len(df)} tweet ke '{HASIL_FILE}'")

except WebDriverException as e:
    print("WebDriver error:", e)
finally:
    driver.quit()
