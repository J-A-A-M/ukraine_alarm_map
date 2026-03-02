# Redis Deployment

Скрипт для розгортання Redis сервера з підтримкою персистентності даних, аутентифікації та налаштування портів.

## Можливості

- Налаштування порту Redis
- Аутентифікація з логіном і паролем (Redis 6+ ACL)
- Підтримка legacy аутентифікації (тільки пароль)
- Збереження даних на диск (RDB + AOF)
- Налаштування інтервалів збереження
- Налаштування рівня логування

## Використання

### Базове використання

```bash
./redeploy_redis.sh \
    --password "your_secure_password"
```

### Повне використання з усіма параметрами

```bash
./redeploy_redis.sh \
    --port 6379 \
    --username "redis_user" \
    --password "your_secure_password" \
    --data-path "/var/lib/redis" \
    --save-interval "900 1 300 10 60 10000" \
    --appendonly "yes" \
    --logging "INFO"
```

## Параметри

- `-p, --port` - Порт Redis (за замовчуванням: 6379)
- `-u, --username` - Ім'я користувача для аутентифікації (Redis 6+ ACL)
- `-w, --password` - Пароль для аутентифікації
- `-d, --data-path` - Шлях для збереження даних (за замовчуванням: /var/lib/redis)
- `-s, --save-interval` - Інтервали збереження RDB (за замовчуванням: "900 1 300 10 60 10000")
  - Формат: "seconds changes [seconds changes ...]"
  - 900 1 = зберігати після 900 секунд якщо змінився 1 ключ
  - 300 10 = зберігати після 300 секунд якщо змінилось 10 ключів
  - 60 10000 = зберігати після 60 секунд якщо змінилось 10000 ключів
- `-a, --appendonly` - Увімкнути AOF персистентність (за замовчуванням: yes)
- `-c, --clean-data` - Видалити всі існуючі дані перед запуском (за замовчуванням: no)
- `-l, --logging` - Рівень логування: DEBUG, INFO, WARNING, ERROR (за замовчуванням: INFO)

## Персистентність даних

Redis підтримує два методи збереження даних:

### RDB (Redis Database)

- Створює snapshot бази даних через певні інтервали
- Файл: `dump.rdb`
- Налаштовується через параметр `--save-interval`

### AOF (Append Only File)

- Записує кожну операцію запису в лог
- Файл: `appendonly.aof`
- Більш надійний, але займає більше місця
- Налаштовується через параметр `--appendonly`

## Аутентифікація

### ⚠️ Рекомендація: Використовуйте простий пароль (без username)

Для уникнення проблем з ACL при завантаженні AOF файлів, **рекомендується використовувати простий пароль**:

```bash
./redeploy_redis.sh \
    --password "secure_password"
```

Підключення:
```bash
redis-cli -h localhost -p 6379 -a secure_password
```

### Redis 6+ ACL (з username) - для досвідчених користувачів

⚠️ **Увага**: Використання ACL з username може викликати проблеми при завантаженні AOF файлів.

```bash
./redeploy_redis.sh \
    --username "admin" \
    --password "secure_password"
```

Підключення:
```bash
redis-cli -h localhost -p 6379 --user admin --pass secure_password
```

**Примітка**: При використанні username, користувач `default` залишається активним з повними правами для коректного завантаження AOF файлів.

## Приклади

### Розробка (без аутентифікації)

```bash
./redeploy_redis.sh
```

### Продакшн (з аутентифікацією і персистентністю)

```bash
./redeploy_redis.sh \
    --port 6379 \
    --username "redis_admin" \
    --password "$(openssl rand -base64 32)" \
    --data-path "/mnt/redis-data" \
    --appendonly "yes" \
    --logging "WARNING"
```

### Кешування (без персистентності)

```bash
./redeploy_redis.sh \
    --password "cache_password" \
    --appendonly "no" \
    --save-interval ""
```

## Docker мережа

Контейнер підключається до мережі `jaam` та експонує порт назовні.

