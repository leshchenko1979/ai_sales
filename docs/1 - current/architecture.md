`# Текущая архитектура системы

## Общая структура

### 1. Основные компоненты
1. **Telegram интеграция**
   - MTProto клиент через Pyrogram
   - Long polling для взаимодействия с Telegram API
   - Базовая обработка событий
   - Простая система сессий
   - Команды для тестового режима
   - Только исходящие соединения, без веб-хуков

2. **Диалоговая система**
   - Промпты для LLM с гибкой системой форматирования
   - Контекст диалога с поддержкой истории
   - Продвинутая система обработки сообщений через DialogConductor
   - Асинхронная пакетная обработка сообщений
   - Компоненты анализа и советов (SalesAdvisor)
   - Управление продажами через SalesManager
   - Тестовый режим для отдела продаж

3. **Хранение данных**
   - База данных на сервере монолита
   - Файловое хранилище для логов
   - Сохранение тестовых диалогов
   - Отсутствие кэширования

4. **Инфраструктура**
   - Контейнеризация через Docker
   - Автоматический деплой с проверками качества кода
   - Отдельная инфраструктура для n8n и Traefik
   - Минимальные сетевые требования (только исходящие соединения)

## Ограничения

### 1. Безопасность
1. **Управление аккаунтами**
   - Базовая нетестированная ротация
   - Простой механизм прогрева
   - Минимальный мониторинг
   - Отсутствие автоматизации

2. **Защита от блокировок**
   - Экспериментальные ограничения
   - Отсутствие проверенных метрик
   - Ручное вмешательство при проблемах

### 2. Масштабируемость
1. **Обработка нагрузки**
   - Асинхронная обработка через asyncio
   - Пакетная обработка сообщений
   - Отложенная обработка с настраиваемыми задержками

2. **Распределение**
   - Монолитная архитектура
   - Централизованное выполнение
   - Отсутствие балансировки

## Технический долг

### 1. Код
1. **Качество**
   - Базовые автоматизированные проверки (isort, black)
   - Запуск тестов при деплое
   - Базовое логирование
   - Простая обработка ошибок

2. **Организация**
   - Монолитная структура
   - Слабая модульность
   - Улучшенная документация по сетевой архитектуре

### 2. Данные
1. **Хранение**
   - Простая схема данных
   - Отсутствие миграций
   - Только логирование в файлы

2. **Обработка**
   - Синхронные операции
   - Отсутствие валидации
   - Базовая обработка ошибок
