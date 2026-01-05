Misora_ai 取扱説明書（確定版）

VOICEVOX + UA-4FX ループバック構成 / 自己音声抑制対応

1. 概要

Misora_ai は、VOICEVOX を用いた TTS 音声を
指定したオーディオ出力デバイス（例：UA-4FX）に再生し、
オーディオインターフェースの ループバック機能 により
その音声を マイク入力として Discord / ゲームへ送出できます。

TTS 再生中は STT入力を一時抑制できるため、
自己会話ループや暴走を防いだ安定運用が可能です。

2. 前提環境

OS: Windows

Python: 3.11

VOICEVOX Engine（ローカル起動）

Roland UA-4FX（ループバック対応）

Discord / ゲーム（マイク入力を指定可能なもの）

推奨：サブ垢でモニター（聞くだけ）

3. 音声構成（確定）
Misora TTS
   ↓
UA-4FX OUT  ──→（あなたの耳 or サブ垢でモニター）
   ↓ ループバック
UA-4FX IN
   ↓
Discord / Game マイク入力


Misora は 自分の声を聞かない

あなたは サブ垢で安全にモニター

自己会話ループなし

4. セットアップ手順
4.1 VOICEVOX Engine 起動

VOICEVOX を起動し、以下が有効であることを確認：

http://127.0.0.1:50021

4.2 UA-4FX 設定

UA-4FX ドライバ設定で ループバック ON

Windows 録音デバイスで UA-4FX IN のレベルが動くことを確認

4.3 Discord / ゲーム設定

マイク入力：UA-4FX IN

出力：任意（サブ垢で聞く場合はそちら）

5. Misora_ai 設定（確定）
推奨 config.json
{
  "speech": {
    "enabled": true,
    "provider": "voicevox",
    "sink": "device",
    "voicevox": {
      "base_url": "http://127.0.0.1:50021",
      "speaker_id": 1,
      "timeout_sec": 2.5
    },
    "device_sink": {
      "name_contains": "UA-4FX"
    },
    "self_suppress": {
      "enabled": true,
      "tail_ms": 250
    }
  }
}

重要

speech.enabled = false が デフォルト

有効化しない限り 挙動は一切変わらない

6. 動作確認チェック

 Misoraが喋ると UA-4FX OUT から音が出る

 Discordの入力メーターが反応する

 TTS中に Misora が自分に反応しない

7. よくあるトラブル
音が出ない

speech.enabled が false

name_contains がデバイス名と一致していない

VOICEVOX Engine 未起動

Discordに声が届かない

マイク入力が UA-4FX IN になっていない

ループバックが OFF

自己会話する

self_suppress.enabled を確認

自分のマイク音が出力ミックスに入っていないか確認

8. 推奨運用

メイン垢：Misora発話用

サブ垢：聞くだけ（自分のマイクOFF）

これが最も安定します