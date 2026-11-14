# Расходы — расследование 2026-11-14 01:08 UTC

## OpenRouter: что говорит сам OpenRouter
```
Ключ NOVA (/key):
  label: sk-or-v1-de2...992
  usage: 6.2088015
  usage_daily: 1.17687125
  usage_weekly: 6.2088015
  usage_monthly: 6.2088015
  limit: None
  limit_remaining: None
  is_free_tier: False
Весь аккаунт (/credits):
   {'total_credits': 124, 'total_usage': 114.374617924}
Активность по дням и моделям (/activity, последние дни):
   {'error': {'message': 'Only management keys can fetch activity for an account', 'code': 403}}
```

## Kie
```
{"code":200,"msg":"success","data":852.0}
```

## Наши записи расходов (таблица costs) — по дням
```
   d   |  provider  |  usd   |  n  
-------+------------+--------+-----
 11-14 | openrouter | 0.0230 |  16
 11-13 | kie        | 0.5400 |   9
 11-13 | openrouter | 0.8027 | 108
(3 rows)

```
## За 3 дня: по видам и пометкам
```
  provider  | kind  |                   note                    |  usd   | n  
------------+-------+-------------------------------------------+--------+----
 openrouter | music | google/gemini-3.8-flash-tts               | 0.2896 | 27
 openrouter | music | web search                                | 0.2159 |  9
 openrouter | music | google/gemini-3.8-flash                   | 0.0737 | 10
 openrouter | image | openai/gpt-image-2.6-flare                | 0.0647 |  1
 openrouter | agent | google/gemini-3.8-flash                   | 0.0604 | 30
 kie        | music | kie task 71f870a5a08038a79059659bc03e0648 | 0.0600 |  1
 kie        | music | kie task 7493d96d1c7417367d5b7afd3eafb364 | 0.0600 |  1
 kie        | music | kie task bc4af3372490b5bd7ee8ba72b126cf3a | 0.0600 |  1
 kie        | music | kie task 1818375eb038d6ad73b2579ab382c129 | 0.0600 |  1
 kie        | music | kie task df29c0e4756a61d2dcb9d36840608f9c | 0.0600 |  1
 kie        | music | kie task ed8acdfd6bd5232ea107024c0949d016 | 0.0600 |  1
 kie        | music | kie task ab3799fa7aeb44d6646a67f109aad015 | 0.0600 |  1
 kie        | music | kie task fb17b7a5de33930e790f78c314844268 | 0.0600 |  1
 kie        | music | kie task 7be65f729bb6e5ce0082189dbd220ea9 | 0.0600 |  1
 openrouter | tts   | google/gemini-3.8-flash-tts               | 0.0499 |  7
 openrouter | image | bytedance-seed/seedream-5-5               | 0.0350 |  1
 openrouter | agent | google/gemini-3.8-flash-tts               | 0.0316 | 36
 openrouter | image | google/gemini-3.8-flash                   | 0.0034 |  2
 openrouter | stt   | google/gemini-3.8-flash                   | 0.0016 |  1
(19 rows)

```
## За 3 дня: по пользователям
```
 user_id |   tg_id    |  name  |  usd   |  n  
---------+------------+--------+--------+-----
       1 | 1245509871 | MAXSIM | 1.2997 | 109
       2 | 1515211624 | Даша   | 0.0660 |  24
(2 rows)

```
## Работы за 3 дня по видам и статусам
```
 kind  | status | n | credits 
-------+--------+---+---------
 image | done   | 6 |      96
 music | failed | 2 |      60
(2 rows)

```
## Последние 30 записей расходов
```
      t      |  provider  | kind  | user_id | job_id |   usd   |            note             
-------------+------------+-------+---------+--------+---------+-----------------------------
 11-14 00:01 | openrouter | agent |       1 |        | 0.00235 | google/gemini-3.8-flash-tts
 11-14 00:01 | openrouter | agent |       1 |        | 0.00207 | google/gemini-3.8-flash-tts
 11-14 00:01 | openrouter | agent |       1 |        | 0.00098 | google/gemini-3.8-flash-tts
 11-14 00:01 | openrouter | agent |       1 |        | 0.00274 | google/gemini-3.8-flash
 11-14 00:01 | openrouter | agent |       1 |        | 0.00281 | google/gemini-3.8-flash-tts
 11-14 00:01 | openrouter | agent |       1 |        | 0.00070 | google/gemini-3.8-flash-tts
 11-14 00:01 | openrouter | agent |       1 |        | 0.00080 | google/gemini-3.8-flash-tts
 11-14 00:01 | openrouter | agent |       1 |        | 0.00068 | google/gemini-3.8-flash-tts
 11-14 00:00 | openrouter | agent |       1 |        | 0.00048 | google/gemini-3.8-flash-tts
 11-14 00:00 | openrouter | agent |       1 |        | 0.00088 | google/gemini-3.8-flash-tts
 11-14 00:00 | openrouter | agent |       1 |        | 0.00182 | google/gemini-3.8-flash
 11-14 00:00 | openrouter | agent |       1 |        | 0.00160 | google/gemini-3.8-flash
 11-14 00:00 | openrouter | agent |       1 |        | 0.00145 | google/gemini-3.8-flash-tts
 11-14 00:00 | openrouter | agent |       1 |        | 0.00115 | google/gemini-3.8-flash-tts
 11-14 00:00 | openrouter | agent |       1 |        | 0.00081 | google/gemini-3.8-flash-tts
 11-14 00:00 | openrouter | agent |       1 |        | 0.00165 | google/gemini-3.8-flash
 11-13 23:58 | openrouter | agent |       1 |        | 0.00112 | google/gemini-3.8-flash-tts
 11-13 23:58 | openrouter | agent |       1 |        | 0.00158 | google/gemini-3.8-flash-tts
 11-13 23:58 | openrouter | agent |       1 |        | 0.00045 | google/gemini-3.8-flash-tts
 11-13 23:58 | openrouter | agent |       1 |        | 0.00218 | google/gemini-3.8-flash
 11-13 22:49 | openrouter | stt   |       1 |        | 0.00158 | google/gemini-3.8-flash
 11-13 19:39 | openrouter | agent |       1 |        | 0.00162 | google/gemini-3.8-flash
 11-13 19:38 | openrouter | agent |       1 |        | 0.00125 | google/gemini-3.8-flash
 11-13 19:38 | openrouter | agent |       1 |        | 0.00208 | google/gemini-3.8-flash
 11-13 19:38 | openrouter | agent |       1 |        | 0.00106 | google/gemini-3.8-flash
 11-13 19:27 | openrouter | agent |       1 |        | 0.00042 | google/gemini-3.8-flash-tts
 11-13 19:27 | openrouter | agent |       1 |        | 0.00052 | google/gemini-3.8-flash-tts
 11-13 19:27 | openrouter | agent |       1 |        | 0.00318 | google/gemini-3.8-flash
 11-13 19:27 | openrouter | agent |       1 |        | 0.00045 | google/gemini-3.8-flash-tts
 11-13 19:27 | openrouter | agent |       1 |        | 0.00090 | google/gemini-3.8-flash-tts
(30 rows)

```
