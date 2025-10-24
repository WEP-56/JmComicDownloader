from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Dict
import re
from urllib.parse import quote_plus

try:
    import cloudscraper
    from bs4 import BeautifulSoup
    SCRAPER_AVAILABLE = True
except Exception:
    SCRAPER_AVAILABLE = False


class SearchWorker(QThread):
    search_finished = pyqtSignal(list, str)

    def __init__(self, keyword: str, page: int = 1, proxy: str = "", timeout: int = 30):
        super().__init__()
        self.keyword = keyword or ""
        self.page = max(1, int(page) if isinstance(page, int) else 1)
        self.proxy = proxy.strip() if proxy else ""
        self.timeout = int(timeout) if timeout else 30

    def run(self):
        try:
            kw = self.keyword.strip()
            if kw.isdigit():
                self.search_finished.emit([
                    {'id': kw, 'title': f'专辑 {kw}', 'author': '-', 'tags': [], 'score': '-', 'cover': ''}
                ], "")
                return
            results = self._scrape_search(kw, self.page)
            self.search_finished.emit(results, "")
        except Exception as e:
            self.search_finished.emit([], f"搜索失败: {e}")

    def _scrape_search(self, keyword: str, page: int) -> List[Dict]:
        if not SCRAPER_AVAILABLE:
            return []

        bases = [
            "https://18comic.vip",
            "https://18comic.org",
            "https://jmcomic1.me",
            "https://jmcomic.me",
        ]

        proxies = None
        if self.proxy and (self.proxy.startswith("http://") or self.proxy.startswith("https://")):
            proxies = {"http": self.proxy, "https": self.proxy}

        scraper = cloudscraper.create_scraper()
        query = quote_plus(keyword)

        for base in bases:
            try:
                url = f"{base}/search/photos?search_query={query}&page={page}"
                resp = scraper.get(url, timeout=self.timeout, proxies=proxies)
                if resp.status_code != 200 or not resp.text:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                anchors = soup.find_all('a', href=re.compile(r"/album/\d+"))
                seen = set()
                items: List[Dict] = []
                for a in anchors:
                    href = a.get('href') or ""
                    m = re.search(r"/album/(\d+)", href)
                    if not m:
                        continue
                    album_id = m.group(1)
                    if album_id in seen:
                        continue
                    seen.add(album_id)

                    title = a.get('title') or a.get_text(strip=True) or f"专辑 {album_id}"
                    # 启发式卡片
                    card = a
                    for _ in range(3):
                        if card and not card.find('img'):
                            card = card.parent
                    img_tag = (card.find('img') if card else None) or a.find('img') or (a.parent.find('img') if a.parent else None)
                    cover_url = None
                    if img_tag:
                        cover_url = img_tag.get('data-original') or img_tag.get('src') or None
                        if cover_url:
                            if cover_url.startswith('//'):
                                cover_url = 'https:' + cover_url
                            elif cover_url.startswith('/'):
                                cover_url = base.rstrip('/') + cover_url
                    # meta
                    author = '-'
                    score = '-'
                    tags: List[str] = []
                    if card:
                        author_a = card.find('a', href=re.compile(r"/search/.*(author|artist|uploader).*"))
                        if author_a and author_a.get_text(strip=True):
                            author = author_a.get_text(strip=True)
                        for tag_el in card.find_all(['a','span'], class_=re.compile(r"(badge|tag|category)")):
                            t = tag_el.get_text(strip=True)
                            if t and len(tags) < 6:
                                tags.append(t)
                        score_el = card.find(['span','div'], class_=re.compile(r"(score|rating)"))
                        if score_el:
                            st = score_el.get_text(strip=True)
                            if st:
                                score = st

                    items.append({'id': album_id,'title': title,'author': author or '-', 'tags': tags,'score': score or '-', 'cover': cover_url or ''})
                if items:
                    return items
            except Exception:
                continue
        return []
