import os
import time
import shutil
import requests
from utils import (
    remove_bad_chars, get_ranobe_name_from_url, headers, style, Book,
    ChapterContentParser, make_chapter_title, extract_text_from_prosemirror,
    ImageManager, BadLinesFilter, review_ad_banners, CONFIG
)
TIME_TO_SLEEP = CONFIG.get("time_to_sleep", 0.5)  # задержка между запросами к каждой главе

ADD_FOLDER = CONFIG.get("add_folder", True)  # Добавлять ли папку с названием ранобе
FILTER_ADS = CONFIG.get("filter_ads", True)  # Удалять ли рекламу, ссылки на соцсети и водяные знаки переводчиков
CHECK_AD_BANNERS = CONFIG.get("check_ad_banners", True)  # Проверять подозрительные рекламные баннеры (повторяющиеся в конце глав)
BANNER_MIN_REPEATS = CONFIG.get("banner_min_repeats", 2)  # Минимальное количество повторений баннера для проверки

class RanobeDownloader:
    base_url = CONFIG.get("base_url", "https://api.cdnlibs.org")

    def __init__(self, name, volume=None, filter_ads=FILTER_ADS, check_ad_banners=CHECK_AD_BANNERS):
        self.data = None  
        self.name = name
        self.volume = volume          # None → whole-book mode
        self.volumes = []             # populated in fetch_ranobe_info
        self.info_dict = None
        self.filter_ads = filter_ads
        self.check_ad_banners = check_ad_banners
        
        
        self.chosen_branch_id = 0
        self.chosen_branch_name = None
        self.has_branches = True

        self.chapters_data = None
        self.volume_chapters_dict = {}  # single-vol: {num→info}; whole-book: {vol→{num→info}}

        self.book = None
        self.folder_name = ""
        self.covers_by_vol = {}   # {"1": url, "2": url, …} — populated in fetch_cover_image

    def fetch_ranobe_info(self):
        # ranobe info
        url_to_ranobe = f"{self.base_url}/api/manga/{self.name}?fields[]=background&fields[]=eng_name&fields[]=otherNames&fields[]=summary&fields[]=releaseDate&fields[]=type_id&fields[]=caution&fields[]=views&fields[]=close_view&fields[]=rate_avg&fields[]=rate&fields[]=genres&fields[]=tags&fields[]=teams&fields[]=user&fields[]=franchise&fields[]=authors&fields[]=publisher&fields[]=userRating&fields[]=moderated&fields[]=metadata&fields[]=metadata.count&fields[]=metadata.close_comments&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id&fields[]=artists&fields[]=format"
        response = requests.get(url_to_ranobe, headers=headers)
        data = response.json()['data'] 
        if response.status_code != 200:
            raise Exception(f"HTTP Error {response.status_code}: Failed to fetch {url_to_ranobe} ranobe info with response: {data}\n Maybe bearer token required?")
               
        self.info_dict = {
            'id': data.get('id'),
            'cover_url': data.get('cover', {}).get('default', ''),
            'author': data.get('authors', [{}])[0].get('rus_name') or data.get('authors', [{}])[0].get('name', 'Unknown Author'),
            'title': data.get('rus_name', data.get('name', '')),
            'description': extract_text_from_prosemirror(data.get('summary', '')),
        }
        self.data = data
        print(f"{self.info_dict['title']} от {self.info_dict['author']}")

        if ADD_FOLDER:
            if self.volume is None:
                self.folder_name = f"{self.info_dict['title']}/"
            else:
                self.folder_name = f"{self.info_dict['title']} Том {self.volume}/"


        # ranobe chapters
        url_to_chapters = f"{self.base_url}/api/manga/{self.name}/chapters"
        response = requests.get(url_to_chapters, headers=headers)
        self.chapters_data = response.json()['data']
        if response.status_code != 200:
            raise Exception(f"Failed to fetch chapters: {response.status_code}")

        if self.volume is None:
            # whole-book mode: collect every volume in API order, then sort numerically
            for chapter in self.chapters_data:
                vol = chapter.get('volume')
                if vol not in self.volumes:
                    self.volumes.append(vol)
                self.volume_chapters_dict.setdefault(vol, {})[chapter['number']] = {
                    "name": chapter['name'],
                    "available_branch_ids": [branch["branch_id"] for branch in chapter.get("branches", [])]
                }
            # Sort so Vol 1 comes first regardless of API return order
            self.volumes.sort(key=lambda v: float(str(v)))
        else:
            self.volumes = [self.volume]
            for chapter in self.chapters_data:
                if chapter.get('volume') == self.volume:
                    self.volume_chapters_dict[chapter['number']] = {
                        "name": chapter['name'],
                        "available_branch_ids": [branch["branch_id"] for branch in chapter.get("branches", [])]
                    }
        self._select_translation_team()


    def _all_chapter_infos(self):
        """Yield every chapter-info dict regardless of single-vol or whole-book dict layout."""
        if self.volume is None:
            for vol_chapters in self.volume_chapters_dict.values():
                yield from vol_chapters.values()
        else:
            yield from self.volume_chapters_dict.values()

    def _select_translation_team(self):
        teams = self.data.get("teams", [])
        
        if not teams:
            self.has_branches = False
            self.chosen_branch_id = None
            return
        
        if len(teams) == 1:
            self._setup_single_team(teams[0])
            return


        used_branch_ids = []
        teams_dict = {}

        for team in teams: 
            name = team.get("name")
            details = team.get("details", {})
            branch_id = details.get("branch_id")
            is_active = details.get("is_active", False)
            
            if branch_id not in used_branch_ids:
                if name and branch_id:
                    if is_active:
                        teams_dict[branch_id] = name
                        used_branch_ids.append(branch_id)

        # if no active teams
        for team in teams:
            name = team.get("name")
            details = team.get("details", {})
            branch_id = details.get("branch_id")
            
            if branch_id not in used_branch_ids:
                if name and branch_id:
                    teams_dict[branch_id] = name
                    used_branch_ids.append(branch_id)
        
        
        if not teams_dict:
            self._setup_default_team()
            return
        

        url_to_team_defaults = f"{self.base_url}/api/branches/{self.info_dict['id']}?team_defaults=1"
        response = requests.get(url_to_team_defaults, headers=headers)
        team_defaults_data = response.json().get("data", [])
        
        main_branch_id = next((branch['id'] for branch in team_defaults_data if branch.get('name') == "main"), None)
        main_branch_name = teams_dict.get(main_branch_id, list(teams_dict.values())[0])
        
        branch_chapter_numbers = {}
        for branch_id in teams_dict.keys():
            team_chapters = len([ch for ch in self._all_chapter_infos()
                                 if branch_id in ch["available_branch_ids"]])
            branch_chapter_numbers[branch_id] = team_chapters

                
        
        available_teams = {}
        for branch_id, team_name in teams_dict.items():
            chapter_count = branch_chapter_numbers.get(branch_id, 0)
            if chapter_count > 0:
                available_teams[branch_id] = team_name
        if main_branch_id in available_teams:
            default_branch_id = main_branch_id
            default_branch_name = main_branch_name
        else:
            default_branch_id = list(available_teams.keys())[0] if available_teams else None
            default_branch_name = available_teams.get(default_branch_id, "")

        while True:
            try:
                if len(available_teams) == 1:
                    only_branch_id = list(available_teams.keys())[0]
                    only_team_name = list(available_teams.values())[0]
                    print(f"Автоматически выбран перевод: {only_team_name}; Глав: {branch_chapter_numbers[only_branch_id]}")
                    self.chosen_branch_id = only_branch_id
                    self.chosen_branch_name = only_team_name
                    return



                print(f"Выберите перевод (По умолчанию {default_branch_name}):")
                for n, (branch_id, team_name) in enumerate(available_teams.items(), 1):
                    chapter_count = branch_chapter_numbers[branch_id]
                    print(f"{n}. {team_name}; Глав: {chapter_count}")
                
                user_input = input("Введите номер перевода: ").strip()
            
                if not user_input and default_branch_id:
                    print(f"Выбран перевод по умолчанию: {default_branch_name}")
                    self.chosen_branch_id = default_branch_id
                    self.chosen_branch_name = default_branch_name
                    return
                
                chosen_n = int(user_input) - 1
                
                if 0 <= chosen_n < len(available_teams):
                    selected_branch_id = list(available_teams.keys())[chosen_n]
                    selected_team_name = list(available_teams.values())[chosen_n]
                    
                    print(f"Выбран перевод: {selected_team_name}")
                    self.chosen_branch_id = selected_branch_id
                    self.chosen_branch_name = selected_team_name
                    return
                else:
                    print(f"Пожалуйста, введите число от 1 до {len(available_teams)}")
                    
            except ValueError:
                print("Ошибка: Введите корректное число")

    def _setup_single_team(self, team):
        self.has_branches = False
        self.chosen_branch_id = None
        self.chosen_branch_name = team.get("name", "Основной перевод")
        print(f"Автоматически выбран перевод: {self.chosen_branch_name}")

    def _setup_default_team(self):
        print("Автоматически выбран основной перевод")
        self.has_branches = False
        self.chosen_branch_id = None
    

    def download_cover_image(self):
        cover_data = requests.get(self.info_dict["cover_url"], headers=headers).content
        with open(f'{self.folder_name}cover/cover.jpg', 'wb') as handler:
            handler.write(cover_data)

    def fetch_cover_image(self):
        url_to_covers = f"{self.base_url}/api/manga/{self.name}/covers"
        json_data = requests.get(url_to_covers).json()

        # Build vol-number → orig-url mapping (items with info=null are the global default)
        self.covers_by_vol = {
            item["info"]: item["cover"]["orig"]
            for item in json_data["data"]
            if item["info"] and "orig" in item["cover"]
        }

        if self.volume is None:
            # whole-book mode: main EPUB cover = first volume's cover, or keep default
            first_vol = str(self.volumes[0]) if self.volumes else None
            if first_vol and first_vol in self.covers_by_vol:
                self.info_dict["cover_url"] = self.covers_by_vol[first_vol]
            # if no per-vol cover exists for vol 1, self.info_dict["cover_url"] stays
            # as the default cover already set in fetch_ranobe_info — no change needed
        else:
            # single-volume mode: existing behaviour
            if str(self.volume) in self.covers_by_vol:
                self.info_dict["cover_url"] = self.covers_by_vol[str(self.volume)]

    def create_book_object(self):
        title = (self.info_dict["title"] if self.volume is None
                 else f"{self.info_dict['title']} Том {self.volume}")
        self.book = Book(title=title,
                         author=self.info_dict["author"],
                         description=self.info_dict["description"])
        with open(f'{self.folder_name}cover/cover.jpg', 'rb') as file:
            self.book.set_cover(file.read())
        self.book.set_stylesheet(style)
        self.image_manager = ImageManager(
            folder_name=self.folder_name,
            book=self.book,
            headers=headers
        )

    def add_chapters_to_book_object(self):
        if self.volume is None:
            # whole-book: one cover landing page per volume, chapters nested under it
            default_cover_bytes = None  # downloaded at most once, reused as fallback

            for vol in self.volumes:
                cover_url = self.covers_by_vol.get(str(vol))

                if cover_url:
                    print(f"\nЗагрузка обложки Том {vol}...")
                    cover_bytes = requests.get(cover_url, headers=headers).content
                else:
                    # No per-volume cover → use default, downloading it only once
                    if default_cover_bytes is None:
                        print("\nОбложка для этого тома не найдена, используется обложка по умолчанию...")
                        default_cover_bytes = requests.get(
                            self.info_dict["cover_url"], headers=headers
                        ).content
                    cover_bytes = default_cover_bytes

                vol_page = self.book.add_cover_page(
                    title=f"Том {vol}",
                    cover_data=cover_bytes,
                )
                chapters_for_vol = self.volume_chapters_dict.get(vol, {})
                self._add_volume_chapters(vol, chapters_for_vol, parent=vol_page)
        else:
            # single-volume: chapters go straight to root (no parent)
            self._add_volume_chapters(self.volume, self.volume_chapters_dict, parent=None)

    def _filter_chapters_by_branch(self, chapters_dict: dict) -> dict:
        """Return only chapters available for the chosen branch (or all if no branching)."""
        if not self.has_branches:
            return chapters_dict
        return {
            num: info for num, info in chapters_dict.items()
            if self.chosen_branch_id in info["available_branch_ids"]
        }

    def _add_volume_chapters(self, volume, chapters_dict: dict, parent):
        """Fetch every chapter of one volume and add it to the book under `parent`."""
        chosen = self._filter_chapters_by_branch(chapters_dict)
        # image filenames are prefixed with volume number to avoid cross-volume collisions
        image_prefix = f"v{volume}-" if self.volume is None else ""
        for chapter_num, chapter_info in chosen.items():
            chapter_name = chapter_info["name"].strip() or f"Глава {chapter_num}"
            url_to_chapter = (
                f"{self.base_url}/api/manga/{self.name}/chapter?"
                f"{'branch_id=' + str(self.chosen_branch_id) + '&' if self.has_branches else ''}"
                f"number={chapter_num}&volume={volume}"
            )
            parser = ChapterContentParser(
                url=url_to_chapter,
                chapter_num=chapter_num,
                chapter_name=chapter_name,
                folder_name=self.folder_name,
                image_prefix=image_prefix,
                image_manager=self.image_manager,
                filter_ads=self.filter_ads,
            )
            chapter_content, images_dict = parser.fetch_content()
            self.book.add_page(
                title=make_chapter_title(chapter_num, chapter_name),
                content=chapter_content,
                parent=parent,
            )
            if images_dict:
                for image in images_dict.values():
                    with open(image, 'rb') as image_file:
                        self.book.add_image(image.split("/")[-1], image_file.read())
            time.sleep(TIME_TO_SLEEP)  # Чтобы не получить error 429


    def review_ad_banners(self):
        if not self.check_ad_banners or not hasattr(self, 'image_manager') or not self.image_manager:
            return
        review_ad_banners(self.image_manager, self.book, min_repeats=BANNER_MIN_REPEATS)

    def save_book_to_file(self):
        if self.check_ad_banners:
            self.review_ad_banners()
        if self.volume is None:
            book_name = remove_bad_chars(self.info_dict["title"]) + " (полная версия).epub"
        else:
            book_name = remove_bad_chars(self.info_dict["title"]) + f" Том {self.volume}.epub"
        book_path = f"{self.folder_name}{book_name}"
        if os.path.exists(book_path):
            print(f'\nФайл {book_name} уже существует. Перезаписываю...')
            os.remove(book_path)
        self.book.save(book_path)
        print(f'\nКнига сохранена как {book_name} в папке {self.folder_name}')

    def create_folders(self):
        shutil.rmtree(f"{self.folder_name}cover", ignore_errors=True)
        shutil.rmtree(f"{self.folder_name}images", ignore_errors=True)
        os.makedirs(f"{self.folder_name}cover", exist_ok=True)
        os.makedirs(f"{self.folder_name}images", exist_ok=True)

