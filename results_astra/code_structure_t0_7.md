<!-- prompt=code_structure model=gpt-6-astra temperature=0.7 time=2026-10-24 14:14 -->

## 1. Общая архитектура

Рекомендую **модульный монолит**: FastAPI-приложение с изолированными бизнес-модулями, отдельный процесс фоновых задач и React-приложение с пользовательской и административной частями.

Это проще в разработке и эксплуатации, чем микросервисы, но позволяет позднее выделить платежи, уведомления или обработку изображений в отдельные сервисы.

### Технологический стек

| Область | Технологии |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Работа с БД | PostgreSQL, SQLAlchemy 2, Alembic |
| Frontend | React, TypeScript, Vite |
| Маршрутизация | React Router |
| Серверное состояние | TanStack Query |
| Формы и валидация | React Hook Form, Zod |
| Локальное состояние | React state; Zustand при необходимости |
| Фоновые задачи | Celery, Redis как брокер |
| Изображения | S3-совместимое хранилище; MinIO локально |
| Email | SMTP или API email-провайдера |
| Платежи | Адаптер выбранного провайдера |
| Тесты | pytest, Vitest, React Testing Library, Playwright |
| Развертывание | Docker, reverse proxy, CI/CD |

```text
Браузер
   │ HTTPS
   ▼
Reverse proxy
   ├── /          → React static files
   └── /api/v1    → FastAPI
                        ├── PostgreSQL
                        ├── S3 / MinIO
                        └── платежный провайдер

PostgreSQL: outbox
   │
   ▼
Outbox dispatcher → Redis → Celery workers
                              ├── email
                              ├── обработка изображений
                              └── сверка платежей и обслуживание заказов

Платежный провайдер → webhook → FastAPI
```

**Базовые архитектурные правила:**

- Бизнес-логика не зависит от FastAPI, SQLAlchemy, Celery и платежного SDK.
- Модули взаимодействуют через прикладные интерфейсы и события, а не через чужие ORM-модели.
- PostgreSQL — источник истины для заказов, платежей и остатков.
- Сетевой вызов платежного провайдера не удерживает открытую транзакцию БД.
- Redis не используется как единственное хранилище критичных бизнес-данных.
- API и workers масштабируются независимо.

---

## 2. Структура директорий

Монорепозиторий упрощает синхронизацию API, frontend и инфраструктуры.

