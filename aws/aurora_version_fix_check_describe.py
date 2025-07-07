import requests
from bs4 import BeautifulSoup
import sys
import re

def search_in_versions(search_string, case_sensitive=False, context_lines=2):
    # base_url = "https://docs.aws.amazon.com/ja_jp/AmazonRDS/latest/AuroraMySQLReleaseNotes/AuroraMySQL.Updates"
    base_url = "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraMySQLReleaseNotes/AuroraMySQL.Updates"
    versions = ["3090", "3082", "3081", "3080", "3071", "3070", "3061", "3060",
                "3052", "3051", "3050", "3044", "3043", "3042", "3041", "3040"]
    found_urls = []

    print(f"検索文字列: '{search_string}'")
    print("検索中...\n")

    search_lower = search_string.lower() if not case_sensitive else search_string

    for version in versions:
        url = f"{base_url}.{version}.html"
        try:
            response = requests.get(url)
            # エンコーディングを明示的に指定
            response.encoding = 'utf-8'

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # テキストを行ごとに分割
                lines = soup.get_text().split('\n')

                # 検索結果を格納
                matches = []
                for i, line in enumerate(lines):
                    compare_line = line.lower() if not case_sensitive else line
                    if search_lower in compare_line:
                        # 前後の行を含めてコンテキストを取得
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        context = lines[start:end]
                        matches.append({
                            'line_number': i + 1,
                            'context': context,
                            'matched_line': line.strip()
                        })

                if matches:
                    found_urls.append(url)
                    print(f"\nバージョン {version} で見つかりました: {url}")
                    print("-" * 80)

                    for match in matches:
                        print(f"行番号: {match['line_number']}")
                        print("コンテキスト:")
                        for ctx_line in match['context']:
                            ctx_line = ctx_line.strip()
                            if ctx_line:  # 空行を除外
                                if search_string in ctx_line:
                                    # 検索文字列をハイライト
                                    print(f">>> {ctx_line}")
                                else:
                                    print(f"    {ctx_line}")
                        print("-" * 80)

        except Exception as e:
            print(f"エラー (バージョン {version}): {e}")

    print(f"\n検索結果: {len(found_urls)} 件見つかりました")
    return found_urls

if __name__ == "__main__":
    # Pythonスクリプトのデフォルトエンコーディングをutf-8に設定
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if len(sys.argv) > 1:
        search_string = sys.argv[1]
    else:
        search_string = input("検索したい文字列を入力してください: ")

    found_urls = search_in_versions(search_string)
