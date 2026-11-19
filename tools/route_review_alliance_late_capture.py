"""Refresh Sage's factual Alliance quest index. Never download during an addon build."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


SITE = "https://www.sageguide.net"
FILE = Path(__file__).with_name("route_review_alliance_late_sage.json")
QUEST_ICONS = {"Quest Start": "accept", "Quest Do": "work", "Quest Do Part": "work", "Quest End": "turnin"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.rows = []
        self.current = None
        self.icon = ""

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "li":
            self.current = {"versions": set(), "quests": []}
            self.icon = ""
        if tag == "img" and self.current is not None:
            title = attrs.get("title")
            if title in ("Classic", "Forever"):
                self.current["versions"].add(title)
            self.icon = QUEST_ICONS.get(title, "")
        if tag != "a":
            return
        href = attrs.get("href") or ""
        if re.fullmatch(r"/\d+-\d+_[^?#/]+", href) and href not in self.paths:
            self.paths.append(href)
        parts = urlsplit(href)
        quest = re.fullmatch(r"/(?:forever|classic)/quest=(\d+)(?:/[^?#]*)?", parts.path)
        if self.current is not None and quest and parts.hostname in ("www.wowhead.com", "wowhead.com"):
            self.current["quests"].append((self.icon or "mentions", int(quest[1])))
        self.icon = ""

    def handle_endtag(self, tag):
        if tag == "li" and self.current is not None:
            if self.current["versions"] != {"Classic"}:
                self.rows.extend(self.current["quests"])
            self.current = None


def fetch(path):
    req = Request(SITE + path, headers={"User-Agent": "RutaXP route comparison/1"})
    with urlopen(req, timeout=30) as response:
        body = response.read()
    page = Page()
    page.feed(body.decode("utf8"))
    return page, sha256(body).hexdigest()


def capture(path):
    page, digest = fetch(path)
    if not page.rows:
        raise ValueError(f"No quest links found on {path}; check the source before refreshing")
    # The first occurrence of each quest per action preserves the author's
    # order. Only factual IDs, URLs and hashes are shipped, never the guide text.
    return {"url": SITE + path, "sha256": digest, **{
        kind: list(dict.fromkeys(qid for action, qid in page.rows if action == kind))
        for kind in ("accept", "work", "turnin", "mentions")}}


if __name__ == "__main__":
    links, _ = fetch("/")
    with ThreadPoolExecutor(max_workers=4) as workers:
        pages = list(workers.map(capture, links.paths))
    data = {"source": SITE, "checkedUTC": datetime.now(timezone.utc).date().isoformat(), "pages": pages}
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8", newline="\n")
