import uuid
from uuid_extensions.uuid7 import uuid7

# UUID v4 (128 bit ; ランダム生成)
uuid_v4 = uuid.uuid4()
print(f"UUID v4: {uuid_v4}")

# UUIDのbit数を計算（128ビットに補正）
# 先頭のゼロビットはbin()関数で変換した際に省略されるため
hex_str = str(uuid_v4).replace('-', '')
bin_str = format(int(hex_str, 16), '0128b')  # 128ビットに0埋め
print(f"Bit length: {len(bin_str)} bits\n")

# UUID v7 (先頭60 bit : タイムスタンプベース)
uuid_v7 = uuid7()
print(f"UUID v7: {uuid_v7}")

# UUIDのbit数を計算（128ビットに補正）
hex_str = str(uuid_v7).replace('-', '')
bin_str = format(int(hex_str, 16), '0128b')  # 128ビットに0埋め
print(f"Bit length: {len(bin_str)} bits\n")

# 複数回生成して時系列順序を確認
print("複数のUUID v4を連続生成(128bit):")
for _ in range(3):
    print(uuid.uuid4())

# 複数回生成して時系列順序を確認
print("\n複数のUUID v7を連続生成(128bitで先頭60bitはTimestamp):")
for _ in range(3):
    print(uuid7())