```text
ecommerce/
├── README.md                         # Запуск, команды, обзор архитектуры
├── .env.example                      # Переменные локальной инфраструктуры без секретов
├── .gitignore                        # Исключения: секреты, сборки, временные файлы
├── Makefile                          # Единые команды dev, lint, test, migrate
├── compose.yaml                      # PostgreSQL, Redis, MinIO, Mailpit, приложения
├── .github/
│   └── workflows/
│       └── ci.yml                    # Проверки, тесты, сборка контейнеров
│
├── docs/
│   ├── architecture.md               # Границы модулей и зависимости
│   ├── order-lifecycle.md             # Состояния заказов, оплат и резервов
│   ├── api-conventions.md             # Ошибки, пагинация, идемпотентность
│   ├── operations.md                 # Backup, restore, мониторинг, runbooks
│   └── adr/
│       └── 0001-modular-monolith.md   # Обоснование архитектурных решений
│
├── backend/
│   ├── pyproject.toml                # Зависимости, Ruff, mypy, pytest
│   ├── uv.lock                       # Зафиксированные версии Python-зависимостей
│   ├── .env.example                  # Пример backend-конфигурации
│   ├── Dockerfile                    # Образ API и фоновых процессов
│   ├── alembic.ini                   # Конфигурация миграций
│   ├── migrations/
│   │   ├── env.py                    # Подключение БД и регистрация metadata
│   │   └── versions/                 # Версионированные миграции
│   ├── src/
│   │   └── app/
│   │       ├── main.py               # Создание FastAPI, middleware, lifespan
│   │       ├── bootstrap.py          # Composition root: сборка зависимостей
│   │       ├── api/
│   │       │   ├── router.py         # Подключение /api/v1 роутеров
│   │       │   ├── dependencies.py   # Текущий пользователь, DI, проверки доступа
│   │       │   └── exception_handlers.py # Ошибки приложения → HTTP-ответы
│   │       ├── core/
│   │       │   ├── config.py         # Pydantic Settings
│   │       │   ├── security.py       # JWT, хеширование, криптографические утилиты
│   │       │   ├── logging.py        # Структурированные логи, request ID
│   │       │   └── telemetry.py      # Метрики и distributed tracing
│   │       ├── shared/
│   │       │   ├── domain/
│   │       │   │   ├── money.py      # Денежная сумма и валюта
│   │       │   │   └── events.py     # Базовые типы событий
│   │       │   └── application/
│   │       │       ├── errors.py     # Общие типизированные ошибки
│   │       │       ├── pagination.py # Контракты пагинации
│   │       │       └── uow.py        # Интерфейс транзакции Unit of Work
│   │       ├── infrastructure/
│   │       │   ├── database/
│   │       │   │   ├── base.py       # SQLAlchemy DeclarativeBase
│   │       │   │   ├── session.py    # Фабрики сессий API/worker
│   │       │   │   └── uow.py        # Реализация Unit of Work
│   │       │   ├── messaging/
│   │       │   │   ├── celery_app.py # Конфигурация Celery
│   │       │   │   ├── outbox.py     # Сохранение и получение outbox-событий
│   │       │   │   └── dispatcher.py # Публикация событий в брокер
│   │       │   └── cache/
│   │       │       └── redis.py      # Клиент Redis и инфраструктурные настройки
│   │       └── modules/
│   │           ├── identity/        # Учетные записи, сессии, роли, восстановление
│   │           ├── catalog/         # Товары, категории, SKU, цены
│   │           ├── inventory/       # Остатки и резервы
│   │           ├── cart/            # Корзина и ее позиции
│   │           ├── orders/          # Заказы и управление их жизненным циклом
│   │           ├── payments/        # Платежи, возвраты, webhooks
│   │           ├── media/           # Метаданные и жизненный цикл изображений
│   │           ├── notifications/   # Email-шаблоны и доставки
│   │           ├── reviews/         # Отзывы, рейтинги, модерация
│   │           └── audit/           # Аудит административных действий
│   └── tests/
│       ├── conftest.py              # Общие фикстуры и изоляция тестов
│       ├── factories/               # Генерация тестовых сущностей
│       ├── unit/                    # Чистая бизнес-логика
│       ├── integration/             # PostgreSQL, репозитории, адаптеры
│       ├── api/                     # HTTP-контракты и авторизация
│       └── contract/                # Контракты внешних интеграций
│
├── frontend/
│   ├── package.json                 # Зависимости и команды
│   ├── pnpm-lock.yaml               # Зафиксированные JS-зависимости
│   ├── .env.example                 # Только публичная frontend-конфигурация
│   ├── Dockerfile                   # Сборка и публикация статических файлов
│   ├── index.html                   # HTML entry point
│   ├── vite.config.ts               # Сборка и локальный proxy
│   ├── tsconfig.json                # TypeScript strict mode
│   ├── eslint.config.js             # Правила качества кода
│   ├── public/                      # Необрабатываемые статические ресурсы
│   ├── src/
│   │   ├── main.tsx                 # Инициализация React
│   │   ├── app/
│   │   │   ├── router.tsx           # Публичные, личные и admin-маршруты
│   │   │   ├── providers.tsx        # QueryClient, сессия, глобальные провайдеры
│   │   │   └── layouts/             # StorefrontLayout, AccountLayout, AdminLayout
│   │   ├── pages/
│   │   │   ├── storefront/          # Каталог, карточка товара, корзина, checkout
│   │   │   ├── account/             # Профиль, адреса, заказы
│   │   │   ├── auth/                # Вход, регистрация, восстановление
│   │   │   └── admin/               # Товары, заказы, отзывы, пользователи
│   │   ├── features/
│   │   │   ├── auth/                # Вход, обновление сессии, выход
│   │   │   ├── catalog/             # Поиск и фильтрация товаров
│   │   │   ├── cart/                # Операции с корзиной
│   │   │   ├── checkout/            # Оформление и переход к оплате
│   │   │   ├── orders/              # Работа с заказами
│   │   │   ├── reviews/             # Публикация и модерация отзывов
│   │   │   └── media-upload/        # Загрузка и подтверждение изображений
│   │   ├── entities/
│   │   │   ├── product/             # Типы представления и UI товара
│   │   │   ├── order/               # UI заказа
│   │   │   ├── user/                # UI пользователя
│   │   │   └── review/              # UI отзыва и рейтинга
│   │   ├── shared/
│   │   │   ├── api/
│   │   │   │   ├── client.ts        # HTTP-клиент и единая обработка ошибок
│   │   │   │   └── generated/       # Типы/клиент, сгенерированные из OpenAPI
│   │   │   ├── ui/                 # Переиспользуемые Button, Input, Modal
│   │   │   ├── config/             # Проверка публичных env-переменных
│   │   │   ├── lib/                # Форматирование, небольшие общие функции
│   │   │   └── styles/             # Тема и глобальные стили
│   │   └── test/
│   │       ├── setup.ts            # Настройка Vitest и Testing Library
│   │       └── mocks/              # MSW handlers для имитации API
│   └── e2e/
│       ├── checkout.spec.ts        # Покупка от каталога до результата оплаты
│       └── admin.spec.ts           # Основные административные сценарии
│
└── infra/
    ├── nginx/
    │   └── default.conf            # TLS termination/proxy, заголовки, лимиты
    ├── deploy/                     # Манифесты выбранной платформы развертывания
    └── monitoring/                 # Метрики, dashboards и alert rules
```

