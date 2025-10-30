import requests
from bs4 import BeautifulSoup
import sys
import re
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

class MySQLReleaseNotesSearcher:
    def __init__(self):
        self.base_url = "https://dev.mysql.com/doc/relnotes/mysql/8.0/en/"
        self.versions = [f"news-8-0-{i}" for i in range(44, 20, -1)]
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _search_in_version(self, version: str, search_string: str,
                          case_sensitive: bool = False, context_lines: int = 2) -> Dict:
        url = f"{self.base_url}{version}.html"
        search_text = search_string if case_sensitive else search_string.lower()

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')
            # メインコンテンツ部分のみを取得（不要なヘッダー・フッターを除外）
            main_content = soup.find('div', class_='section')
            if not main_content:
                return None

            lines = main_content.get_text().split('\n')
            matches = []

            for i, line in enumerate(lines):
                compare_line = line if case_sensitive else line.lower()
                if search_text in compare_line:
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    matches.append({
                        'line_number': i + 1,
                        'context': lines[start:end],
                        'matched_line': line.strip()
                    })

            return {'version': version, 'url': url, 'matches': matches} if matches else None

        except requests.RequestException as e:
            print(f"警告: バージョン {version} の取得中にエラーが発生しました: {e}")
            return None

    def search(self, search_string: str, case_sensitive: bool = False,
              context_lines: int = 2) -> List[Dict]:
        print(f"検索文字列: '{search_string}'")
        print("検索中...\n")

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self._search_in_version, version, search_string,
                              case_sensitive, context_lines)
                for version in self.versions
            ]

            for future in futures:
                result = future.result()
                if result:
                    results.append(result)

        self._print_results(results, search_string)
        return results

    def _print_results(self, results: List[Dict], search_string: str) -> None:
        for result in results:
            print(f"\nバージョン {result['version']} で見つかりました: {result['url']}")
            print("-" * 80)

            for match in result['matches']:
                print(f"行番号: {match['line_number']}")
                print("コンテキスト:")
                for ctx_line in match['context']:
                    ctx_line = ctx_line.strip()
                    if ctx_line:
                        if search_string in ctx_line:
                            print(f">>> {ctx_line}")
                        else:
                            print(f"    {ctx_line}")
                print("-" * 80)

        print(f"\n検索結果: {len(results)} 件見つかりました")

def main():
    searcher = MySQLReleaseNotesSearcher()
    search_string = sys.argv[1] if len(sys.argv) > 1 else input("検索したい文字列を入力してください: ")
    searcher.search(search_string)

if __name__ == "__main__":
    main()
