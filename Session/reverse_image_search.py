import time
import logging
import time
import requests
from bs4 import BeautifulSoup
import json
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin, urlparse, parse_qs, unquote

logging.basicConfig(
    filename='error.log',
    level=logging.INFO,
    format='%(asctime)s | [%(levelname)s]: %(message)s',
    datefmt='%m-%d-%Y / %I:%M:%S %p'
)

class SearchResults:
    def __init__(self, results):
        self.results = results

    def __str__(self):
        output = ""
        for result in self.results:
            output += "---\n"
            output += f"Title: {result.get('title', 'Title not found')}\n"
            output += f"Link: {result.get('link', 'Link not found')}\n"
            if result.get('source'):
                output += f"Source: {result.get('source')}\n"
            if result.get('score') is not None:
                output += f"Score: {result.get('score')}\n"
            output += "---\n"
        return output

class GoogleReverseImageSearch:
    def __init__(self):
        self.google_base_url = "https://www.google.com/searchbyimage"
        self.yandex_base_url = "https://yandex.com/images/search"
        self.bing_base_url = "https://www.bing.com/images/search"
        self.duckduckgo_html_base = "https://duckduckgo.com/html/"
        self.headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        self.retry_count = 3
        self.retry_delay = 1
        self.similarity_threshold = 60
        self.request_timeout = 20
        self._page_image_cache = {}
        self.non_article_domains = {
            'artofit.org', 'wallpapercave.com', 'wallpapersafari.com', 'patreon.com',
            'tumblr.com', 'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
            'pinterest.com', 'youtube.com', 'tiktok.com', 'linkedin.com', 'reddit.com',
            'flickr.com', 'imdb.com', 'wallpapers.com', 'genius.com'
        }

    def response(self, query: str, image_url: str, max_results: int = 10, delay: int = 1, fallback_result: Optional[Dict] = None) -> SearchResults:
        self._validate_input(query, image_url)

        all_results = []
        all_results.extend(self._search_yandex(image_url, max_results=max_results))
        if len(all_results) < max_results:
            all_results.extend(self._search_google(query, image_url, max_results, delay))
        if len(all_results) < max_results:
            all_results.extend(self._search_bing(image_url, max_results=max_results))

        all_results = self._dedupe_results(all_results)

        source_url = ''
        if fallback_result:
            source_url = fallback_result.get('source_url', '')

        if source_url:
            all_results = self._prioritize_external_domains(
                all_results,
                source_url=source_url,
            )

        # Attach approximate perceptual similarity scores where candidate image URLs can be resolved.
        all_results = self._attach_similarity_scores(image_url, all_results)

        # Only count results that are either visibly similar images or article-like fallback hits.
        all_results = self._filter_countable_results(all_results, source_url=source_url)

        if source_url:
            external_article_count = self._count_external_article_results(all_results, source_url)
        else:
            external_article_count = 0

        if (len(all_results) == 0 or external_article_count == 0) and fallback_result:
            related = self._search_related_articles(
                image_url=image_url,
                source_title=fallback_result.get('title', ''),
                source_url=fallback_result.get('source_url', ''),
                max_results=max_results,
            )
            all_results.extend(related)
            all_results = self._dedupe_results(all_results)
            if source_url:
                all_results = self._prioritize_external_domains(all_results, source_url=source_url)

        if len(all_results) == 0:
            if fallback_result:
                fallback_link = fallback_result.get('source_url') or fallback_result.get('link')
                fallback_title = fallback_result.get('title') or 'Fallback source match'
                if fallback_link:
                    logging.warning("Reverse-image providers returned no structured hits; using fallback source metadata.")
                    return SearchResults([
                        {
                            'link': fallback_link,
                            'title': fallback_title,
                            'source': 'manifest-fallback',
                            'match_type': 'source_fallback',
                        }
                    ])

            logging.warning(f"No results were found for the given query: [{query}], and/or image URL: [{image_url}].")
            return "No results found. Please try again with a different query and/or image URL."

        return SearchResults(all_results[:max_results])

    def _search_google(self, query: str, image_url: str, max_results: int, delay: int) -> List[Dict]:
        encoded_query = quote(query)
        encoded_image_url = quote(image_url)

        url = f"{self.google_base_url}?q={encoded_query}&image_url={encoded_image_url}&sbisrc=cr_1_5_2"
        all_results = []
        start_index = 0

        while len(all_results) < max_results:
            if start_index != 0:
                time.sleep(delay)

            paginated_url = f"{url}&start={start_index}"

            response = self._make_request(paginated_url)
            if response is None:
                break

            search_results, valid_content = self._parse_search_results(response.text)
            if not valid_content:
                logging.warning("Unexpected HTML structure encountered.")
                break

            for result in search_results:
                if len(all_results) >= max_results:
                    break
                data = self._extract_result_data(result, source='google')
                if data and data not in all_results:
                    all_results.append(data)

            start_index += (len(all_results) - start_index)

        return all_results

    def _search_yandex(self, image_url: str, max_results: int) -> List[Dict]:
        url = f"{self.yandex_base_url}?rpt=imageview&url={quote(image_url)}"
        response = self._make_request(url)
        if response is None:
            return []

        return self._parse_yandex_results(response.text, max_results=max_results)

    def _search_bing(self, image_url: str, max_results: int) -> List[Dict]:
        params = {
            'view': 'detailv2',
            'iss': 'sbi',
            'q': f'imgurl:{image_url}',
        }
        url = f"{self.bing_base_url}?q={quote(params['q'])}&view={params['view']}&iss={params['iss']}"
        response = self._make_request(url)
        if response is None:
            return []

        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for item in soup.select('a.iusc'):
                meta = item.get('m')
                if not meta:
                    continue

                try:
                    payload = json.loads(meta)
                except Exception:
                    continue

                link = payload.get('purl') or payload.get('ru') or payload.get('murl')
                title = payload.get('t') or payload.get('pt') or item.get('aria-label') or 'Bing visual match'
                if link:
                    results.append({
                        'link': link,
                        'title': title,
                        'source': 'bing',
                        'match_type': 'reverse_image',
                        'image_url': payload.get('murl') or payload.get('turl') or '',
                    })

                if len(results) >= max_results:
                    break

            return results
        except Exception as exc:
            logging.error(f"Error parsing Bing HTML content: {exc}")
            return []

    def _search_related_articles(self, image_url: str, source_title: str, source_url: str, max_results: int) -> List[Dict]:
        # Fallback that broadens to likely syndicated coverage when providers fail to return structured reverse-image results.
        queries = []
        if source_title:
            queries.append(f'"{source_title}"')
            short_title = ' '.join(source_title.split()[:8])
            if short_title and short_title != source_title:
                queries.append(short_title)

        image_basename = urlparse(image_url).path.split('/')[-1]
        if image_basename:
            queries.append(f'"{image_basename}"')

        if source_url:
            source_domain = urlparse(source_url).netloc.replace('www.', '')
            if source_domain and source_title:
                queries.append(f'"{source_title}" -site:{source_domain}')

        all_results = []
        for q in queries:
            for result in self._duckduckgo_search(q, max_results=max_results):
                result['source'] = 'duckduckgo-related'
                result['match_type'] = 'related_story_fallback'
                all_results.append(result)
            if len(all_results) >= max_results:
                break

        if source_url:
            all_results = self._prioritize_external_domains(all_results, source_url=source_url)

        return all_results[:max_results]

    def _duckduckgo_search(self, query: str, max_results: int = 10) -> List[Dict]:
        url = f"{self.duckduckgo_html_base}?q={quote(query)}"
        response = self._make_request(url)
        if response is None:
            return []

        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for node in soup.select('a.result__a'):
                href = node.get('href')
                title = node.get_text(' ', strip=True)
                if not href or not title:
                    continue
                href = self._unwrap_duckduckgo_redirect(href)
                results.append({'link': href, 'title': title})
                if len(results) >= max_results:
                    break

            return results
        except Exception as exc:
            logging.error(f"Error parsing DuckDuckGo HTML content: {exc}")
            return []

    def _unwrap_duckduckgo_redirect(self, href: str) -> str:
        try:
            parsed = urlparse(href)
            if 'duckduckgo.com' in parsed.netloc and parsed.path.startswith('/l/'):
                qs = parse_qs(parsed.query)
                uddg = qs.get('uddg', [])
                if uddg:
                    return unquote(uddg[0])
        except Exception:
            return href
        return href

    def _dedupe_results(self, results: List[Dict]) -> List[Dict]:
        seen = set()
        deduped = []
        for row in results:
            link = row.get('link', '').strip()
            title = row.get('title', '').strip()
            if not link:
                continue
            key = (link, title)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def _prioritize_external_domains(self, results: List[Dict], source_url: str) -> List[Dict]:
        source_domain = urlparse(source_url).netloc.lower().replace('www.', '')
        if not source_domain:
            return results

        external = []
        same_domain = []
        for row in results:
            link = row.get('link', '')
            domain = urlparse(link).netloc.lower().replace('www.', '')
            if domain and domain != source_domain:
                external.append(row)
            else:
                same_domain.append(row)

        return external + same_domain

    def _count_external_article_results(self, results: List[Dict], source_url: str) -> int:
        source_domain = urlparse(source_url).netloc.lower().replace('www.', '')
        count = 0
        for row in results:
            link = row.get('link', '')
            domain = urlparse(link).netloc.lower().replace('www.', '')
            if not domain or domain == source_domain:
                continue
            if domain in self.non_article_domains:
                continue
            if row.get('match_type') == 'related_story_fallback' or self._is_similar_image_match(row):
                count += 1
        return count

    def _filter_countable_results(self, results: List[Dict], source_url: str) -> List[Dict]:
        if not results:
            return results

        filtered = []
        for row in results:
            if self._is_similar_image_match(row):
                filtered.append(row)
                continue

            if row.get('match_type') == 'related_story_fallback' and self._is_external_article_result(row, source_url):
                filtered.append(row)

        return filtered

    def _is_similar_image_match(self, row: Dict) -> bool:
        score = row.get('score')
        return isinstance(score, (int, float)) and score >= self.similarity_threshold

    def _is_external_article_result(self, row: Dict, source_url: str) -> bool:
        link = row.get('link', '')
        if not link or not source_url:
            return False

        source_domain = urlparse(source_url).netloc.lower().replace('www.', '')
        domain = urlparse(link).netloc.lower().replace('www.', '')
        return bool(domain and domain != source_domain and domain not in self.non_article_domains)

    def _attach_similarity_scores(self, query_image_url: str, results: List[Dict]) -> List[Dict]:
        if not results:
            return results

        query_hash = self._compute_image_hash_from_url(query_image_url)
        if query_hash is None:
            return results

        for row in results:
            row['score'] = None
            candidate_img = row.get('image_url') or self._extract_candidate_image_url(row.get('link', ''))
            if candidate_img:
                row['image_url'] = candidate_img

            candidate_hash = self._compute_image_hash_from_url(candidate_img) if candidate_img else None
            if candidate_hash is None:
                continue

            row['score'] = self._hash_similarity_score(query_hash, candidate_hash)

        return results

    def _extract_candidate_image_url(self, page_url: str) -> str:
        if not page_url:
            return ''

        if page_url in self._page_image_cache:
            return self._page_image_cache[page_url]

        try:
            resp = requests.get(page_url, headers=self.headers, timeout=self.request_timeout)
            resp.raise_for_status()
            if not resp.headers.get('Content-Type', '').startswith('text/html'):
                self._page_image_cache[page_url] = ''
                return ''

            soup = BeautifulSoup(resp.text, 'html.parser')
            candidates = []

            og = soup.find('meta', attrs={'property': 'og:image'})
            if og and og.get('content'):
                candidates.append(og.get('content'))

            tw = soup.find('meta', attrs={'name': 'twitter:image'})
            if tw and tw.get('content'):
                candidates.append(tw.get('content'))

            for img in soup.select('img[src]')[:5]:
                candidates.append(img.get('src'))

            for c in candidates:
                if not c:
                    continue
                resolved = urljoin(page_url, c)
                self._page_image_cache[page_url] = resolved
                return resolved

            self._page_image_cache[page_url] = ''
            return ''
        except Exception:
            self._page_image_cache[page_url] = ''
            return ''

    def _compute_image_hash_from_url(self, image_url: str):
        if not image_url:
            return None

        try:
            from PIL import Image
        except Exception:
            return None

        try:
            resp = requests.get(image_url, headers=self.headers, timeout=self.request_timeout)
            resp.raise_for_status()
            resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', getattr(Image, 'LANCZOS', 1))
            img = Image.open(BytesIO(resp.content)).convert('L').resize((8, 8), resample)
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = ''.join('1' if p >= avg else '0' for p in pixels)
            return bits
        except Exception:
            return None

    def _hash_similarity_score(self, hash_a: str, hash_b: str) -> int:
        if not hash_a or not hash_b or len(hash_a) != len(hash_b):
            return 0
        distance = sum(1 for a, b in zip(hash_a, hash_b) if a != b)
        similarity = 1.0 - (distance / len(hash_a))
        return int(round(similarity * 100))
    
    def _validate_input(self, query: str, image_url: str):
        if not query:
            raise ValueError("Query not found. Please enter a query and try again.")
        if not image_url:
            raise ValueError("Image URL not found. Please enter an image URL and try again.")
        if not self._validate_image_url(image_url):
            raise ValueError("Invalid image URL. Please enter a valid image URL and try again.")
    
    def _validate_image_url(self, url: str) -> bool:
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        valid_extensions = (".jpg", ".jpeg", ".png", ".webp")
        return any(path.endswith(ext) for ext in valid_extensions)
    
    def _make_request(self, url: str):
        attempts = 0
        while attempts < self.retry_count:
            try:
                response = requests.get(url, headers=self.headers)
                if response.headers.get('Content-Type', '').startswith('text/html'):
                    response.raise_for_status()
                    return response
                else:
                    logging.warning("Non-HTML content received.")
                    return None
            except requests.exceptions.HTTPError as http_err:
                logging.error(f"HTTP error occurred: {http_err}")
                attempts += 1
                time.sleep(self.retry_delay)
            except Exception as err:
                logging.error(f"An error occurred: {err}")
                return None
        return None

    def _parse_search_results(self, html_content: str) -> (Optional[list], bool):
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            return soup.find_all('div', class_='g'), True
        except Exception as e:
            logging.error(f"Error parsing HTML content: {e}")
            return None, False

    def _parse_yandex_results(self, html_content: str, max_results: int) -> List[Dict]:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            all_results = []

            for item in soup.select('a.serp-item__link'):
                data = self._extract_result_data(item, source='yandex')
                if data and data not in all_results:
                    data['link'] = urljoin('https://yandex.com', item.get('href', ''))
                    data['title'] = item.get('title') or item.get_text(' ', strip=True)
                    all_results.append(data)

                if len(all_results) >= max_results:
                    break

            return all_results
        except Exception as e:
            logging.error(f"Error parsing Yandex HTML content: {e}")
            return []

    def _extract_result_data(self, result, source: str = 'google') -> Dict:
        if source == 'yandex':
            link = result.get('href')
            title = result.get('title') or result.get_text(strip=True)
            return {"link": link, "title": title, "source": source, "match_type": "reverse_image"} if link and title else {}

        link = result.find('a', href=True)['href'] if result.find('a', href=True) else None
        title = result.find('h3').get_text(strip=True) if result.find('h3') else None
        return {"link": link, "title": title, "source": source, "match_type": "reverse_image"} if link and title else {}
