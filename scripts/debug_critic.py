from core.agents.mock_llm import call_llm
from pprint import pprint

draft = {
 'intent': 'answer',
 'content': [
  {'type': 'say', 'text': '要点Aについて詳しく説明します。長いテキストが続きます。'},
  {'type': 'say', 'text': '要点Aについて詳しく説明します。長いテキストが続きます。'},
  {'type': 'say', 'text': '要点Bはこうです。'},
  {'type': 'say', 'text': 'つまり、追加の説明をします。'},
  {'type': 'say', 'text': '最後に確認ですか？'},
  {'type': 'say', 'text': '他にも確認しますか？'},
 ]
}
payload = {
 'role': 'critic',
 'state': 'TALK',
 'user_text': '長い内容',
 'draft': draft,
 'context': {'scalars': {'confidence': 0.3, 'glitch': 0.7, 'social_pressure': 0.8}},
 'rules': {'must_include_disclaimer_if_low_conf': True, 'no_long_monologue': True, 'neuro_style': True},
 'limits': {'target_chunks': [1, 2], 'max_chars_per_chunk': 20},
}
res = call_llm(payload)
print('edited content:')
for it in res.get('edited', {}).get('content', []):
    print('-', it)
print('\nsummary:')
print('total chars', sum(len(it.get('text','')) for it in res.get('edited', {}).get('content', [])))
print('issues:', res.get('issues'))
