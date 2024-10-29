import requests
import time
import os
from bs4 import BeautifulSoup
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'
}


def get_ranobe_name_from_url(url:str) -> str:
    if "https://" in url:
        url = url.split("//")[1].split("/")[3].split("?")[0]
    else:
        url = url.split("/")[3].split("?")[0]
    return url
def get_ranobe_info(url:str) -> dict:
    """Парсит cover_url, author, title, description"""
    response = requests.get(url, headers=headers)
    if response.status_code not in [200, 204]:
        print(f"Ответ {response.status_code}: {url}")
        time.sleep(5)
        get_ranobe_info(url)
    data = response.json()['data']
    ranobe_info_dict = dict()
    ranobe_info_dict['cover_url'] = data['cover']['default']
    ranobe_info_dict['author'] = data['authors'][0]['rus_name'] if data['authors'][0]['rus_name'] is not None else data['authors'][0]['name']
    try:
        ranobe_info_dict['title'] = data['rus_name']
    except:
        ranobe_info_dict['title'] = data['name']
    try:
        ranobe_info_dict['description'] = data['summary']
    except Exception as e:
        ranobe_info_dict['description'] = ""
    return ranobe_info_dict


def get_volume_chapters(url:str, volume:str) -> dict:
    """Парсит номер и название глав"""
    response = requests.get(url, headers=headers)
    data = response.json()['data']
    chapters_dict = {}
    for chapter in data:
        if chapter['volume'] == volume:
            chapter_num = chapter['number']
            chapter_name = chapter['name'] if chapter['name'].strip() != "" else f"Глава {chapters_dict}"
            chapters_dict[chapter_num] = chapter_name
    return chapters_dict

def download_cover(url:str) -> None:
    cover_data = requests.get(url, headers=headers).content
    with open('cover/cover.jpg', 'wb') as handler:
        handler.write(cover_data)

def remove_bad_chars(text:str) -> str:
    bad_chars = '"?<>|\/:–'
    for c in bad_chars:
        text = text.replace(c, '')
    return text


def get_chapter_content(url:str, chapter_num:str, chapter_name:str) -> tuple[str, dict]:
    response = requests.get(url, headers=headers)
    json_response = response.json()
    try:
        json_response['data']['content']['type'] == "doc" # если ошибка значит легаси
        is_legacy = False
        print(f"\nГлава {chapter_num}: {chapter_name}: {url}  \nТип главы: не легаси")
    except TypeError:
        is_legacy = True
        print(f"\nГлава {chapter_num}: {chapter_name}: {url}  \nТип главы: легаси")
    os.makedirs("images", exist_ok=True)
    images_dict = {}
    image_counter = 1
    if is_legacy:
        content_soup = BeautifulSoup(json_response['data']['content'], 'lxml')
        bad_sites = ["novel.tl", "ruranobe.ru", "rulate.ru"]

        for img in content_soup.find_all('img'):
            img_url = img['src']
            if not any(x in img_url for x in bad_sites):
                img_url = "https://ranobelib.me" + img_url
            if img_url.count("ranobelib.me") > 1:
                img_url = img_url[20:]
            print(f"Арт {chapter_num}-{image_counter}: " + img_url)
            with open(f'images/{chapter_num}-{image_counter}.jpg', 'wb') as f:
                f.write(requests.get(img_url, headers=headers).content)
            del img['loading']
            img['src'] = f'images/{chapter_num}-{image_counter}.jpg'
            images_dict[str(image_counter)] = img['src']
            image_counter += 1
        for p in content_soup.find_all('p'):
            del p['data-paragraph-index']
        content = ((f"<h1>Глава {str(chapter_num)}. {str(chapter_name)}</h1>" + str(content_soup))
                   .replace('<html>', "")
                   .replace("</html>", "")
                   .replace("<body>", "")
                   .replace("</body>", ""))


    else:  # не легаси
        attachments = json_response['data']['attachments']
        chapter_content = json_response['data']['content']['content']
        content = f"<h1>Глава {chapter_num}. {chapter_name}</h1>\n"
        for element in chapter_content:
            if element['type'] == 'image':
                images = element['attrs']['images']
                for image in images:
                    image_id = image['image']
                    for attachment in attachments:
                        if attachment['name'] == image_id:
                            img_url = ' https://ranobelib.me' + attachment['url']
                            print(f"Арт {chapter_num}-{image_counter}: " + img_url)
                            img_content = requests.get(img_url, headers=headers).content
                            with open(f'images/{chapter_num}-{image_counter}.png', 'wb') as handler:
                                handler.write(img_content)
                            content += f'<p><img src="images/{chapter_num}-{image_counter}.png"></img></p>\n'
                            images_dict[str(image_counter)] = f"images/{chapter_num}-{image_counter}.png"
                            image_counter += 1
            elif element['type'] == "paragraph":
                if "content" in element:
                    for line_of_element in element['content']:
                        if line_of_element['type'] == 'text':
                            if "marks" and "italic" in str(line_of_element):
                                content += f"<p><i>{line_of_element['text']}</i></p>\n"
                            else:
                                content += f"<p>{line_of_element['text']}</p>\n"
                        elif line_of_element['type'] == 'hardBreak':
                            content += "<br>\n"
                        else:
                            print(line_of_element['text'])
                            raise Exception(f"не текст {line_of_element['type']}, {line_of_element}")
        
                    content += f"<p></p>\n"
            elif element['type'] == "heading":
                if "content" in element:
                    for line_of_element in element['content']:
                        if line_of_element['type'] == 'text':
                            content += f"<h3>{line_of_element['text']}</h3>\n"
                        else:
                            raise Exception(f"не текст {element}, {line_of_element}")
            elif element['type'] == "horizontalRule" and "content" not in element:
                pass
            elif element['type'] == "bulletList":
                bullet_list_content = element['content']
                for element_of_list in bullet_list_content:
                    if element_of_list['type'] == 'listItem':
                        for content_of_list_item in element_of_list['content']:
                            if content_of_list_item['type'] == 'paragraph':
                                content_of_content = content_of_list_item['content'][0]
                                if content_of_content['type'] == 'text':
                                    
                                    content += f"<p><li>{content_of_content['text']}</li></p>\n"
                                else:
                                    raise Exception(element)
                            else:
                                raise Exception(element)
                    else:
                        raise Exception("not listitem?", element_of_list, "\n", element)
            else:
                raise Exception(f"Новый тип {element['type']}, {element}")
    return content, images_dict