### Внутренняя структура backend-модуля

На примере заказов:

```text
orders/
├── public.py                       # Публичные прикладные контракты модуля
├── domain/
│   ├── entities.py                 # Order, OrderItem и бизнес-инварианты
│   ├── value_objects.py            # Снимок адреса, статусы
│   ├── events.py                   # OrderCreated, OrderPaid, OrderCancelled
│   └── policies.py                 # Правила переходов и отмены заказа
├── application/
│   ├── dto.py                      # Независимые от HTTP входы и результаты
│   ├── ports.py                    # Репозитории и интерфейсы внешних возможностей
│   └── use_cases/
│       ├── create_order.py         # Проверка корзины, расчет, резервирование
│       ├── cancel_order.py         # Отмена и инициирование компенсаций
│       └── get_order.py            # Получение заказа с проверкой владельца
├── infrastructure/
│   ├── models.py                   # SQLAlchemy-модели заказов
│   ├── repository.py               # Реализация хранения
│   └── tasks.py                    # Тонкие Celery-обертки над use cases
└── presentation/
    ├── schemas.py                  # Pydantic request/response
    ├── router.py                   # Пользовательские endpoints
    └── admin_router.py             # Административные endpoints
```

Этот шаблон используется **по необходимости**: не стоит создавать пустые слои и универсальные репозитории для каждого простого CRUD-объекта.

Frontend-feature обычно содержит `api/`, `model/`, `ui/` и расположенные рядом `*.test.ts(x)`. Зависимости направлены сверху вниз: `app → pages → features → entities → shared`.

---

## 3. Основные модули и зависимости

| Модуль | Ответственность | Основные зависимости |
|---|---|---|
| Identity | Регистрация, JWT, refresh-сессии, роли, сброс пароля | Notification port |
| Catalog | Товары, категории, SKU, цены, публикация | Media |
| Inventory | Остатки, резервирование, списание | PostgreSQL |
| Cart | Содержимое корзины; не окончательная стоимость | Catalog |
| Orders | Расчет итогов, снимки данных, переходы состояний | Catalog, Inventory, Payment port |
| Payments | Попытки оплаты, возвраты, проверка webhooks | Payment provider adapter |
| Media | Загрузка, проверка, варианты изображений | Object storage, workers |
| Notifications | Шаблоны писем, очередь доставки, повторы | Email adapter |
| Reviews | Отзывы, подтверждение покупки, модерация, агрегаты | Orders через read interface |
| Audit | Кто и какие административные изменения сделал | PostgreSQL |

Административная панель — **не отдельная копия бизнес-логики**. Ее endpoints вызывают те же use cases с дополнительными разрешениями и аудитом.

### Обработка заказа

1. Клиент отправляет создание заказа с `Idempotency-Key`.
2. Backend заново проверяет цены, доступность SKU и адрес; клиентские суммы не считаются доверенными.
3. В одной транзакции создаются заказ, позиции-снимки, резерв остатков и outbox-событие.
4. Платежная попытка создается с устойчивым ключом идемпотентности; вызов провайдера выполняется вне транзакции БД.
5. Проверенный webhook меняет состояние платежа и запускает допустимый переход заказа.
6. В той же транзакции сохраняются события для email и последующей обработки.
7. Просроченные неоплаченные заказы отменяются, резервы освобождаются.

