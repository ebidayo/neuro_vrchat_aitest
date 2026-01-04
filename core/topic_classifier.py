import unicodedata

def classify_topic(title: str, summary: str) -> str:
    """ニュース/KBタイトル・要約からtopic分類（決定的・辞書ベース）"""
    TOPICS = [
        ("disaster", ["地震","津波","台風","警報","避難","噴火","災害","震度"]),
        ("tech", ["AI","OpenAI","GPU","CPU","NVIDIA","AMD","Microsoft","Google","Apple","アップデート","脆弱性","セキュリティ"]),
        ("game", ["ゲーム","Steam","PS5","Switch","任天堂","ソニー","新作","eスポーツ"]),
        ("anime", ["アニメ","声優","漫画","コミケ","ラノベ","VTuber","にじさんじ","ホロライブ"]),
        ("society", ["政治","選挙","法案","経済","円","株","事件","逮捕","裁判"]),
    ]
    def normalize(text):
        text = unicodedata.normalize("NFKC", text)
        return text
    text = normalize((title or "") + " " + (summary or ""))
    # "アニメ新作"などはanime優先
    if "アニメ" in text and "新作" in text:
        return "anime"
    for topic, keywords in TOPICS:
        for kw in keywords:
            if kw in text:
                return topic
    return "other"
