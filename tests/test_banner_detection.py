import os
import shutil
import tempfile
import json
import zipfile
import unittest
from unittest.mock import patch, MagicMock

from utils import (
    ImageManager,
    Book,
    ChapterContentParser,
    load_ad_banners_cache,
    save_ad_banners_cache,
    review_ad_banners,
    display_terminal_image,
    get_image_dimensions,
    timed_input,
    load_config,
    DEFAULT_CONFIG,
    find_config_path,
    CONFIG,
)


class TestAdBannerCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.test_dir, ".test_ad_cache.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_non_existent_cache(self):
        loaded = load_ad_banners_cache(self.cache_file)
        self.assertEqual(loaded, set())

    def test_save_and_load_cache(self):
        test_hashes = {"hash123", "hash456", "hash789"}
        save_ad_banners_cache(test_hashes, self.cache_file)
        self.assertTrue(os.path.exists(self.cache_file))

        loaded = load_ad_banners_cache(self.cache_file)
        self.assertEqual(loaded, test_hashes)

    def test_corrupted_cache_fallback(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            f.write("INVALID JSON content {{{")
        loaded = load_ad_banners_cache(self.cache_file)
        self.assertEqual(loaded, set())


class TestImageBoundaryDetection(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_name = os.path.join(self.test_dir, "test_novel") + "/"
        os.makedirs(f"{self.folder_name}images", exist_ok=True)
        self.book = Book(title="Test", author="Test")
        self.image_manager = ImageManager(folder_name=self.folder_name, book=self.book, headers={})
        # Distinct dummy png bytes for distinct images
        self.png1 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        self.png2 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        self.png3 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x03\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'

    def tearDown(self):
        try:
            self.book.tempdir.cleanup()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('requests.get')
    def test_legacy_html_boundary_detection(self, mock_get):
        responses = [
            MagicMock(status_code=200, content=self.png1),
            MagicMock(status_code=200, content=self.png2),
            MagicMock(status_code=200, content=self.png3),
        ]
        mock_get.side_effect = responses

        # Case 1: Image near start (< 50 chars before)
        parser_start = ChapterContentParser(
            url="http://fake.api/chap1",
            chapter_num="1",
            chapter_name="Start Test",
            folder_name=self.folder_name,
            image_manager=self.image_manager
        )
        html_start = '<p><img src="http://example.com/banner_start.png"></p><p>' + ('Текст главы ' * 100) + '</p>'
        parser_start._parse_legacy_content(html_start)

        # Case 2: Image near end (< 250 chars after)
        parser_end = ChapterContentParser(
            url="http://fake.api/chap2",
            chapter_num="2",
            chapter_name="End Test",
            folder_name=self.folder_name,
            image_manager=self.image_manager
        )
        html_end = '<p>' + ('Текст главы ' * 100) + '</p><p><img src="http://example.com/banner_end.png"></p>'
        parser_end._parse_legacy_content(html_end)

        # Case 3: Image in middle
        parser_mid = ChapterContentParser(
            url="http://fake.api/chap3",
            chapter_num="3",
            chapter_name="Mid Test",
            folder_name=self.folder_name,
            image_manager=self.image_manager
        )
        html_mid = '<p>' + ('Текст до арта ' * 100) + '</p><p><img src="http://example.com/art_mid.png"></p><p>' + ('Текст после арта ' * 100) + '</p>'
        parser_mid._parse_legacy_content(html_mid)

        # Find entries in hash_to_image
        h2img = self.image_manager.hash_to_image
        self.assertEqual(len(h2img), 3)

        start_hash = next(h for h, e in h2img.items() if "1-1" in e['canonical_name'])
        end_hash = next(h for h, e in h2img.items() if "2-1" in e['canonical_name'])
        mid_hash = next(h for h, e in h2img.items() if "3-1" in e['canonical_name'])

        self.assertTrue(self.image_manager.image_occurrences[start_hash][0]['is_near_start'])
        self.assertFalse(self.image_manager.image_occurrences[start_hash][0]['is_near_end'])

        self.assertFalse(self.image_manager.image_occurrences[end_hash][0]['is_near_start'])
        self.assertTrue(self.image_manager.image_occurrences[end_hash][0]['is_near_end'])

        self.assertFalse(self.image_manager.image_occurrences[mid_hash][0]['is_near_start'])
        self.assertFalse(self.image_manager.image_occurrences[mid_hash][0]['is_near_end'])

    @patch('requests.get')
    def test_prosemirror_boundary_detection(self, mock_get):
        responses = [
            MagicMock(status_code=200, content=self.png1),
            MagicMock(status_code=200, content=self.png2),
            MagicMock(status_code=200, content=self.png3),
        ]
        mock_get.side_effect = responses

        parser = ChapterContentParser(
            url="http://fake.api/chap10",
            chapter_num="10",
            chapter_name="PM Test",
            folder_name=self.folder_name,
            image_manager=self.image_manager
        )
        pm_data = {
            "attachments": [
                {"name": "pm_start.png", "url": "/pm_start.png"},
                {"name": "pm_mid.png", "url": "/pm_mid.png"},
                {"name": "pm_end.png", "url": "/pm_end.png"},
            ],
            "content": {
                "type": "doc",
                "content": [
                    {"type": "image", "attrs": {"images": [{"image": "pm_start.png"}]}},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст главы параграф 1 " * 20}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст главы параграф 2 " * 20}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст главы параграф 3 " * 20}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст главы параграф 4 " * 20}]},
                    {"type": "image", "attrs": {"images": [{"image": "pm_mid.png"}]}},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст после арта параграф 1 " * 20}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст после арта параграф 2 " * 20}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст после арта параграф 3 " * 20}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Текст после арта параграф 4 " * 20}]},
                    {"type": "image", "attrs": {"images": [{"image": "pm_end.png"}]}}
                ]
            }
        }
        parser._parse_modern_content(pm_data)

        h2img = self.image_manager.hash_to_image
        self.assertEqual(len(h2img), 3)

        start_hash = next(h for h, e in h2img.items() if "10-1" in e['canonical_name'])
        mid_hash = next(h for h, e in h2img.items() if "10-2" in e['canonical_name'])
        end_hash = next(h for h, e in h2img.items() if "10-3" in e['canonical_name'])

        self.assertTrue(self.image_manager.image_occurrences[start_hash][0]['is_near_start'])
        self.assertFalse(self.image_manager.image_occurrences[start_hash][0]['is_near_end'])

        self.assertFalse(self.image_manager.image_occurrences[mid_hash][0]['is_near_start'])
        self.assertFalse(self.image_manager.image_occurrences[mid_hash][0]['is_near_end'])

        self.assertFalse(self.image_manager.image_occurrences[end_hash][0]['is_near_start'])
        self.assertTrue(self.image_manager.image_occurrences[end_hash][0]['is_near_end'])


