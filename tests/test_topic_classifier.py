from core.topic_classifier import classify_topic

def test_disaster():
    assert classify_topic("地震速報","") == "disaster"
    assert classify_topic("津波警報","") == "disaster"
def test_tech():
    assert classify_topic("AIアップデート","") == "tech"
    assert classify_topic("NVIDIA新GPU","") == "tech"
def test_game():
    assert classify_topic("新作ゲーム発表","") == "game"
    assert classify_topic("eスポーツ大会","") == "game"
def test_anime():
    assert classify_topic("アニメ新作","") == "anime"
    assert classify_topic("VTuberイベント","") == "anime"
def test_society():
    assert classify_topic("選挙速報","") == "society"
    assert classify_topic("株価急落","") == "society"
def test_other():
    assert classify_topic("珍しい動物発見","") == "other"
def test_priority():
    # disaster > tech > game > anime > society > other
    assert classify_topic("地震とAI","") == "disaster"
    assert classify_topic("AIとゲーム","") == "tech"
    assert classify_topic("ゲームとアニメ","") == "game"
    assert classify_topic("アニメと経済","") == "anime"
    assert classify_topic("経済と珍事","") == "society"