Заказ, платеж и исполнение имеют **раздельные статусы**. Например, `payment=paid` не означает `fulfillment=shipped`.

Для поздней оплаты уже отмененного заказа нужна явная политика: повторное резервирование либо возврат. Такие случаи нельзя автоматически превращать в обычный оплаченный заказ без проверки остатков.

---

## 4. Паттерны проектирования

| Паттерн | Применение |
|---|---|
| Clean Architecture / Ports & Adapters | Независимость бизнес-логики от транспорта и SDK |
| Dependency Injection | Сборка адаптеров в `bootstrap.py`, передача через FastAPI dependencies |
| Repository | Хранение агрегатов; не механическая обертка каждой таблицы |
| Unit of Work | Общая транзакция для заказа, резервов и outbox |
| Adapter / Strategy | Замена платежного, email- и storage-провайдера |
| State machine | Только разрешенные переходы заказов и платежей |
| Transactional Outbox | Надежная фиксация бизнес-изменений и событий вместе |
| Idempotent Consumer | Безопасная повторная доставка задач и webhooks |
| Умеренное CQRS | Отдельные запросы для каталога/админки без обязательной отдельной БД |

Outbox и очередь обеспечивают доставку **как минимум один раз**, а не «ровно один раз». Обработчики обязаны учитывать дубликаты. Для email абсолютное отсутствие дублей зависит также от поддержки идемпотентности провайдером.

DRY применяется к действительно общей логике. Сходство двух DTO не является достаточным основанием связывать независимые модули общей моделью.

---

## 5. API-структура

Префикс: `/api/v1`.

### Основные endpoints

