import hashlib
import json
import re
import requests
import os
import shutil
import subprocess
from bs4 import BeautifulSoup
import collections
import datetime
import itertools
import jinja2
import pathlib
import tempfile
import uuid
import zipfile
from dotenv import load_dotenv

load_dotenv()

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0',
    'Accept': '*/*',
    'Accept-Language': 'ru,en-US;q=0.7,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://ranobelib.me/',
    'Site-Id': '3',
    'Content-Type': 'application/json',
    'Client-Time-Zone': 'Asia/Krasnoyarsk',
    'Origin': 'https://ranobelib.me',
    'DNT': '1',
    'Sec-GPC': '1',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
    'Connection': 'keep-alive'
}
# Токен авторизации для ранобе доступных только авторизованным пользователям
token = None
if token:
    if not token.startswith("Bearer "):
        token = "Bearer " + token
    headers['Authorization'] = token

style = """
@page {
    margin-bottom: 5pt;
    margin-top: 5pt
    }

.block_ {
    display: block;
    font-size: 0.83333em;
    line-height: 1.2;
    text-align: center;
    margin: 0 0 10pt;
    padding: 0
    }
.block_1 {
    display: block;
    font-family: serif;
    font-size: 0.83333em;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_2 {
    display: block;
    font-size: 0.83333em;
    line-height: 1.2;
    text-align: center;
    margin: 0 0 10pt;
    padding: 0
    }
.block_3 {
    display: block;
    font-size: 1.29167em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_4 {
    display: block;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_5 {
    display: block;
    font-size: 0.83333em;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_6 {
    display: block;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_7 {
    display: block;
    font-size: 1.29167em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_8 {
    display: block;
    font-size: 1em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_9 {
    display: block;
    font-size: 1em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_10 {
    display: block;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_11 {
    display: block;
    font-size: 1.29167em;
    font-weight: normal;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.calibre {
    color: black;
    display: block;
    font-family: "Arial", sans-serif;
    font-size: 1em;
    padding-left: 0;
    padding-right: 0;
    margin: 0 5pt
    }
.calibre1 {
    display: block;
    height: auto;
    line-height: 1.2;
    width: auto
    }
.calibre2 {
    font-size: 1em;
    line-height: 1.2;
    vertical-align: super
    }
.calibre3 {
    font-size: 0.75em;
    line-height: 1.2;
    vertical-align: super
    }
.calibre4 {
    line-height: 1.2
    }
.calibre5 {
    display: block;
    font-size: 1.29167em;
    line-height: 1.2
    }
.calibre6 {
    line-height: 1.2;
    text-decoration: none
    }
.calibre7 {
    display: block;
    margin-left: 40px
    }
.footnote {
    display: block;
    margin: 1em 0
    }
.footnote1 {
    display: block;
    page-break-after: avoid;
    margin: 1em 0
    }
.noteref {
    text-decoration: none
    }
.text_ {
    font-size: 1.2em;
    line-height: 1.2
    }

"""


def get_ranobe_name_from_url(url: str) -> str | bool:
    url = url.strip()
    if url.startswith("https://") and "/read/" in url:
        url = url.split("//")[1].split("/")[2]
    elif url.startswith("https://"):
        url = url.split("//")[1].split("/")[3].split("?")[0]
    else:
        return False
    return url

def remove_bad_chars(text: str) -> str:
    return ''.join(c for c in text if c not in r'"?<>|\/:–')



# Matches a leading "Глава X" token (any case) + optional separator so it can be
# stripped from chapter names like "ГЛАВА 1 Название" or "Глава 1. Название".
# \S+ captures the chapter number/id (e.g. "1", "1.5", "1."); [.\s]* eats any
# trailing period/space that was part of the separator.
_CHAPTER_PREFIX_RE = re.compile(
    r'^[Гг][Лл][Аа][Вв][Аа]\s+\S+[.\s]*',
    re.UNICODE,
)


def make_chapter_title(chapter_num: str, chapter_name: str) -> str:
    """Return a formatted chapter title without redundant repetition.

    Strips any leading "Глава N" prefix from chapter_name (case-insensitive)
    before composing the title, so names like "ГЛАВА 1 Прибыл коллега..."
    become "Глава 1. Прибыл коллега..." instead of "Глава 1. ГЛАВА 1 Прибыл...".

    Returns "Глава N" when chapter_name is empty or contained nothing beyond
    the redundant prefix.
    """
    name = _CHAPTER_PREFIX_RE.sub('', chapter_name).strip()
    if not name:
        return f"Глава {chapter_num}"
    return f"Глава {chapter_num}. {name}"


def extract_text_from_prosemirror(node) -> str:
    """Recursively extract plain text from a ProseMirror/TipTap JSON doc.

    Accepts either a dict (the doc root or any node) or a plain string
    (legacy API), so it is safe to call on any summary value.
    """
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    node_type = node.get("type", "")
    parts = []
    for child in node.get("content", []):
        text = extract_text_from_prosemirror(child)
        if text:
            parts.append(text)
    # doc / blockquote / lists: contain block children → join with newline
    # paragraph / heading / listItem: contain inline children → join with ""
    block_container = node_type in ("doc", "blockquote", "bulletList", "orderedList")
    return "\n".join(parts) if block_container else "".join(parts)


def detect_image_ext(data: bytes) -> str:
    """Detect image file extension from magic bytes. Falls back to 'jpg'."""
    magic_numbers = {
        b'\xFF\xD8\xFF': 'jpg',
        b'\x89PNG\r\n': 'png',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'RIFF': 'webp',
    }
    for magic, ext in magic_numbers.items():
        if data.startswith(magic):
            return ext
    return 'jpg'


