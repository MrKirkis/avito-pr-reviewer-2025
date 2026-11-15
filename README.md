# Сервис назначения ревьюеров для Pull Request'ов (Авито, осень 2025)

Решение тестового задания на стажировку Backend в Авито (осенняя волна 2025).
- **Исходное задание:** [Backend-trainee-assignment-autumn-2025.md](https://github.com/avito-tech/tech-internship/blob/main/Tech%20Internships/Backend/Backend-trainee-assignment-autumn-2025/Backend-trainee-assignment-autumn-2025.md)
- **Стек:** Python 3.11, FastAPI, Pydantic v2, Pytest, Docker & Docker Compose.

## Что реализовано (объём работы)

**Сделано (вся обязательная часть ТЗ):**
- `POST /team/add` и `GET /team/get` – создание команды с участниками и получение состава команды.
- `POST /users/setIsActive` – переключение флага активности пользователя (`is_active`). Неактивные пользователи не назначаются на ревью.
- `POST /pullRequest/create` – создание PR и автоматическое назначение до 2 случайных активных ревьюеров из команды автора (исключая самого автора). Если доступных кандидатов меньше двух, назначается 0 или 1.
- `POST /pullRequest/reassign` – замена одного ревьюера на случайного активного участника из команды заменяемого ревьюера (исключая автора PR и второго действующего ревьюера).
- `POST /pullRequest/merge` – идемпотентный перевод PR в статус `MERGED` с фиксацией времени `mergedAt` (повторный вызов не возвращает ошибку и не меняет `mergedAt`). После `MERGED` менять ревьюеров запрещено.
- `GET /users/getReview` – список PR, назначенных конкретному пользователю.
- Запуск на порту `8080` через `docker-compose up`, автотесты на `pytest` и автопроверка в GitHub Actions CI.

**Что не входит в текущий объём и почему:**
- Внешняя СУБД PostgreSQL и миграции – по условию задания явно разрешена `in-memory` реализация, что позволяет поднять и проверить сервис одной командой без внешней БД.
- Дополнительные задания со звёздочкой (эндпоинт статистики, массовая деактивация за `< 100 мс` и нагрузочное тестирование SLI).

## Принятые допущения (по разделу «Ход решения» ТЗ)

1. **Переназначение без доступных кандидатов:** если в команде заменяемого ревьюера нет других активных участников (кроме автора PR и уже назначенного второго ревьюера), сервис возвращает `409 Conflict` с кодом `NO_CANDIDATE`, а не `500 Internal Server Error`.
2. **Деактивация уже назначенного ревьюера:** смена `is_active = false` через `/users/setIsActive` гарантирует, что пользователь не попадёт в новые назначения, но не сбрасывает его автоматически из уже открытых PR до явного вызова `/pullRequest/reassign`.
3. **Идемпотентность `merge`:** повторный вызов `/pullRequest/merge` для закрытого PR возвращает `200 OK` и сохраняет исходную метку времени `mergedAt` первого слияния.

## Как запустить

### Вариант 1: Через Docker Compose (рекомендуемый)
```bash
docker-compose up --build
```
Сервис поднимется на `http://localhost:8080`. Интерактивная документация Swagger UI доступна по адресу `http://localhost:8080/docs`.

### Вариант 2: Локальный запуск без Docker
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Как проверяли (запуск тестов)
```bash
pytest -v
```

### Пример проверки основного сценария через curl
```bash
# 1. Создать команду
curl -X POST http://localhost:8080/team/add -H "Content-Type: application/json" \
  -d '{"team_name":"backend","members":[{"user_id":"u1","username":"Alice","is_active":true},{"user_id":"u2","username":"Bob","is_active":true},{"user_id":"u3","username":"Charlie","is_active":true}]}'

# 2. Создать PR (автоматически назначит u2 и u3)
curl -X POST http://localhost:8080/pullRequest/create -H "Content-Type: application/json" \
  -d '{"pull_request_id":"pr-1","pull_request_name":"Fix API","author_id":"u1"}'

# 3. Смержить PR
curl -X POST http://localhost:8080/pullRequest/merge -H "Content-Type: application/json" \
  -d '{"pull_request_id":"pr-1"}'
```