| Область | Endpoints |
|---|---|
| Аутентификация | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout` |
| Восстановление | `POST /auth/password-reset/request`, `/auth/password-reset/confirm` |
| Профиль | `GET/PATCH /users/me` |
| Адреса | `GET/POST /users/me/addresses`, `PATCH/DELETE /users/me/addresses/{id}` |
| Каталог | `GET /categories`, `GET /products`, `GET /products/{slug}` |
| Корзина | `GET /cart`, `POST /cart/items`, `PATCH/DELETE /cart/items/{id}` |
| Заказы | `POST /orders`, `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/cancel` |
| Оплата | `POST /orders/{id}/payments`, `GET /payments/{id}` |
| Webhooks | `POST /webhooks/payments/{provider}` |
| Отзывы | `GET/POST /products/{id}/reviews`, `PATCH/DELETE /reviews/{id}` |
| Изображения | `POST /admin/media/uploads`, `POST /admin/media/{id}/complete` |
| Управление товарами | `POST /admin/products`, `PATCH/DELETE /admin/products/{id}` |
| Управление заказами | `GET /admin/orders`, `POST /admin/orders/{id}/ship` |
| Возвраты | `POST /admin/payments/{id}/refunds` |
| Модерация | `GET /admin/reviews`, `PATCH /admin/reviews/{id}/moderation` |
| Пользователи и аудит | `GET /admin/users`, `GET /admin/audit-events` |

### Соглашения

- OpenAPI — источник контракта; frontend-клиент генерируется автоматически.
- Ошибки — `application/problem+json` с машинным `code` и `request_id`.
- Коллекции имеют ограниченный `limit`, предсказуемую сортировку и пагинацию.
- Денежные значения передаются в минимальных единицах валюты и с кодом валюты; не `float`.
- Создание заказа, платежа и возврата поддерживает идемпотентность. Ключ связывается с пользователем, операцией и хешем запроса.
- Доступ к объекту проверяется на backend: пользователь видит только собственные заказы и платежи.
- Административные изменения проверяют конкретные permissions, а не только наличие авторизации.

### JWT и безопасность

- Короткоживущий JWT access token хранится в памяти frontend и отправляется в `Authorization: Bearer`.
- Refresh token — случайный непрозрачный секрет в `HttpOnly`, `Secure`, `SameSite` cookie; в БД хранится его хеш.
- Refresh-сессии ротируются; повторное использование старого токена отзывает семейство сессий.
- Cookie-endpoints защищаются проверкой Origin и CSRF-механизмом согласно схеме развертывания.
- Проверяются подпись JWT, фиксированный допустимый алгоритм, `exp`, `iss`, `aud`.
- Пароли хешируются Argon2id; login/reset защищаются rate limiting.
- Для администраторов рекомендуется MFA.
- React route guards нужны для UX, но не заменяют backend-авторизацию.

---

## 6. Структура PostgreSQL

Для начала достаточно одной БД с логическим владением таблицами по модулям.

| Таблица | Основные поля и ограничения |
|---|---|
| `users` | `id`, `email`, `password_hash`, `status`, timestamps; unique нормализованного email |
| `roles`, `permissions` | Справочники ролей и разрешений |
| `user_roles`, `role_permissions` | Связи many-to-many с составными unique |
| `refresh_sessions` | `user_id`, `token_hash`, `family_id`, `expires_at`, `revoked_at` |
| `addresses` | `user_id`, адресные поля |
| `categories` | `id`, `parent_id`, `slug UNIQUE`, `name` |
| `products` | `id`, `slug UNIQUE`, `title`, `description`, `status` |
| `product_categories` | Связь товаров и категорий |
| `product_variants` | `product_id`, `sku UNIQUE`, `attributes JSONB`, `price_minor`, `currency` |
| `media_assets` | `object_key UNIQUE`, MIME, размер, dimensions, `status` |
| `product_images` | `product_id`, `asset_id`, `position`, `alt_text` |
| `inventory` | `variant_id UNIQUE`, `on_hand`, `reserved`, ограничения неотрицательности |
| `stock_reservations` | `order_id`, `variant_id`, `quantity`, `status`, `expires_at` |
| `carts`, `cart_items` | Владелец, SKU, количество; unique `(cart_id, variant_id)` |
| `orders` | `user_id`, `status`, суммы, валюта, снимок адреса, `version` |
| `order_items` | `order_id`, SKU/название-снимок, цена-снимок, количество, итоги |
| `payments` | `order_id`, провайдер, внешний ID, сумма, валюта, статус, idempotency key |
| `refunds` | `payment_id`, сумма, статус, внешний ID |
| `payment_webhook_events` | Провайдер, внешний event ID, статус обработки; составной unique |
| `reviews` | `user_id`, `product_id`, `rating`, текст, статус модерации |
| `product_rating_stats` | `product_id`, `rating_sum`, `review_count` |
| `notification_deliveries` | Получатель, шаблон, event ID, статус, попытки, provider ID |
| `outbox_events` | Тип, aggregate ID, payload, время, состояние публикации |
| `idempotency_records` | Scope, ключ, request hash, результат, срок хранения |
| `audit_events` | Actor, действие, объект, безопасные before/after данные, время |

### Важные инварианты

- `rating BETWEEN 1 AND 5`.
- Для базовой политики — один отзыв пользователя на товар: unique `(user_id, product_id)`.
- Рейтинг рассчитывается только по опубликованным отзывам; агрегат можно перестроить из исходных данных.
- Подтверждение покупки проверяется сервером по подходящему состоянию заказа.
- Исторический заказ не изменяется при редактировании товара или адреса.
- Резервирование выполняется атомарным условным обновлением либо блокировкой строк; простая последовательность «прочитать остаток → записать» недопустима.
- Для нескольких SKU используется стабильный порядок блокировок и обработка deadlock/retry.
- Индексы предусматриваются на внешних ключах и частых фильтрах: заказы пользователя, статусы/даты, события outbox, истечение резервов.
- Время хранится как `timestamptz`, работа приложения — в UTC.

### Платежная интеграция

Используйте hosted checkout или токенизацию провайдера: карточные данные не проходят через ваше приложение.

Webhook проверяет подпись по исходному телу, допустимость события, соответствие заказа, суммы и валюты. Событие сначала надежно сохраняется, затем обрабатывается идемпотентно. Redirect браузера после оплаты **не подтверждает платеж**.

Периодическая сверка с провайдером восстанавливает состояние после потерянных webhook или неопределенного результата сетевого вызова.

### Изображения

В БД хранятся метаданные и ключи объектов, а не бинарные изображения.

1. Backend выдает ограниченное разрешение на загрузку в карантинный префикс.
2. После загрузки worker проверяет реальный формат, размер, количество пикселей и декодируемость.
3. Создаются безопасно перекодированные варианты; лишние метаданные удаляются.
4. Только готовые изображения становятся публичными через CDN.
5. Неподтвержденные и осиротевшие объекты удаляются по lifecycle-политике.

---

## 7. Конфигурация и эксплуатация

Пример `backend/.env.example`:

```dotenv
APP_ENV=development
PUBLIC_APP_URL=http://localhost:5173
API_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/ecommerce
WORKER_DATABASE_URL=postgresql+psycopg://app:app@postgres:5432/ecommerce
CELERY_BROKER_URL=redis://redis:6379/0

JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private_key
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public_key
JWT_ISSUER=ecommerce-api
JWT_AUDIENCE=ecommerce-web
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_DAYS=30

S3_ENDPOINT_URL=http://minio:9000
S3_REGION=us-east-1
S3_BUCKET=ecommerce-media
S3_ACCESS_KEY_ID=local-development
S3_SECRET_ACCESS_KEY=local-development-only
MEDIA_PUBLIC_BASE_URL=http://localhost:9000/ecommerce-media

EMAIL_BACKEND=smtp
SMTP_HOST=mailpit
SMTP_PORT=1025
EMAIL_FROM=no-reply@example.test

PAYMENT_PROVIDER=selected-provider
PAYMENT_SECRET_KEY=
PAYMENT_WEBHOOK_SECRET=

CORS_ORIGINS=["http://localhost:5173"]
LOG_LEVEL=INFO
OTEL_EXPORTER_OTLP_ENDPOINT=
```

API использует async-сессии, Celery-задачи могут использовать синхронные SQLAlchemy-сессии. Движки и сессии создаются в соответствующем процессе, не разделяются между процессами или задачами.

Frontend:

```dotenv
VITE_API_BASE_URL=/api/v1
```

**Любая `VITE_*` переменная доступна пользователю.** Секреты там запрещены.

### Production

- Секреты поступают из secret manager, а не из репозитория.
- Миграции запускаются отдельным deployment job, не каждой репликой API.
- API stateless; корзина и refresh-сессии находятся в PostgreSQL.
- Workers масштабируются по очередям: email, media, платежные операции.
- Для критичных задач предусмотрены backoff, лимит попыток и ручной повтор.
- Контролируются возраст outbox-событий, очередь, ошибки webhook, задержки email и зависшие платежи.
- Настраиваются PostgreSQL backups/PITR и регулярные проверки восстановления.
- Логи исключают пароли, токены, карточные данные и избыточные персональные сведения.

---

## 8. Тесты и контроль качества

| Уровень | Что проверять |
|---|---|
| Backend unit | Расчеты денег, переходы состояний, отмену, резервирование, правила отзывов |
| Integration | SQL-ограничения, транзакции, конкурентные покупки, outbox, storage |
| API | Валидацию, RBAC, доступ к чужим объектам, пагинацию, refresh rotation |
| Payment contract | Подписи webhook, дубликаты, события не по порядку, sandbox API |
| Frontend unit/component | Формы, состояния загрузки/ошибок, корзину, права отображения |
| E2E | Регистрация → покупка → подтверждение → заказ → отзыв; admin-сценарии |

Для интеграционных тестов используется **настоящий PostgreSQL**, например через Testcontainers: SQLite не воспроизводит нужную семантику блокировок и типов.

Приоритетные сценарии отказов:

- Два покупателя одновременно покупают последнюю единицу.
- Клиент повторяет создание заказа после таймаута.
- Webhook приходит несколько раз или раньше завершения запроса оплаты.
- Worker завершается после внешнего вызова, но до фиксации результата.
- Резерв истекает одновременно с подтверждением платежа.
- Отзыв скрыт модератором, и рейтинг корректно обновляется.
- Пользователь пытается получить чужой заказ или административный доступ.

CI выполняет Ruff, mypy, pytest, ESLint, TypeScript checking, frontend-тесты, проверку актуальности OpenAPI-клиента и сборку. Для критичных бизнес-инвариантов важнее полное покрытие сценариев, чем формальный общий процент покрытия.

**Итог:** структура сохраняет простоту единого приложения, но дает четкие границы модулей, надежный транзакционный контур заказов и платежей, независимое масштабирование фоновых задач и возможность постепенно выделять сервисы без переписывания бизнес-логики.