DEFAULT_BANNER_CACHE_FILE = ".ad_banners_cache.json"


def load_ad_banners_cache(cache_path: str = DEFAULT_BANNER_CACHE_FILE) -> set[str]:
    """Load persistent set of confirmed ad banner SHA-256 hashes."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict):
                    return set(data.get("banners", []))
        except Exception as e:
            print(f"Не удалось загрузить кэш баннеров из {cache_path}: {e}")
    return set()


def save_ad_banners_cache(hashes: set[str], cache_path: str = DEFAULT_BANNER_CACHE_FILE):
    """Save persistent set of confirmed ad banner SHA-256 hashes."""
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(hashes)), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Не удалось сохранить кэш баннеров в {cache_path}: {e}")


def display_terminal_image(image_path: str, max_cols: int = 80, max_rows: int = 25) -> bool:
    """Display an image directly in the terminal using Sixel or Unicode symbols.

    Returns True if successfully displayed, False otherwise.
    """
    if not os.path.exists(image_path):
        return False

    term_size = shutil.get_terminal_size((80, 24))
    cols = min(term_size.columns, max_cols)
    rows = min(max(10, term_size.lines - 5), max_rows)

    # 1. Try chafa with Sixel format (optimal quality and automatic sizing)
    if shutil.which("chafa"):
        try:
            res = subprocess.run(
                ["chafa", "-f", "sixels", "-s", f"{cols}x{rows}", image_path],
                check=False
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 2. Try img2sixel
    if shutil.which("img2sixel"):
        try:
            res = subprocess.run(
                ["img2sixel", "-w", f"{cols * 8}px", image_path],
                check=False
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 3. Fallback to chafa symbols (Unicode 24-bit half-blocks, universal terminal support)
    if shutil.which("chafa"):
        try:
            res = subprocess.run(
                ["chafa", "-f", "symbols", "-s", f"{cols}x{rows}", image_path],
                check=False
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


class ImageManager:
    """Manages downloading, deduplicating, referencing, and tracking banner images."""

    def __init__(self, folder_name: str, book=None, headers: dict | None = None, banner_cache_path: str = DEFAULT_BANNER_CACHE_FILE):
        self.folder_name = folder_name
        self.book = book
        self.headers = headers or {}
        self.url_to_hash: dict[str, str] = {}
        self.hash_to_image: dict[str, dict] = {}
        self.added_to_book: set[str] = set()
        self.banner_cache_path = banner_cache_path
        self.known_banners = load_ad_banners_cache(banner_cache_path)
        self.whitelisted_hashes: set[str] = set()
        # hash -> list of occurrences
        self.image_occurrences: dict[str, list[dict]] = collections.defaultdict(list)

    def process_image(
        self,
        img_url: str,
        img_key: str,
        chapter_num: str = "",
        image_counter: int = 1,
        is_near_end: bool = False,
        is_near_start: bool = False,
    ) -> tuple[str, str, bool]:
        """Download or reuse an image based on URL and content hash.

        Returns:
            (epub_img_path, folder_img_path, is_duplicate)
        """
        # 1. URL cache hit
        if img_url in self.url_to_hash:
            img_hash = self.url_to_hash[img_url]
            entry = self.hash_to_image[img_hash]
            entry['ref_count'] += 1
            self.image_occurrences[img_hash].append({
                'chapter_num': str(chapter_num),
                'is_near_end': is_near_end,
                'is_near_start': is_near_start,
            })
            print(f"  [Повторный арт] Гл. {chapter_num}: изображение уже скачано ({entry['canonical_name']}), повторно используем.")
            return entry['epub_path'], entry['disk_path'], True

        # 2. Download image
        try:
            response = requests.get(img_url, headers=self.headers)
            response.raise_for_status()
            img_bytes = response.content
        except Exception as e:
            print(f"  [Ошибка загрузки арта] Гл. {chapter_num}: {e}")
            folder_img_path = f"{self.folder_name}images/{img_key}.jpg"
            return f"images/{img_key}.jpg", folder_img_path, False

        # 3. Content hash check
        img_hash = hashlib.sha256(img_bytes).hexdigest()
        self.url_to_hash[img_url] = img_hash
        self.image_occurrences[img_hash].append({
            'chapter_num': str(chapter_num),
            'is_near_end': is_near_end,
            'is_near_start': is_near_start,
        })

        if img_hash in self.hash_to_image:
            entry = self.hash_to_image[img_hash]
            entry['ref_count'] += 1
            print(f"  [Повторный арт] Гл. {chapter_num}: найден дубликат изображения ({entry['canonical_name']}), повторно используем.")
            return entry['epub_path'], entry['disk_path'], True

        # 4. New unique image
        ext = detect_image_ext(img_bytes)
        canonical_name = f"{img_key}.{ext}"
        folder_img_path = f"{self.folder_name}images/{canonical_name}"
        epub_img_path = f"images/{canonical_name}"

        try:
            with open(folder_img_path, 'wb') as f:
                f.write(img_bytes)
        except Exception as e:
            print(f"  [Ошибка сохранения арта] {folder_img_path}: {e}")

        if self.book:
            self.book.add_image(canonical_name, img_bytes)
            self.added_to_book.add(canonical_name)

        self.hash_to_image[img_hash] = {
            'canonical_name': canonical_name,
            'disk_path': folder_img_path,
            'epub_path': epub_img_path,
            'ref_count': 1,
            'hash': img_hash,
        }
        print(f"Загрузка арта {chapter_num}-{image_counter}")
        return epub_img_path, folder_img_path, False

    def find_suspicious_banners(self, min_repeats: int = 2) -> list[dict]:
        """Find images that appear in multiple chapters at the end or start."""
        suspicious = []
        for img_hash, entry in self.hash_to_image.items():
            if img_hash in self.whitelisted_hashes:
                continue

            occurrences = self.image_occurrences.get(img_hash, [])
            distinct_chapters = set(occ['chapter_num'] for occ in occurrences)
            total_chapters = len(distinct_chapters)

            end_or_start_occs = [occ for occ in occurrences if occ['is_near_end'] or occ['is_near_start']]
            end_or_start_chapters = len(set(occ['chapter_num'] for occ in end_or_start_occs))

            is_known = img_hash in self.known_banners

            if is_known or (total_chapters >= min_repeats and end_or_start_chapters >= 2):
                def _sort_key(ch):
                    try:
                        return float(ch)
                    except ValueError:
                        return 9999.0

                suspicious.append({
                    'hash': img_hash,
                    'canonical_name': entry['canonical_name'],
                    'disk_path': entry['disk_path'],
                    'epub_path': entry['epub_path'],
                    'total_chapters': total_chapters,
                    'end_or_start_chapters': end_or_start_chapters,
                    'chapter_nums': sorted(list(distinct_chapters), key=_sort_key),
                    'is_known': is_known,
                })
        return suspicious


def review_ad_banners(image_manager: ImageManager, book, min_repeats: int = 2):
    """Review suspicious recurring banner images and purge confirmed ones."""
    if not image_manager or not book:
        return

    suspicious = image_manager.find_suspicious_banners(min_repeats=min_repeats)
    if not suspicious:
        return

    print("\n" + "=" * 65)
    print("  ПРОВЕРКА РЕКЛАМНЫХ БАННЕРОВ В КОНЦЕ/НАЧАЛЕ ГЛАВ")
    print("=" * 65)

    for item in suspicious:
        canonical_name = item['canonical_name']
        img_hash = item['hash']
        disk_path = item['disk_path']
        ch_list = item['chapter_nums']
        total_ch = item['total_chapters']
        end_start_ch = item['end_or_start_chapters']
        is_known = item['is_known']

        if is_known:
            print(f"\n[!] Известный рекламный баннер из кэша: '{canonical_name}' (хэш {img_hash[:8]})")
            print(f"    Встретился в {total_ch} глав(ах): {', '.join(ch_list[:15])}{'...' if len(ch_list) > 15 else ''}")
            purged = book.purge_image(canonical_name)
            local_file = os.path.join(image_manager.folder_name, "images", canonical_name)
            if os.path.exists(local_file):
                try:
                    os.remove(local_file)
                except Exception:
                    pass
            print(f"    [УДАЛЕН БАННЕР] Автоматически удален из {purged} глав(ы).")
            continue

        print(f"\n[?] Подозрительное изображение: '{canonical_name}'")
        print(f"    Встретилось в {total_ch} глав(ах), из них {end_start_ch} раз(а) на границе глав:")
        print(f"    Главы: {', '.join(ch_list[:20])}{'...' if len(ch_list) > 20 else ''}")
        print(f"    Файл: {disk_path}")

        print("\nПредпросмотр изображения:")
        displayed = display_terminal_image(disk_path)
        if not displayed:
            print("  (Терминал не поддерживает sixel/chafa, откройте файл вручную)")

        while True:
            print("\nЧто сделать с этим изображением?")
            print("  1. Удалить из ВСЕХ глав (рекламный баннер) [По умолчанию: Enter / 1]")
            print("  2. Оставить во всех главах (сюжетная иллюстрация / арт)")
            print("  3. Открыть во внешнем просмотрщике (xdg-open)")
            choice = input("Выберите действие (1/2/3, по умолчанию 1): ").strip()

            if choice in ("", "1"):
                purged = book.purge_image(canonical_name)
                image_manager.known_banners.add(img_hash)
                save_ad_banners_cache(image_manager.known_banners, image_manager.banner_cache_path)
                local_file = os.path.join(image_manager.folder_name, "images", canonical_name)
                if os.path.exists(local_file):
                    try:
                        os.remove(local_file)
                    except Exception:
                        pass
                print(f"  [УДАЛЕН БАННЕР] '{canonical_name}' удален из {purged} глав(ы) и добавлен в кэш баннеров.")
                break
            elif choice == "2":
                image_manager.whitelisted_hashes.add(img_hash)
                print(f"  [ОСТАВЛЕНО] '{canonical_name}' сохранено в книге.")
                break
            elif choice == "3":
                if shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", disk_path])
                    print("  Открыто в просмотрщике системы.")
                else:
                    print(f"  xdg-open не найден. Путь к файлу: {disk_path}")
            else:
                print("  Неверный ввод. Введите 1, 2 или 3.")

    print("=" * 65 + "\n")


class BadLinesFilter:
    """Intelligent advertisement and translator plug cleaner with false-positive safeguards."""

    _URL_RE = re.compile(
        r"(?:https?://\S+|t\.me/\S+|vk\.com/\S+|vk\.me/\S+|boosty\.to/\S+|patreon\.com/\S+|discord(?:\.gg|app\.com)/\S+|donationalerts\.(?:ru|com)/\S+|yoomoney\.ru/\S+)",
        re.IGNORECASE
    )
    _TG_HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{3,}")

    _CREDIT_KEYWORD_RE = re.compile(
        r"(?:"
        r"работал[аио]?\s+над\s+переводом|"
        r"над\s+переводом\s+работал[аио]?|"
        r"перевод(?:чик)?\s*:|"
        r"редакт(?:ор|ура)\s*:|"
        r"вычитка\s*:|"
        r"тайп(?:ер)?\s*:|"
        r"бета\s*:|"
        r"клинер\s*:|"
        r"анлейт\s*:|"
        r"команда\s+перевода|"
        r"переведено\s+командой|"
        r"перевод\s+и\s+редактура|"
        r"переведено\s+(?:специально\s+)?для\s+(?:сайта|проекта)?|"
        r"сайт\s+перевода"
        r")",
        re.IGNORECASE
    )

    _CTA_KEYWORD_RE = re.compile(
        r"(?:"
        r"не\s*забудьте\s+(?:вступить|подписаться)|"
        r"вступайте\s+в|"
        r"подписывайтесь\s+на|"
        r"присоединяйтесь\s+к|"
        r"ж[дд]ем\s+(?:вас\s+)?в\s+(?:нашем|нашей)?"
        r")",
        re.IGNORECASE
    )

    _SOCIAL_REF_RE = re.compile(
        r"(?:"
        r"наш\s+(?:тг|телеграм|telegram|канал|паблик|дискорд|discord|вк|vk)|"
        r"групп[аеуы]\s+(?:вк|вконтакте)|"
        r"паблик[еауы]?\s+(?:вк|вконтакте)|"
        r"телеграм-канал[еауы]?|"
        r"тг-канал[еауы]?"
        r")",
        re.IGNORECASE
    )

    _DONATION_KEYWORD_RE = re.compile(
        r"(?:"
        r"поддержать\s+(?:перевод|переводчик[а-я]*|команду|выход\s+глав)|"
        r"платные\s+главы|"
        r"ранний\s+доступ\s+(?:к\s+главам)?|"
        r"главы\s+на\s+бусти|"
        r"донат\s*:|"
        r"номер\s+карты\s*:?|"
        r"сбер(?:банк)?\s*:?|"
        r"тинькофф\s*:?|"
        r"юмани\s*:?|"
        r"yoomoney|"
        r"boosty\.to|"
        r"patreon\.com|"
        r"donationalerts"
        r")",
        re.IGNORECASE
    )

    _STRICT_CREDIT_LINE_RE = re.compile(
        r"^\s*(?:(?:Над\s+переводом\s+работал[аио]?|Перевод(?:чик)?|Редакт(?:ор|ура)|Вычитка|Бета|Тайп(?:ер)?|Клинер|Анлейт|Сверил)\s*:\s*[\w\d_\s.,&/@:()-]{2,80})$",
        re.IGNORECASE
    )

    _STANDALONE_LINK_RE = re.compile(
        r"^\s*(?:https?://\S+|t\.me/\S+|vk\.com/\S+|boosty\.to/\S+|discord\.gg/\S+|@[A-Za-z0-9_]{3,})\s*$",
        re.IGNORECASE
    )

    _SITE_WATERMARK_RE = re.compile(
        r"^\s*(?:"
        r"(?:источник|взято\s+с|читать\s+на)\s*:\s*(?:https?://)?(?:ranobelib|rulate|ранобелиб|ranobehub)\S*|"
        r"переведено\s+(?:специально\s+)?для\s+(?:ranobelib|rulate|ранобелиб|ranobehub)\S*|"
        r"(?:ranobelib\.me|rulate\.ru|ranobehub\.org|tl\.rulate\.ru)"
        r")\s*$",
        re.IGNORECASE
    )

    _DIALOGUE_START_RE = re.compile(r"^\s*(?:[—–-]\s|«|“|\")")

    def is_ad_line(self, line: str) -> tuple[bool, str]:
        text = line.strip()
        if not text:
            return False, ""

        if len(text) > 400 and not self._URL_RE.search(text):
            return False, ""

        is_dialogue = bool(self._DIALOGUE_START_RE.match(text))
        has_explicit_url = bool(self._URL_RE.search(text))
        has_tg_handle = bool(self._TG_HANDLE_RE.search(text))
        has_social_ref = bool(self._SOCIAL_REF_RE.search(text))
        has_credit_kw = bool(self._CREDIT_KEYWORD_RE.search(text))
        has_cta_kw = bool(self._CTA_KEYWORD_RE.search(text))
        has_donation_kw = bool(self._DONATION_KEYWORD_RE.search(text))

        # Dialogue guard: Dialogue is protected unless it contains an explicit URL or clear social handle/ref
        if is_dialogue and not has_explicit_url and not (has_tg_handle and has_social_ref):
            return False, ""

        if self._SITE_WATERMARK_RE.match(text):
            return True, "Водяной знак сайта"
        if self._STANDALONE_LINK_RE.match(text):
            return True, "Ссылка или никнейм"
        if self._STRICT_CREDIT_LINE_RE.match(text):
            if ":" in text or "@" in text or "работа" in text.lower():
                return True, "Титры команды перевода"

        if has_donation_kw and (has_explicit_url or has_tg_handle or "донат" in text.lower() or "номер карты" in text.lower() or "бусти" in text.lower()):
            return True, "Донат / платные главы"
        if has_credit_kw and (has_explicit_url or has_tg_handle or has_social_ref):
            return True, "Титры с контактами"
        if has_cta_kw and (has_explicit_url or has_tg_handle or has_social_ref):
            return True, "Призыв подписаться в соцсети"
        if has_social_ref and (has_tg_handle or has_explicit_url):
            return True, "Контакты команды"

        return False, ""

    def filter_chapter_html(self, html_content: str, chapter_num: str = "") -> str:
        """Filter out ad lines and translator plugs from chapter HTML."""
        if not html_content:
            return html_content

        soup = BeautifulSoup(html_content, 'lxml')
        body = soup.body if soup.body else soup

        for tag in list(body.find_all(['p', 'div', 'blockquote', 'li', 'h2', 'h3', 'h4', 'h5', 'h6'])):
            if not tag.parent:
                continue

            has_images = bool(tag.find_all('img'))
            br_tags = tag.find_all('br')

            if not br_tags and not has_images:
                text = tag.get_text(strip=True)
                is_ad, reason = self.is_ad_line(text)
                if is_ad:
                    print(f"  [УДАЛЕНА РЕКЛАМА | Гл. {chapter_num}]: \"{text}\"  (Причина: {reason})")
                    tag.decompose()
                    continue

            if br_tags:
                segments = []
                curr_nodes = []
                for child in list(tag.children):
                    if getattr(child, 'name', None) == 'br':
                        segments.append((curr_nodes, child))
                        curr_nodes = []
                    else:
                        curr_nodes.append(child)
                segments.append((curr_nodes, None))

                for seg_nodes, br_node in segments:
                    seg_has_img = any(
                        getattr(n, 'name', None) == 'img' or
                        (hasattr(n, 'find_all') and bool(n.find_all('img')))
                        for n in seg_nodes
                    )
                    if seg_has_img:
                        continue
                    seg_text = "".join(
                        n.get_text() if hasattr(n, 'get_text') else str(n)
                        for n in seg_nodes
                    ).strip()
                    if not seg_text:
                        continue
                    is_ad, reason = self.is_ad_line(seg_text)
                    if is_ad:
                        print(f"  [УДАЛЕНА РЕКЛАМА | Гл. {chapter_num}]: \"{seg_text}\"  (Причина: {reason})")
                        for n in seg_nodes:
                            n.extract()
                        if br_node:
                            br_node.extract()

                while tag.contents and getattr(tag.contents[-1], 'name', None) == 'br':
                    tag.contents[-1].extract()
                while tag.contents and getattr(tag.contents[0], 'name', None) == 'br':
                    tag.contents[0].extract()

                if not tag.get_text(strip=True) and not tag.find_all('img'):
                    tag.decompose()

        return "".join(
            str(c) for c in body.children
            if getattr(c, 'name', None) or str(c).strip()
        )


class ChapterContentParser:
    def __init__(
        self,
        url: str,
        chapter_num: str,
        chapter_name: str,
        folder_name: str,
        image_prefix: str = "",
        image_manager: ImageManager | None = None,
        filter_ads: bool = False,
    ):
        self.url = url
        self.chapter_num = chapter_num
        self.chapter_name = chapter_name
        self.headers = headers
        self.images_dict = {}
        self.folder_name = folder_name
        self.image_prefix = image_prefix  # prefix for image filenames to avoid cross-volume collisions
        self.image_manager = image_manager or ImageManager(folder_name=folder_name, book=None, headers=headers)
        self.filter_ads = filter_ads
        self.ad_filter = BadLinesFilter() if filter_ads else None

    def fetch_content(self) -> tuple[str, dict]:
        """Парсит и анализирует главу"""
        response = requests.get(self.url, headers=self.headers)
        response.raise_for_status()
        json_response = response.json()

        try:  # Проверка легаси глава или нет
            json_response['data']['content']['type']  # если выдает ошибку значит легаси
            is_legacy = False
        except TypeError:
            is_legacy = True
        print(f"\nГлава {self.chapter_num}: {self.chapter_name}")

        if is_legacy:
            content = self._parse_legacy_content(json_response['data']['content'])
        else:
            content = self._parse_modern_content(json_response['data'])

        if self.filter_ads and self.ad_filter:
            content = self.ad_filter.filter_chapter_html(content, str(self.chapter_num))

        content = f"<h1>{make_chapter_title(self.chapter_num, self.chapter_name)}</h1>\n{content}"
        return content, self.images_dict

    def _parse_legacy_content(self, content_html: str) -> str:
        """Парсит легаси главу (html контент)"""
        content_soup = BeautifulSoup(content_html, 'lxml')
        image_counter = 1
        bad_sites = ["novel.tl", "ruranobe.ru", "rulate.ru"]

        for img in content_soup.find_all('img'):
            img_url = img.get('src', '')
            if not img_url:
                continue
            if not any(x in img_url for x in bad_sites):
                img_url = "https://ranobelib.me" + img_url
            if img_url.count("ranobelib.me") > 1:
                img_url = img_url[20:]

            # Position check for banner detection
            trailing_strings = img.find_all_next(string=True)
            trailing_len = sum(len(s.strip()) for s in trailing_strings)
            is_near_end = trailing_len < 250

            leading_strings = img.find_all_previous(string=True)
            leading_len = sum(len(s.strip()) for s in leading_strings)
            is_near_start = leading_len < 50

            img_key = f"{self.image_prefix}{self.chapter_num}-{image_counter}"
            epub_img_path, folder_img_path, is_dup = self.image_manager.process_image(
                img_url=img_url,
                img_key=img_key,
                chapter_num=str(self.chapter_num),
                image_counter=image_counter,
                is_near_end=is_near_end,
                is_near_start=is_near_start,
            )
            if not is_dup:
                self.images_dict[str(image_counter)] = folder_img_path
            img['src'] = epub_img_path
            image_counter += 1

        content = str(content_soup).replace('<html>', "").replace("</html>", "").replace("<body>", "").replace("</body>", "")
        return content

    def _parse_modern_content(self, data: dict) -> str:
        """Парсит модерн главу (json контент)"""
        content = ""
        image_counter = 1
        attachments = {att['name']: f"https://ranobelib.me{att['url']}" for att in data.get('attachments', [])}
        elements = data.get('content', {}).get('content', [])
        total_elements = len(elements)

        for idx, element in enumerate(elements):
            content = self._parse_element(
                element=element,
                attachments=attachments,
                image_counter=image_counter,
                current_content=content,
                element_idx=idx,
                total_elements=total_elements,
                all_elements=elements,
            )
            if isinstance(content, tuple):
                content, image_counter = content
        return content

    def _parse_element(
        self,
        element: dict,
        attachments: dict = None,
        image_counter: int = 1,
        current_content: str = "",
        element_idx: int | None = None,
        total_elements: int | None = None,
        all_elements: list | None = None,
    ) -> str | tuple:
        """Рекурсивно парсит любой элемент"""
        element_type = element['type']

        if element_type == 'image':
            return self._process_images(
                element=element,
                attachments=attachments,
                image_counter=image_counter,
                content=current_content,
                element_idx=element_idx,
                total_elements=total_elements,
                all_elements=all_elements,
            )
        elif element_type == "paragraph":
            return current_content + self._process_paragraph(element)
        elif element_type == "heading":
            return current_content + self._process_heading(element)
        elif element_type == "bulletList":
            return current_content + self._process_bullet_list(element)
        elif element_type == "blockquote":
            return current_content + self._process_blockquote(element)
        elif element_type == "horizontalRule":
            return current_content + self._process_horizontal_rule(element)
        elif element_type == "orderedList":
            return current_content + self._process_ordered_list(element)
        elif element_type == "text":
            return current_content + self._process_text_element(element)
        else:
            print(f"Неизвестный тип элемента: {element_type}")
            return current_content

    def _save_image(self, img_url: str, img_path: str):
        """Скачивает и сохраняет картинку."""
        img_content = requests.get(img_url, headers=self.headers).content
        with open(img_path, 'wb') as f:
            f.write(img_content)

    def _process_images(
        self,
        element,
        attachments,
        image_counter,
        content,
        element_idx: int | None = None,
        total_elements: int | None = None,
        all_elements: list | None = None,
    ):
        is_near_end = False
        is_near_start = False
        if element_idx is not None and total_elements is not None and all_elements is not None:
            trailing_text = ""
            for trail_el in all_elements[element_idx + 1:]:
                trailing_text += extract_text_from_prosemirror(trail_el)
            is_near_end = (element_idx >= total_elements - 3) or (len(trailing_text.strip()) < 250)

            leading_text = ""
            for lead_el in all_elements[:element_idx]:
                leading_text += extract_text_from_prosemirror(lead_el)
            is_near_start = (element_idx <= 1) and (len(leading_text.strip()) < 50)

        for image in element['attrs']['images']:
            img_url = attachments.get(image['image'])
            if img_url:
                img_key = f"{self.image_prefix}{self.chapter_num}-{image_counter}"
                epub_img_path, folder_img_path, is_dup = self.image_manager.process_image(
                    img_url=img_url,
                    img_key=img_key,
                    chapter_num=str(self.chapter_num),
                    image_counter=image_counter,
                    is_near_end=is_near_end,
                    is_near_start=is_near_start,
                )
                content += f'<p><img src="{epub_img_path}"></img></p>\n'
                if not is_dup:
                    self.images_dict[str(image_counter)] = folder_img_path
                image_counter += 1
        return content, image_counter

    def _process_text_element(self, element):
        """Обрабатывает текстовый элемент с форматированием"""
        text = element.get('text', '')
        marks = element.get('marks', [])
        
        if any(mark['type'] == "italic" for mark in marks) and any(mark['type'] == "bold" for mark in marks):
            text = f"<b><i>{text}</i></b>"
        elif any(mark['type'] == "italic" for mark in marks):
            text = f"<i>{text}</i>"
        elif any(mark['type'] == "bold" for mark in marks):
            text = f"<b>{text}</b>"
        
        return text

    def _process_paragraph(self, element):
        """Рекурсивно обрабатывает параграф с вложенными элементами"""
        paragraph_content = "<p>"
        
        for child in element.get("content", []):
            if child['type'] == 'text':
                paragraph_content += self._process_text_element(child)
            elif child['type'] == 'hardBreak':
                paragraph_content += "<br>\n"
            else:
                paragraph_content = self._parse_element(child, None, 1, paragraph_content)
                if isinstance(paragraph_content, tuple):
                    paragraph_content = paragraph_content[0]
        
        paragraph_content += "</p>\n"
        return paragraph_content

    def _process_heading(self, element):
        """Рекурсивно обрабатывает заголовок с вложенными элементами"""
        heading_level = element.get("attrs", {}).get("level", 3)
        heading_content = ""

        for child in element.get("content", []):
            if child['type'] == 'text':
                heading_content += self._process_text_element(child)
            else:
                heading_content = self._parse_element(child, None, 1, heading_content)
                if isinstance(heading_content, tuple):
                    heading_content = heading_content[0]
        
        return f"<h{heading_level}>{heading_content}</h{heading_level}>\n"

    def _process_bullet_list(self, element):
        """Рекурсивно обрабатывает маркированный список"""
        list_content = "<ul>\n"
        
        for item in element.get("content", []):
            if item['type'] == 'listItem':
                list_content += "<li>"
                for child in item.get("content", []):
                    if child['type'] == 'paragraph':
                        list_content += self._process_paragraph(child).replace('<p>', '').replace('</p>', '')
                    elif child['type'] == 'bulletList':
                        list_content += self._process_bullet_list(child)
                    elif child['type'] == 'orderedList':
                        list_content += self._process_ordered_list(child)
                    else:
                        list_content = self._parse_element(child, None, 1, list_content)
                        if isinstance(list_content, tuple):
                            list_content = list_content[0]
                
                list_content += "</li>\n"
        
        list_content += "</ul>\n"
        return list_content

    def _process_ordered_list(self, element):
        """Рекурсивно обрабатывает нумерованный список"""
        list_content = "<ol>\n"
        
        for item in element.get("content", []):
            if item['type'] == 'listItem':
                list_content += "<li>"
                
                for child in item.get("content", []):
                    if child['type'] == 'paragraph':
                        list_content += self._process_paragraph(child).replace('<p>', '').replace('</p>', '')
                    elif child['type'] == 'bulletList':
                        list_content += self._process_bullet_list(child)
                    elif child['type'] == 'orderedList':
                        list_content += self._process_ordered_list(child)
                    else:
                        list_content = self._parse_element(child, None, 1, list_content)
                        if isinstance(list_content, tuple):
                            list_content = list_content[0]
                
                list_content += "</li>\n"
        
        list_content += "</ol>\n"
        return list_content

    def _process_blockquote(self, element):
        """Рекурсивно обрабатывает цитату с вложенными элементами"""
        quote_content = "<blockquote>"
        
        for child in element.get("content", []):
            if child['type'] == 'paragraph':
                quote_content += self._process_paragraph(child)
            elif child['type'] == 'bulletList':
                quote_content += self._process_bullet_list(child)
            elif child['type'] == 'orderedList':
                quote_content += self._process_ordered_list(child)
            else:
                quote_content = self._parse_element(child, None, 1, quote_content)
                if isinstance(quote_content, tuple):
                    quote_content = quote_content[0]
        
        quote_content += "</blockquote>\n"
        return quote_content

    def _process_horizontal_rule(self, element):
        return "<hr />"




###############################################################################
#  Дальше пофикшенный код mkepub
###############################################################################
def mediatype(name):
    ext = name.split('.')[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'svg','webp'):
        raise ValueError('Image format "{}" is not supported.'.format(ext))
    if ext == 'jpg':
        ext = 'jpeg'
    return 'image/' + ext


def fonttype(name):
    ext = name.split('.')[-1].lower()
    mimetypes = {
        'otf': 'application/font-sfnt',
        'ttf': 'application/font-sfnt',
        'woff': 'font/woff',
        'woff2': 'font/woff2',
    }
    if ext not in mimetypes.keys():
        raise ValueError('Font format "{}" is not supported.'.format(ext))
    return mimetypes[ext]


env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
env.filters['mediatype'] = mediatype
env.filters['fonttype'] = fonttype
###############################################################################

Page = collections.namedtuple('Page', 'page_id title children')
Image = collections.namedtuple('Image', 'image_id name')


class Book:
    """EPUB book."""

    def __init__(self, title, **metadata):
        """"Create new book."""
        self.title = title
        self.metadata = metadata

        self.tempdir = tempfile.TemporaryDirectory()
        self.root = []
        self.fonts = []
        self.images = []
        self.uuid = uuid.uuid4()
        self._page_id = map('{:04}'.format, itertools.count(1))
        self._image_id = itertools.count(1)

        self.path = pathlib.Path(self.tempdir.name).resolve()
        for dirname in [
                'EPUB', 'META-INF', 'EPUB/images', 'EPUB/css', 'EPUB/covers']:
            (self.path / dirname).mkdir()

        self.set_stylesheet('')
        self._cover = None
        self._cover_hashes = {}

    ###########################################################################
    # Public Methods
    ###########################################################################

    def add_page(self, title, content, parent=None):
        """
        Add a new page.

        The page will be added as a subpage of the parent. If no parent is
        provided, the page will be added to the root of the book.
        """
        page = Page(next(self._page_id), title, [])
        self.root.append(page) if not parent else parent.children.append(page)
        self._write_page(page, content)
        return page

    def add_image(self, name, data):
        """Add image file, reusing existing manifest entry if name was already added."""
        for img in self.images:
            if img.name == name:
                return img
        img_id = f'{next(self._image_id):03}'
        img_entry = Image(img_id, name)
        self.images.append(img_entry)
        self._add_file(pathlib.Path('images') / name, data)
        return img_entry

    def add_cover_page(self, title: str, cover_data: bytes):
        """Add a full-page cover image as a regular content page.

        Unlike set_cover(), this embeds the image in EPUB/images/ and produces
        an ordinary page.xhtml that displays it full-screen. The page is added
        to the root TOC and its Page object is returned so chapters can be
        nested under it as children. Reuses existing image if identical cover_data
        was already added.
        """
        cover_hash = hashlib.sha256(cover_data).hexdigest()
        if cover_hash in self._cover_hashes:
            img_name = self._cover_hashes[cover_hash]
        else:
            ext = self._detect_image_ext(cover_data)
            img_id = f'{next(self._image_id):03}'
            img_name = f'volcover_{img_id}.{ext}'
            self._cover_hashes[cover_hash] = img_name
            self.images.append(Image(img_id, img_name))
            self._add_file(pathlib.Path('images') / img_name, cover_data)

        content = (
            f'<h1>{title}</h1>'
            f'<div style="text-align:center;">'
            f'<img src="images/{img_name}" '
            f'style="max-width:100%; max-height:90vh;" alt="{title}"/>'
            f'</div>'
        )
        return self.add_page(title=title, content=content)

    def purge_image(self, canonical_name: str) -> int:
        """Purge an image completely from all pages and manifest of the book.

        Returns the number of pages from which the image was removed.
        """
        cleaned_pages_count = 0
        epub_dir = self.path / 'EPUB'
        img_srcs = {f'images/{canonical_name}', canonical_name}

        for page_file in epub_dir.glob('page*.xhtml'):
            try:
                with open(page_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not any(src in content for src in img_srcs):
                    continue

                soup = BeautifulSoup(content, 'lxml')
                modified = False
                for img in soup.find_all('img'):
                    if img.get('src') in img_srcs:
                        parent = img.parent
                        img.decompose()
                        modified = True
                        if parent and parent.name == 'p':
                            if not parent.get_text(strip=True) and not parent.find_all('img'):
                                parent.decompose()

                if modified:
                    cleaned_html = "".join(str(c) for c in (soup.body.children if soup.body else soup.children))
                    title_tag = soup.find('title')
                    title = title_tag.get_text() if title_tag else ""
                    self._write('page.xhtml', f'EPUB/{page_file.name}', title=title, body=cleaned_html)
                    cleaned_pages_count += 1
            except Exception as e:
                print(f"Ошибка при очистке изображения из {page_file.name}: {e}")

        # Remove from self.images manifest list
        self.images = [img for img in self.images if img.name != canonical_name]

        # Delete physical image file from EPUB/images/
        img_file = epub_dir / 'images' / canonical_name
        if img_file.exists():
            try:
                img_file.unlink()
            except Exception as e:
                print(f"Ошибка удаления файла изображения {img_file}: {e}")

        return cleaned_pages_count

    def add_font(self, name, data):
        """Add font file."""
        self.fonts.append(name)
        self._add_file(pathlib.Path('fonts') / name, data)

    def set_cover(self, data):
        """Set the cover image to the given data."""
        magic_numbers = {
            b'\xFF\xD8\xFF': 'jpg',
            b'\x89PNG\r\n': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'RIFF': 'webp'
        }
        
        for magic, ext in magic_numbers.items():
            if data.startswith(magic):
                self._cover = f'cover.{ext}'
                self._add_file(pathlib.Path('covers') / self._cover, data)
                self._write('cover.xhtml', 'EPUB/cover.xhtml', cover=self._cover)
                return
                
        raise ValueError('Unsupported image format')

    def set_stylesheet(self, data):
        """Set the stylesheet to the given css data."""
        self._add_file(
            pathlib.Path('css') / 'stylesheet.css', data.encode('utf-8'))

    def save(self, filename):
        """Save book to a file."""
        if pathlib.Path(filename).exists():
            raise FileExistsError
        self._write_spine()
        self._write('container.xml', 'META-INF/container.xml')
        self._write_toc()
        with open(str(self.path / 'mimetype'), 'w') as file:
            file.write('application/epub+zip')
        with zipfile.ZipFile(filename, 'w') as archive:
            archive.write(
                str(self.path / 'mimetype'), 'mimetype',
                compress_type=zipfile.ZIP_STORED)
            for file in self.path.rglob('*.*'):
                archive.write(
                    str(file), str(file.relative_to(self.path)),
                    compress_type=zipfile.ZIP_DEFLATED)

    ###########################################################################
    # Private Methods
    ###########################################################################

    def _add_file(self, name, data):
        """Add a file."""
        filepath = self.path / 'EPUB' / name
        if not filepath.parent.exists():
            filepath.parent.mkdir()

        with open(str(filepath), 'wb') as file:
            file.write(data)

    def _detect_image_ext(self, data: bytes) -> str:
        """Detect image file extension from magic bytes. Falls back to 'jpg'."""
        magic_numbers = {
            b'\xFF\xD8\xFF': 'jpg',
            b'\x89PNG\r\n': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'RIFF': 'webp',
        }
        for magic, ext in magic_numbers.items():
            if data.startswith(magic):
                return ext
        return 'jpg'

    def _write(self, template, path, **data):
        with open(str(self.path / path), 'w', encoding="utf-8") as file:
            file.write(env.get_template(template).render(**data))

    def _write_page(self, page, content):
        """Write the contents of the page into an html file."""
        self._write(
            'page.xhtml', 'EPUB/page{}.xhtml'.format(page.page_id),
            title=page.title, body=content)

    def _write_spine(self):
        self._write(
            'package.opf', 'EPUB/package.opf',
            title=self.title,
            date=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            pages=list(self._flatten(self.root)), images=self.images,
            fonts=self.fonts, uuid=self.uuid, cover=self._cover,
            **self.metadata)

    def _write_toc(self):
        self._write(
            'toc.xhtml', 'EPUB/toc.xhtml', pages=self.root, title=self.title)
        self._write(
            'toc.ncx', 'EPUB/toc.ncx',
            pages=self.root, title=self.title, uuid=self.uuid)

    def _flatten(self, tree):
        for item in tree:
            yield item
            yield from self._flatten(item.children)