def parse_volumes(volume_input: str) -> list[str] | None:
    """Parse volume input into a sorted list of volume strings.

    Accepted formats:
      - Single volume:      "3"
      - Space-separated:    "1 2 3"
      - Range (inclusive):  "1-5"
      - Mixed:              "1-3 5 7"
    Returns None if the input is invalid.
    """
    volumes = []
    parts = volume_input.split()
    for part in parts:
        if '-' in part:
            bounds = part.split('-')
            if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                return None
            start, end = int(bounds[0]), int(bounds[1])
            if start > end or start < 1:
                return None
            volumes.extend(range(start, end + 1))
        elif part.isdigit():
            volumes.append(int(part))
        else:
            return None
    # deduplicate, sort, convert back to strings
    seen = set()
    result = []
    for v in volumes:
        if v not in seen:
            seen.add(v)
            result.append(str(v))
    return result or None


if __name__ == "__main__":
    while True:
        url = input("Ссылка на ранобе: ").strip()
        if not url:
            print("URL не может быть пустым. Попробуйте снова.")
            continue
        name = get_ranobe_name_from_url(url)
        if name == False:
            print("Неправильная ссылка, попробуйте снова")
            continue
        break

    print(f"\nФильтр рекламы: {'Включен' if FILTER_ADS else 'Отключен'}")
    print(f"Проверка рекламных баннеров: {'Включена' if CHECK_AD_BANNERS else 'Отключена'}")
    print("\nРежим загрузки:")
    print("  1. Один или несколько томов (отдельные файлы)")
    print("  2. Вся книга целиком (один файл, вложенное оглавление)")
    while True:
        mode_input = input("Режим (1/2, по умолчанию 1): ").strip()
        if mode_input in ("", "1", "2"):
            break
        print("Введите 1 или 2")

    if mode_input == "2":
        # ── Whole-book mode ──────────────────────────────────────────
        print("\nСкачивание всей книги в один файл...")
        downloader = RanobeDownloader(name, volume=None)
        downloader.fetch_ranobe_info()
        print(f"Найдено томов: {len(downloader.volumes)}")
        downloader.create_folders()
        downloader.fetch_cover_image()
        downloader.download_cover_image()
        downloader.create_book_object()
        downloader.add_chapters_to_book_object()
        downloader.save_book_to_file()
        print("\nГотово!")
    else:
        # ── Single / multi-volume mode ────────────────────────────────
        while True:
            print("Том (или несколько: '1 2 3' / диапазон '1-5' / смешанно '1-3 5'):")
            volume_input = input("Том: ").strip()
            volumes = parse_volumes(volume_input)
            if volumes:
                break
            else:
                print("Неверный ввод. Укажите положительные целые числа, диапазон вида '1-5' или их комбинацию.")

        total = len(volumes)
        for idx, ranobe_volume in enumerate(volumes, 1):
            print(f"\n{'='*50}")
            print(f"Скачивание тома {ranobe_volume} ({idx}/{total})")
            print(f"{'='*50}")
            downloader = RanobeDownloader(name, ranobe_volume)
            downloader.fetch_ranobe_info()
            downloader.create_folders()
            downloader.fetch_cover_image()
            downloader.download_cover_image()
            downloader.create_book_object()
            downloader.add_chapters_to_book_object()
            downloader.save_book_to_file()

        print(f"\nГотово! Скачано томов: {total}")