## Перевірка роботи

```bash
# Перевірити статус контейнера
docker ps | grep map_redis

# Переглянути логи
docker logs map_redis

# Підключитися до Redis CLI
docker exec -it map_redis redis-cli -a "your_password"

# Перевірити наявність файлів даних
ls -lh /var/lib/redis/
```

## Перевірка персистентності

Щоб переконатися, що дані зберігаються між перезапусками:

```bash
# 1. Записати тестові дані
docker exec -it map_redis redis-cli -a "your_password" SET test_key "test_value"
docker exec -it map_redis redis-cli -a "your_password" SET another_key "another_value"

# 2. Примусово зберегти дані (опціонально, Redis і так збереже автоматично)
docker exec -it map_redis redis-cli -a "your_password" SAVE

# 3. Перевірити файли на диску
ls -lh /var/lib/redis/dump.rdb /var/lib/redis/appendonly.aof

# 4. Перезапустити контейнер
./redeploy_redis.sh --password "your_password"

# 5. Перевірити, що дані залишилися
docker exec -it map_redis redis-cli -a "your_password" GET test_key
# Має вивести: "test_value"

docker exec -it map_redis redis-cli -a "your_password" KEYS "*"
# Має показати всі збережені ключі
```

## Моніторинг збереження даних

```bash
# Перевірити останнє успішне збереження
docker exec -it map_redis redis-cli -a "your_password" LASTSAVE

# Інформація про персистентність
docker exec -it map_redis redis-cli -a "your_password" INFO persistence

# Примусове збереження (блокуюче)
docker exec -it map_redis redis-cli -a "your_password" SAVE

# Примусове збереження (фонове)
docker exec -it map_redis redis-cli -a "your_password" BGSAVE
```

## Резервне копіювання

Для створення резервної копії скопіюйте файли з директорії даних:

```bash
# RDB snapshot
cp /var/lib/redis/dump.rdb /backup/dump.rdb.$(date +%Y%m%d)

# AOF log
cp /var/lib/redis/appendonly.aof /backup/appendonly.aof.$(date +%Y%m%d)
```

## Відновлення

Для відновлення скопіюйте файли назад у директорію даних перед запуском контейнера:

```bash
cp /backup/dump.rdb /var/lib/redis/dump.rdb
cp /backup/appendonly.aof /var/lib/redis/appendonly.aof
```

## Troubleshooting

### ACL помилки при завантаженні AOF

Якщо ви бачите помилку:
```
CRITICAL == This server is sending an error to its AOF-loading-client: '-NOPERM ACLs rules changed...'
```

Це означає, що AOF файл був створений з іншими ACL правилами.

**Рішення 1: Перейти на простий пароль (РЕКОМЕНДОВАНО)**
```bash
# Зупинити контейнер
docker stop map_redis

# Видалити AOF файл (RDB файл залишиться)
rm /shared_data/redis/appendonly.aof
rm /shared_data/redis/users.acl

# Запустити БЕЗ username (тільки password)
./redeploy_redis.sh --password "your_password"

# Дані відновляться з dump.rdb
```

**Рішення 2: Відключити AOF, використовувати тільки RDB**
```bash
./redeploy_redis.sh \
    --password "your_password" \
    --appendonly "no" \
    --save-interval "900 1 300 10 60 10000"
```

**Рішення 3: Повна очистка даних (втратите всі дані)**
```bash
./redeploy_redis.sh --clean-data --password "your_password"
```

**Рішення 4: Для експертів - виправити ACL файл вручну**
```bash
# Відредагувати ACL файл, щоб default user був активний
echo "user default on nopass ~* &* +@all" > /shared_data/redis/users.acl
echo "user your_username on >your_password ~* &* +@all" >> /shared_data/redis/users.acl
```

### Очистка даних

Для повного очищення даних Redis:
```bash
docker stop map_redis
docker rm map_redis
rm -rf /var/lib/redis/*
./redeploy_redis.sh --password "new_password"
```
