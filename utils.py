import requests
import os
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
token = os.getenv("RANOBELIB_AUTH_TOKEN")
if token:
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



class ChapterContentParser:
    def __init__(self, url: str, chapter_num: str, chapter_name: str, folder_name: str):
        self.url = url
        self.chapter_num = chapter_num
        self.chapter_name = chapter_name
        self.headers = headers
        self.images_dict = {}
        self.folder_name = folder_name
    def fetch_content(self) -> tuple[str, dict]:
        """Парсит и анализирует главу"""
        response = requests.get(self.url, headers=self.headers)
        response.raise_for_status()
        json_response = response.json()


        try: # Проверка легаси глава или нет
            json_response['data']['content']['type']  # если выдает ошибку значит легаси
            is_legacy = False
        except TypeError:
            is_legacy = True
        print(f"\nГлава {self.chapter_num}: {self.chapter_name}")
        

        if is_legacy:
            content = self._parse_legacy_content(json_response['data']['content'])
        else:
            content = self._parse_modern_content(json_response['data'])
        

        content = f"<h1>Глава {self.chapter_num}. {self.chapter_name}</h1>\n{content}"
        return content, self.images_dict

    def _parse_legacy_content(self, content_html: str) -> str:
        """Парсит легаси главу (html контент)"""
        content_soup = BeautifulSoup(content_html, 'lxml')
        image_counter = 1
        bad_sites = ["novel.tl", "ruranobe.ru", "rulate.ru"]

        for img in content_soup.find_all('img'):
            img_url = img['src']
            if not any(x in img_url for x in bad_sites):
                img_url = "https://ranobelib.me" + img_url
            if img_url.count("ranobelib.me") > 1:
                img_url = img_url[20:]
            print(f"Загрузка арта {self.chapter_num}-{image_counter}")
            folder_img_path = f"{self.folder_name}images/{self.chapter_num}-{image_counter}.jpg"
            epub_img_path = f"images/{self.chapter_num}-{image_counter}.jpg"

            self._save_image(img_url, folder_img_path)
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
        
        for element in data['content']['content']:
            content = self._parse_element(element, attachments, image_counter, content)
            if isinstance(content, tuple):
                content, image_counter = content
        return content

    def _parse_element(self, element: dict, attachments: dict = None, image_counter: int = 1, current_content: str = "") -> str | tuple:
        """Рекурсивно парсит любой элемент"""
        element_type = element['type']
        
        if element_type == 'image':
            return self._process_images(element, attachments, image_counter, current_content)
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

    def _process_images(self, element, attachments, image_counter, content):
        for image in element['attrs']['images']:
            img_url = attachments.get(image['image'])
            if img_url:
                folder_img_path = f"{self.folder_name}images/{self.chapter_num}-{image_counter}.jpg"
                epub_img_path = "images/{self.chapter_num}-{image_counter}.jpg"
                self._save_image(img_url, folder_img_path)
                content += f'<p><img src="{epub_img_path}"></img></p>\n'
                self.images_dict[str(image_counter)] = folder_img_path
                print(f"Загрузка арта {self.chapter_num}-{image_counter}")
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
        self._image_id = map('{:03}'.format, itertools.count(1))

        self.path = pathlib.Path(self.tempdir.name).resolve()
        for dirname in [
                'EPUB', 'META-INF', 'EPUB/images', 'EPUB/css', 'EPUB/covers']:
            (self.path / dirname).mkdir()

        self.set_stylesheet('')
        self._cover = None

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
        """Add image file."""
        self.images.append(Image(next(self._image_id), name))
        self._add_file(pathlib.Path('images') / name, data)

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