from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import List
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests
from feedparser import FeedParserDict

logger = logging.getLogger(__name__)

BASE_RSS_URL: str = 'https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/xml'


@dataclass
class Review:
    version: str
    rating: int
    id: int
    title: str
    content: str
    date: datetime
    author_link: str
    author_name: str
    country: str
    vote_count: int | None = 0
    vote_sum: int | None = 0


@dataclass
class AppStoreReviewsReader:
    country: str
    app_id: Optional[str] = None
    timeout: Optional[float] = 2.0

    def fetch_reviews(self, after: Optional[datetime] = None, since_id: Optional[int] = None) -> List[Review]:
        feed_url = BASE_RSS_URL.format(
            country=self.country, app_id=self.app_id,
        )
        self_url: Optional[str] = None
        has_next: bool = True
        reviews: List[Review] = []
        while has_next:
            has_next = False
            feed = self.fetch_feed(feed_url, timeout=self.timeout)

            if feed.feed.links is not None:
                for link in feed.feed.links:
                    if link.get('rel', '') == 'self':
                        self_url = link.href
                    if link.get('rel', '') == 'next':
                        feed_url = link.href
                        has_next = True

                if feed_url is not None and self_url is not None:
                    parsed_next = urlparse(feed_url)
                    parsed_self = urlparse(self_url)

                    if parsed_next.path == parsed_self.path:
                        has_next = False

            if feed.entries is None or len(feed.entries) == 0:
                has_next = False

            for entry in feed.entries:
                if after is not None and after.timetuple() > entry.updated_parsed:
                    has_next = False
                    break

                if since_id is not None and since_id >= int(entry.id):
                    has_next = False
                    break

                try:
                    reviews.append(
                        Review(
                            country=self.country,
                            version=entry.im_version,
                            rating=int(entry.im_rating),
                            id=int(entry.id),
                            title=entry.title,
                            content=entry.summary,
                            date=datetime.fromtimestamp(
                                mktime(entry.updated_parsed),
                            ),
                            vote_count=int(entry.im_votecount),
                            vote_sum=int(entry.im_votesum),
                            author_name=entry.author_detail.name,
                            author_link=str(entry.author_detail.href),
                        ),
                    )
                except Exception:
                    logger.error(f'Error parsing review={entry}')

        return reviews

    @staticmethod
    def fetch_feed(feed_url: str, timeout: Optional[float] = 1.0) -> FeedParserDict:
        # On MacOS https do not work, hence using workaround
        # Refer https://github.com/uvacw/inca/issues/162
        is_https = 'https://' in feed_url[:len('https://')]
        if is_https:
            feed_content = requests.get(feed_url, timeout=timeout)
            feed = feedparser.parse(feed_content.text)
        else:
            feed = feedparser.parse(feed_url)

        return feed