class TestSuspiciousBannerDetection(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_name = os.path.join(self.test_dir, "test_novel") + "/"
        os.makedirs(f"{self.folder_name}images", exist_ok=True)
        self.book = Book(title="Test", author="Test")
        self.image_manager = ImageManager(folder_name=self.folder_name, book=self.book, headers={})

    def tearDown(self):
        try:
            self.book.tempdir.cleanup()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_find_suspicious_banners(self):
        # 1. Story illustration in middle of 3 chapters
        self.image_manager.hash_to_image["hash_story"] = {
            'canonical_name': 'story.png',
            'disk_path': '/path/story.png',
            'epub_path': 'images/story.png',
            'ref_count': 3,
            'hash': 'hash_story',
        }
        self.image_manager.image_occurrences["hash_story"] = [
            {'chapter_num': '1', 'is_near_end': False, 'is_near_start': False},
            {'chapter_num': '2', 'is_near_end': False, 'is_near_start': False},
            {'chapter_num': '3', 'is_near_end': False, 'is_near_start': False},
        ]

        # 2. Suspicious banner appearing at end of 2 chapters
        self.image_manager.hash_to_image["hash_banner"] = {
            'canonical_name': 'banner.png',
            'disk_path': '/path/banner.png',
            'epub_path': 'images/banner.png',
            'ref_count': 2,
            'hash': 'hash_banner',
        }
        self.image_manager.image_occurrences["hash_banner"] = [
            {'chapter_num': '1', 'is_near_end': True, 'is_near_start': False},
            {'chapter_num': '2', 'is_near_end': True, 'is_near_start': False},
        ]

        # 3. One-off end illustration (e.g. author note art in 1 chapter only)
        self.image_manager.hash_to_image["hash_single_end"] = {
            'canonical_name': 'single.png',
            'disk_path': '/path/single.png',
            'epub_path': 'images/single.png',
            'ref_count': 1,
            'hash': 'hash_single_end',
        }
        self.image_manager.image_occurrences["hash_single_end"] = [
            {'chapter_num': '1', 'is_near_end': True, 'is_near_start': False},
        ]

        suspicious = self.image_manager.find_suspicious_banners(min_repeats=2)
        suspicious_hashes = [s['hash'] for s in suspicious]

        self.assertIn("hash_banner", suspicious_hashes)
        self.assertNotIn("hash_story", suspicious_hashes)
        self.assertNotIn("hash_single_end", suspicious_hashes)

    def test_whitelisted_and_known_banners(self):
        self.image_manager.hash_to_image["hash_ad"] = {
            'canonical_name': 'ad.png',
            'disk_path': '/path/ad.png',
            'epub_path': 'images/ad.png',
            'ref_count': 2,
            'hash': 'hash_ad',
        }
        self.image_manager.image_occurrences["hash_ad"] = [
            {'chapter_num': '1', 'is_near_end': True, 'is_near_start': False},
            {'chapter_num': '2', 'is_near_end': True, 'is_near_start': False},
        ]

        # When whitelisted:
        self.image_manager.whitelisted_hashes.add("hash_ad")
        self.assertEqual(len(self.image_manager.find_suspicious_banners()), 0)

        # When in known_banners cache:
        self.image_manager.whitelisted_hashes.clear()
        self.image_manager.known_banners.add("hash_ad")
        res = self.image_manager.find_suspicious_banners()
        self.assertEqual(len(res), 1)
        self.assertTrue(res[0]['is_known'])

    def test_ad_adjacent_image_detection(self):
        # 1. Horizontal image near ad text (should be flagged even in 1 chapter)
        self.image_manager.hash_to_image["hash_ad_horiz"] = {
            'canonical_name': 'ad_banner.png',
            'disk_path': '/path/ad_banner.png',
            'epub_path': 'images/ad_banner.png',
            'ref_count': 1,
            'hash': 'hash_ad_horiz',
            'dimensions': (600, 150),  # Horizontal: width > height
        }
        self.image_manager.image_occurrences["hash_ad_horiz"] = [
            {'chapter_num': '1', 'is_near_end': False, 'is_near_start': False, 'is_near_ad_text': True},
        ]

        # 2. Vertical illustration near ad text (e.g. story art)
        self.image_manager.hash_to_image["hash_ad_vert"] = {
            'canonical_name': 'story_vert.png',
            'disk_path': '/path/story_vert.png',
            'epub_path': 'images/story_vert.png',
            'ref_count': 1,
            'hash': 'hash_ad_vert',
            'dimensions': (400, 800),  # Vertical: height > width
        }
        self.image_manager.image_occurrences["hash_ad_vert"] = [
            {'chapter_num': '1', 'is_near_end': False, 'is_near_start': False, 'is_near_ad_text': True},
        ]

        # 3. Horizontal illustration NOT near ad text, single chapter
        self.image_manager.hash_to_image["hash_normal_horiz"] = {
            'canonical_name': 'landscape.png',
            'disk_path': '/path/landscape.png',
            'epub_path': 'images/landscape.png',
            'ref_count': 1,
            'hash': 'hash_normal_horiz',
            'dimensions': (800, 400),
        }
        self.image_manager.image_occurrences["hash_normal_horiz"] = [
            {'chapter_num': '1', 'is_near_end': False, 'is_near_start': False, 'is_near_ad_text': False},
        ]

        # 4. Tiny icon near ad text (e.g. 32x32 emoji/bullet) -> should NOT be flagged as ad banner
        self.image_manager.hash_to_image["hash_ad_tiny"] = {
            'canonical_name': 'emoji.png',
            'disk_path': '/path/emoji.png',
            'epub_path': 'images/emoji.png',
            'ref_count': 1,
            'hash': 'hash_ad_tiny',
            'dimensions': (32, 32),
        }
        self.image_manager.image_occurrences["hash_ad_tiny"] = [
            {'chapter_num': '1', 'is_near_end': False, 'is_near_start': False, 'is_near_ad_text': True},
        ]

        suspicious = self.image_manager.find_suspicious_banners(min_repeats=2)
        suspicious_hashes = [s['hash'] for s in suspicious]

        self.assertIn("hash_ad_horiz", suspicious_hashes)
        self.assertNotIn("hash_ad_vert", suspicious_hashes)
        self.assertNotIn("hash_normal_horiz", suspicious_hashes)
        self.assertNotIn("hash_ad_tiny", suspicious_hashes)


class TestBookPurgeImage(unittest.TestCase):
    def setUp(self):
        self.book = Book(title="Purge Test", author="Tester")
        self.test_dir = tempfile.mkdtemp()
        self.save_epub = os.path.join(self.test_dir, "purged_test.epub")

    def tearDown(self):
        try:
            self.book.tempdir.cleanup()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_purge_image_removes_from_html_and_epub(self):
        dummy_banner_bytes = b"BANNER_IMAGE_BYTES"
        dummy_art_bytes = b"REAL_ART_BYTES"

        self.book.add_image("banner.png", dummy_banner_bytes)
        self.book.add_image("art.png", dummy_art_bytes)

        # Chapter 1: Has story art and ad banner at end (inside dedicated <p>)
        ch1_html = (
            "<p>Начало главы 1.</p>"
            "<p><img src=\"images/art.png\"/></p>"
            "<p>Конец главы 1.</p>"
            "<p><img src=\"images/banner.png\"/></p>"
        )
        self.book.add_page(title="Глава 1", content=ch1_html)

        # Chapter 2: Has ad banner at end
        ch2_html = (
            "<p>Текст главы 2.</p>"
            "<p><img src=\"images/banner.png\"/></p>"
        )
        self.book.add_page(title="Глава 2", content=ch2_html)

        # Pre-purge checks
        image_names = [img.name for img in self.book.images]
        self.assertIn("banner.png", image_names)
        self.assertIn("art.png", image_names)
        banner_path = os.path.join(self.book.tempdir.name, "EPUB", "images", "banner.png")
        self.assertTrue(os.path.exists(banner_path))

        # Purge banner.png
        purged_count = self.book.purge_image("banner.png")
        self.assertEqual(purged_count, 2)

        # Post-purge checks
        image_names_after = [img.name for img in self.book.images]
        self.assertNotIn("banner.png", image_names_after)
        self.assertIn("art.png", image_names_after)
        self.assertFalse(os.path.exists(banner_path))

        # Verify page contents in tempdir
        epub_dir = os.path.join(self.book.tempdir.name, "EPUB")
        page_files = [f for f in os.listdir(epub_dir) if f.startswith("page") and f.endswith(".xhtml")]
        self.assertEqual(len(page_files), 2)

        for page_name in page_files:
            page_path = os.path.join(epub_dir, page_name)
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("banner.png", content)
                self.assertNotIn("<p></p>", content)
                self.assertNotIn("<p> </p>", content)

        # Check art.png is still in page0001.xhtml
        with open(os.path.join(epub_dir, "page0001.xhtml"), "r", encoding="utf-8") as f:
            self.assertIn("images/art.png", f.read())

        # Save book to file and verify resulting EPUB zip
        self.book.save(self.save_epub)
        self.assertTrue(os.path.exists(self.save_epub))

        with zipfile.ZipFile(self.save_epub, "r") as zf:
            file_names = zf.namelist()
            self.assertNotIn("EPUB/images/banner.png", file_names)
            self.assertIn("EPUB/images/art.png", file_names)

            # Check manifest in package.opf
            opf = zf.read("EPUB/package.opf").decode("utf-8")
            self.assertNotIn("banner.png", opf)
            self.assertIn("art.png", opf)


class TestReviewAdBannersInteractive(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_name = os.path.join(self.test_dir, "test_novel") + "/"
        os.makedirs(f"{self.folder_name}images", exist_ok=True)
        self.cache_file = os.path.join(self.test_dir, ".ad_cache.json")
        self.book = Book(title="Review Test", author="Tester")
        self.image_manager = ImageManager(folder_name=self.folder_name, book=self.book, headers={})
        self.image_manager.banner_cache_path = self.cache_file

        # Create dummy file on disk and add to book
        self.banner_file = os.path.join(self.folder_name, "images", "banner.png")
        with open(self.banner_file, "wb") as f:
            f.write(b"DUMMY_BANNER")
        self.book.add_image("banner.png", b"DUMMY_BANNER")
        self.book.add_page("Глава 1", "<p>Текст</p><p><img src=\"images/banner.png\"/></p>")
        self.book.add_page("Глава 2", "<p>Текст</p><p><img src=\"images/banner.png\"/></p>")

        self.image_manager.hash_to_image["hash_b"] = {
            'canonical_name': 'banner.png',
            'disk_path': self.banner_file,
            'epub_path': 'images/banner.png',
            'ref_count': 2,
            'hash': 'hash_b',
        }
        self.image_manager.image_occurrences["hash_b"] = [
            {'chapter_num': '1', 'is_near_end': True, 'is_near_start': False},
            {'chapter_num': '2', 'is_near_end': True, 'is_near_start': False},
        ]

    def tearDown(self):
        try:
            self.book.tempdir.cleanup()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('builtins.input', return_value='1')
    @patch('utils.display_terminal_image', return_value=True)
    def test_review_user_chooses_purge(self, mock_display, mock_input):
        review_ad_banners(self.image_manager, self.book, min_repeats=2)

        # Banner should be purged from book
        image_names = [img.name for img in self.book.images]
        self.assertNotIn("banner.png", image_names)
        # Local file should be removed
        self.assertFalse(os.path.exists(self.banner_file))
        # Hash should be in known_banners and saved in cache file
        self.assertIn("hash_b", self.image_manager.known_banners)
        cached = load_ad_banners_cache(self.cache_file)
    @patch('builtins.input', return_value='')
    @patch('utils.display_terminal_image', return_value=True)
    def test_review_default_enter_purges(self, mock_display, mock_input):
        review_ad_banners(self.image_manager, self.book, min_repeats=2)

        image_names = [img.name for img in self.book.images]
        self.assertNotIn("banner.png", image_names)
        self.assertFalse(os.path.exists(self.banner_file))
        self.assertIn("hash_b", self.image_manager.known_banners)
        cached = load_ad_banners_cache(self.cache_file)
        self.assertIn("hash_b", cached)

    @patch('builtins.input', return_value='2')
    @patch('utils.display_terminal_image', return_value=True)
    def test_review_user_chooses_keep(self, mock_display, mock_input):
        review_ad_banners(self.image_manager, self.book, min_repeats=2)

        # Banner should NOT be purged from book
        image_names = [img.name for img in self.book.images]
        self.assertIn("banner.png", image_names)
        self.assertTrue(os.path.exists(self.banner_file))
        # Hash should be in whitelisted_hashes
        self.assertIn("hash_b", self.image_manager.whitelisted_hashes)
        # Cache file should not contain it
        cached = load_ad_banners_cache(self.cache_file)
        self.assertNotIn("hash_b", cached)

    @patch('utils.display_terminal_image')
    def test_review_known_banner_auto_purged_without_prompt(self, mock_display):
        self.image_manager.known_banners.add("hash_b")
        review_ad_banners(self.image_manager, self.book, min_repeats=2)

        # display_terminal_image should not be called since it auto-purges known banner
        mock_display.assert_not_called()
        image_names = [img.name for img in self.book.images]
        self.assertNotIn("banner.png", image_names)
        self.assertFalse(os.path.exists(self.banner_file))


class TestTerminalImageDisplay(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sample_img = os.path.join(self.test_dir, "sample.png")
        with open(self.sample_img, "wb") as f:
            f.write(b"PNG_DATA")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_display_terminal_image_chafa_sixel(self, mock_run, mock_which):
        def fake_which(cmd):
            if cmd == "chafa":
                return "/usr/bin/chafa"
            return None
        mock_which.side_effect = fake_which
        mock_run.return_value = MagicMock(returncode=0)

        result = display_terminal_image(self.sample_img)
        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "chafa")
        self.assertIn("-f", args)
        self.assertIn("sixels", args)


class TestRanobeDownloaderBannerIntegration(unittest.TestCase):
    def test_downloader_init_and_save_banner_check(self):
        import importlib
        ranobe_module = importlib.import_module("ranobe-downloader")
        RanobeDownloader = ranobe_module.RanobeDownloader

        # 1. Flag enabled
        downloader = RanobeDownloader(name="test", volume="1", check_ad_banners=True)
        self.assertTrue(downloader.check_ad_banners)

        # Mock review_ad_banners and book.save
        downloader.review_ad_banners = MagicMock()
        downloader.book = MagicMock()
        downloader.info_dict = {"title": "Test Title"}
        downloader.folder_name = tempfile.mkdtemp() + "/"

        downloader.save_book_to_file()
        downloader.review_ad_banners.assert_called_once()

        # 2. Flag disabled
        downloader_disabled = RanobeDownloader(name="test", volume="1", check_ad_banners=False)
        self.assertFalse(downloader_disabled.check_ad_banners)
        downloader_disabled.review_ad_banners = MagicMock()
        downloader_disabled.book = MagicMock()
        downloader_disabled.info_dict = {"title": "Test Title"}
        downloader_disabled.folder_name = downloader.folder_name

        downloader_disabled.save_book_to_file()
        downloader_disabled.review_ad_banners.assert_not_called()

        shutil.rmtree(downloader.folder_name, ignore_errors=True)


class TestTimedInput(unittest.TestCase):
    @patch('select.select')
    @patch('sys.stdin')
    def test_timed_input_timeout_defaults_to_delete(self, mock_stdin, mock_select):
        mock_stdin.isatty.return_value = True
        mock_select.return_value = ([], [], [])
        result = timed_input("Prompt: ", timeout=0.01)
        self.assertEqual(result, "1")

    @patch('select.select')
    @patch('sys.stdin')
    def test_timed_input_user_enters_choice(self, mock_stdin, mock_select):
        mock_stdin.isatty.return_value = True
        mock_select.return_value = ([mock_stdin], [], [])
        mock_stdin.readline.return_value = "2\n"
        result = timed_input("Prompt: ", timeout=0.01)
        self.assertEqual(result, "2")


class TestGetImageDimensions(unittest.TestCase):
    def test_png_dimensions(self):
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x02\x80\x00\x00\x01\x90\x08\x06\x00\x00\x00'
        dims = get_image_dimensions(png_data)
        self.assertEqual(dims, (640, 400))

    def test_gif_dimensions(self):
        gif_data = b'GIF89a\x2c\x01\xc8\x00' + b'\x00' * 20
        dims = get_image_dimensions(gif_data)
        self.assertEqual(dims, (300, 200))

    def test_jpeg_dimensions(self):
        jpeg_data = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x60\x00\x60\x00\x00'
            b'\xff\xc0\x00\x11\x08\x01\x5e\x02\xbc\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01'
            b'\xff\xd9'
        )
        dims = get_image_dimensions(jpeg_data)
        self.assertEqual(dims, (700, 350))


class TestConfigSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.custom_config_path = os.path.join(self.test_dir, "test_config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_config_has_all_required_keys(self):
        required_keys = [
            "time_to_sleep", "add_folder", "filter_ads", "check_ad_banners",
            "banner_min_repeats", "review_timeout", "default_review_action",
            "banner_cache_file", "min_banner_width", "min_banner_height",
            "min_banner_area", "terminal_max_cols", "terminal_max_rows",
            "base_url", "token", "headers"
        ]
        for key in required_keys:
            self.assertIn(key, DEFAULT_CONFIG)

    def test_load_config_custom_file_merges_with_defaults(self):
        custom_data = {
            "time_to_sleep": 1.5,
            "add_folder": False,
            "review_timeout": 5.0,
            "default_review_action": "2",
            "headers": {
                "User-Agent": "CustomAgent/1.0"
            }
        }
        with open(self.custom_config_path, "w", encoding="utf-8") as f:
            json.dump(custom_data, f)

        cfg = load_config(self.custom_config_path)
        self.assertEqual(cfg["time_to_sleep"], 1.5)
        self.assertFalse(cfg["add_folder"])
        self.assertEqual(cfg["review_timeout"], 5.0)
        self.assertEqual(cfg["default_review_action"], "2")
        self.assertEqual(cfg["headers"]["User-Agent"], "CustomAgent/1.0")
        # Ensure unspecified headers from default are preserved
        self.assertIn("Accept", cfg["headers"])
        # Ensure unspecified top-level keys from default are preserved
        self.assertEqual(cfg["min_banner_width"], 200)

    def test_load_config_corrupted_json_falls_back_to_defaults(self):
        with open(self.custom_config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json...")

        cfg = load_config(self.custom_config_path)
        self.assertEqual(cfg["time_to_sleep"], 0.5)
        self.assertTrue(cfg["check_ad_banners"])

    def test_find_config_path_returns_existing(self):
        found = find_config_path("config.json")
        self.assertTrue(os.path.exists(found))


if __name__ == '__main__':
    unittest.main()
