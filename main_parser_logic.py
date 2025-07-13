import json
import re
import requests
from bs4 import BeautifulSoup
from time import sleep
import os
import zipfile
import shutil
from pathlib import Path
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
}

def download_image_threaded(args):
    url, folder, filename = args
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            with open(os.path.join(folder, filename), 'wb') as f:
                f.write(response.content)
            return filename
    except Exception as e:
        print(f"[!] Ошибка загрузки: {url} | {e}")
    return None


def save_all_images(soup, save_dir):
    image_urls = set()

    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "ImageObject":
                url = data.get("contentUrl")
                if url:
                    image_urls.add(url)
        except Exception as e:
            print(f"[!] Ошибка парсинга JSON-LD: {e}")

    gallery_items = soup.find_all("li", class_="imagegallery--item")
    for li in gallery_items:
        img_tag = li.find("img")
        if img_tag and img_tag.get("src"):
            image_urls.add(img_tag["src"])

    tasks = []
    for idx, url in enumerate(image_urls, start=1):
        filename = f"{idx}.jpg"
        tasks.append((url, save_dir, filename))

    saved_paths = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(download_image_threaded, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            if result:
                saved_paths.append(os.path.join(save_dir, result))

    return list(image_urls)


def zip_folder(folder_path):
    zip_path = str(folder_path) + ".zip"
    shutil.make_archive(folder_path, 'zip', folder_path)
    shutil.rmtree(folder_path)
    return zip_path


def extract_price(text):
    clean_text = text.replace('.', '').replace('VB', '1').replace('€', '')
    match = re.search(r'\d+', clean_text)
    return int(match.group()) if match else None


def modify_url_for_page(base_url, page_number):
    if "/k0" in base_url:
        return re.sub(r'(/s-.*?/)(.*?)(/k0)', fr'\1seite:{page_number}/\2\3', base_url)
    elif "/c" in base_url:
        return re.sub(r'(/seite:\d+)?/c', f'/seite:{page_number}/c', base_url)
    return base_url


def parse_ads(url_list, min_price=1, min_views=1, max_pages=2, start_page=1):

    for base_url in url_list:
        print(f"Обработка: {base_url}")

        ad_links = set()
        ad_dates = []

        for page in range(start_page, max_pages + 1):
            page_url = modify_url_for_page(base_url, page)
            print(f" -> Страница: {page_url}")
            sleep(1)

            response = requests.get(page_url, headers=HEADERS)
            soup = BeautifulSoup(response.text, "lxml")
            ad_items = soup.find_all("div", class_="aditem-main")

            for item in ad_items:
                if item.find("div", class_="badge-hint-pro-small-srp"):
                    continue
                if item.find("li", class_="ad-listitem lazyload-item   badge-topad is-topad"):
                    continue

                date_icon = item.find("i", class_="icon icon-small icon-calendar-open")
                if not date_icon:
                    continue
                date_text = date_icon.next_sibling.strip()
                ad_dates.append(date_text)

                price_tag = item.find("p", class_="aditem-main--middle--price-shipping--price")
                if not price_tag:
                    continue
                price = extract_price(price_tag.text)
                if price is None or price < min_price:
                    continue

                a_tag = item.find("a")
                if not a_tag:
                    continue
                card_url = "https://www.kleinanzeigen.de" + a_tag.get("href")
                ad_links.add(card_url)

        for card_url in ad_links:
            sleep(1)
            ad_id_match = re.search(r'\d{10}', card_url)
            if not ad_id_match:
                continue
            ad_id = ad_id_match.group()

            view_url = f"https://www.kleinanzeigen.de/s-vac-inc-get.json?adId={ad_id}"
            try:
                views_resp = requests.get(view_url, headers=HEADERS)
                card_resp = requests.get(card_url, headers=HEADERS)

                views_json = views_resp.json()
                views = views_json.get("numVisits", 0)
                if views < min_views:
                    continue

                soup = BeautifulSoup(card_resp.text, "lxml")
                data_box = soup.find("div", class_="contentbox--vip boxedarticle no-shadow l-container-row")
                if not data_box:
                    continue

                title = data_box.find("h1").get_text(strip=True)
                price_text = data_box.find("h2").get_text(strip=True)
                date_posted = ad_dates.pop(0) if ad_dates else "N/A"

                folder_name = re.sub(r'[^\w\s.-]', '_', title).strip()[:50]
                save_dir = Path("products") / folder_name
                save_dir.mkdir(parents=True, exist_ok=True)

                image_urls = save_all_images(soup, save_dir)
                zip_path = zip_folder(str(save_dir))

                yield views, price_text, card_url, title, date_posted, ", ".join(image_urls), zip_path


            except json.JSONDecodeError as e:
                print(f"[!] JSON Error: {e}")
                continue


def save_to_excel(data, filename="result.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kl Ads"

    ws.append(["Просмотры", "Цена", "Ссылка", "Название", "Дата", "Фото (все)", "Архив"])

    for row in data:
        ws.append(row)

    wb.save(filename)
    print(f"Готово")
