## Misc Scripts



- aurora_version_fix_check_describe.py

```
[ec2-user@ip-172-31-8-156 scripts]$ python aurora_version_fix_check_describe.py "serverless"
検索文字列: 'serverless'
検索中...


バージョン 3070 で見つかりました: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraMySQLReleaseNotes/AuroraMySQL.Updates.3070.html
--------------------------------------------------------------------------------
行番号: 79
コンテキスト:
    operations involving AUTO_INCREMENT columns.
    Fixed an issue in Aurora Serverless v2 that can lead to a database restart while scaling up.
    General improvements:
--------------------------------------------------------------------------------

バージョン 3061 で見つかりました: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraMySQLReleaseNotes/AuroraMySQL.Updates.3061.html
--------------------------------------------------------------------------------
行番号: 49
コンテキスト:
    the InnoDB data dictionary during database recovery.
    Fixed an issue in Aurora Serverless v2 that can lead to a database restart while scaling up.
    General improvements:
--------------------------------------------------------------------------------

```
