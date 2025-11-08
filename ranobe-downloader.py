import os
import time
import shutil
import requests
from utils import remove_bad_chars, get_ranobe_name_from_url, headers, style, Book,  ChapterContentParser
TIME_TO_SLEEP = 0.5  # задержка между запросами к каждой главе

ADD_FOLDER = True  # Добавлять ли папку с названием ранобе

class RanobeDownloader:
    base_url = "https://api.cdnlibs.org"

    def __init__(self, name, volume):
        self.data = None  
        self.name = name
        self.volume = volume
        self.info_dict = None
        
        
        self.chosen_branch_id = 0
        self.chosen_branch_name = None
        self.has_branches = True

        self.chapters_data = None
        self.volume_chapters_dict = {}

        self.book = None
        self.folder_name = ""

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
            'description': data.get('summary', ''),
        }
        self.data = data
        print(f"{self.info_dict['title']} от {self.info_dict['author']}")

        if ADD_FOLDER:
            self.folder_name = f"{self.info_dict['title']} Том {self.volume}/"


        # ranobe chapters
        url_to_chapters = f"{self.base_url}/api/manga/{self.name}/chapters"
        response = requests.get(url_to_chapters, headers=headers)
        self.chapters_data = response.json()['data']
        if response.status_code != 200:
            raise Exception(f"Failed to fetch chapters: {response.status_code}")
        
        for chapter in self.chapters_data:
            if chapter.get('volume') == self.volume:
                self.volume_chapters_dict[chapter['number']] =  {
                    "name": chapter['name'],
                    "available_branch_ids": [branch["branch_id"] for branch in chapter.get("branches")]
                    }
        self._select_translation_team()


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
            team_chapters = len([chapter for chapter in self.volume_chapters_dict.values() 
                                if branch_id in chapter["available_branch_ids"]])
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
        covers = {item["info"]: item["cover"]["orig"] for item in json_data["data"] if item["info"] and "orig" in item["cover"]}
        if str(self.volume) in covers:
            self.info_dict["cover_url"] = covers[str(self.volume)]

    def create_book_object(self):
        self.book = Book(title=self.info_dict["title"],
                         author=self.info_dict["author"],
                         description=self.info_dict["description"])
        with open(f'{self.folder_name}cover/cover.jpg', 'rb') as file:
            self.book.set_cover(file.read())
        self.book.set_stylesheet(style)

    def add_chapters_to_book_object(self):

        chosen_translation_chapters_dict = {
            chapter_num: chapter_info
            for chapter_num, chapter_info in self.volume_chapters_dict.items()
            if self.chosen_branch_id in chapter_info["available_branch_ids"]
        } if self.has_branches else self.volume_chapters_dict


        for chapter_num, chapter_info in chosen_translation_chapters_dict.items():

            chapter_name = chapter_info["name"] if chapter_info["name"].strip() else f"Глава {chapter_num}"
            
            url_to_chapter = (f"{self.base_url}/api/manga/{self.name}/chapter?"
                  f"{f'branch_id={self.chosen_branch_id}&' if self.has_branches else ''}"
                  f"number={chapter_num}&volume={self.volume}")
            
            parser = ChapterContentParser(url=url_to_chapter, chapter_num=chapter_num, chapter_name=chapter_name, folder_name=self.folder_name)

            chapter_content, images_dict = parser.fetch_content()
            self.book.add_page(title=f"Глава {chapter_num}. {chapter_name}", content=chapter_content)
            if images_dict:
                for image in images_dict.values():
                    with open(image, 'rb') as image_file:
                        self.book.add_image(image.split("/")[-1] , image_file.read())
            time.sleep(TIME_TO_SLEEP)  # Чтобы не получить error 429

    def save_book_to_file(self):
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
    while True:
        volume_input = input("Том: ").strip()
        if volume_input.isdigit() and int(volume_input) > 0:
            ranobe_volume = volume_input 
            break
        else:
            print("Неверный номер тома. Попробуйте снова")
        
    downloader = RanobeDownloader(name, ranobe_volume)
    downloader.fetch_ranobe_info()
    downloader.create_folders()
    downloader.fetch_cover_image()
    downloader.download_cover_image()
    downloader.create_book_object()
    downloader.add_chapters_to_book_object()
    downloader.save_book_to_file()

