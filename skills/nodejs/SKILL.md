---
name: nodejs
description: >
  Создание и запуск Node.js приложений: веб-серверы (Express/Fastify), REST API,
  микросервисы, WebSocket, потоковая обработка данных, интеграции с внешними API и базами данных.
  Используй когда нужен Node.js вместо Python — для I/O-задач, real-time, веб-серверов.
triggers:
  - "node"
  - "nodejs"
  - "node.js"
  - "express"
  - "fastify"
  - "веб-сервер"
  - "web server"
  - "REST API"
  - "микросервис"
  - "websocket"
  - "потоковая передача"
---

# Node.js Development

Полноценный инструмент для создания и запуска Node.js-приложений через агент.

## Возможности

- **Веб-серверы** — Express, Fastify, Koa, Hono
- **REST API** — CRUD эндпоинты, маршрутизация, middleware
- **WebSocket** — real-time communication (ws, Socket.IO)
- **Микросервисы** — лёгкие сервисы, прокси, мосты
- **База данных** — SQLite (better-sqlite3), MongoDB, PostgreSQL (pg)
- **Потоковая обработка** — streams, chunked transfer, SSE
- **Интеграции** — HTTP-клиенты (axios, fetch), внешние API
- **Фоновый запуск** — серверы работают параллельно с агентом

## Проверка установки

```bash
node --version    # должна быть v18+
npm --version     # должна быть v9+
```

Если не установлен — используй run_command:
```bash
# Windows — скачать с https://nodejs.org/ (LTS)
# После установки перезапусти shell

# Проверка
node -v
```

## Сценарии использования

### 1. Быстрый HTTP-сервер (One-liner)

```bash
# Простой сервер на порту 3000
node -e "const http=require('http');http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({ok:true,time:new Date()}))}).listen(3000);console.log('Server on :3000')"
```

### 2. Express API сервер

Создай файл `server.js`:

```javascript
const express = require('express');
const app = express();
app.use(express.json());

app.get('/api/health', (req, res) => {
  res.json({ ok: true, uptime: process.uptime() });
});

app.get('/api/data', (req, res) => {
  res.json({ items: [1, 2, 3], ts: Date.now() });
});

app.post('/api/data', (req, res) => {
  console.log('Received:', req.body);
  res.json({ saved: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`API server on :${PORT}`));
```

Установи зависимости и запусти:

```bash
mkdir my-server && cd my-server
npm init -y
npm install express
node server.js
```

### 3. Фоновый сервер (параллельно с агентом)

```bash
# Запуск в фоне — не блокирует агент
start /B node server.js

# Или через PowerShell
Start-Process -WindowStyle Hidden -FilePath "node" -ArgumentList "server.js"

# Проверка что работает
curl http://localhost:3000/api/health

# Остановка
taskkill /IM node.exe /F
```

### 4. WebSocket сервер (real-time)

```javascript
const { WebSocketServer } = require('ws');
const wss = new WebSocketServer({ port: 8080 });

wss.on('connection', (ws) => {
  console.log('Client connected');
  ws.send(JSON.stringify({ type: 'connected', ts: Date.now() }));

  ws.on('message', (data) => {
    const msg = JSON.parse(data);
    console.log('Received:', msg);
    // Broadcast всем клиентам
    wss.clients.forEach(client => {
      if (client.readyState === 1) {
        client.send(JSON.stringify({ type: 'broadcast', ...msg }));
      }
    });
  });
});

console.log('WebSocket server on :8080');
```

### 5. Мост Node ↔ Python

Прокси от Node.js к Python-агенту:

```javascript
const express = require('express');
const axios = require('axios');
const app = express();
app.use(express.json());

const AGENT_URL = 'http://127.0.0.1:7860';

app.post('/chat', async (req, res) => {
  try {
    const { message } = req.body;
    const response = await axios.post(`${AGENT_URL}/api/chat`, { message }, {
      timeout: 30000,
      responseType: 'stream'
    });
    response.data.pipe(res);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/health', (req, res) => {
  res.json({ node: true, agent: AGENT_URL });
});

app.listen(3000, () => console.log('Bridge on :3000'));
```

### 6. Работа с файлами и данными

```javascript
const fs = require('fs');
const readline = require('readline');

// Потоковое чтение больших файлов
async function processLargeFile(filepath) {
  const stream = fs.createReadStream(filepath);
  const rl = readline.createInterface({ input: stream });
  const results = [];

  for await (const line of rl) {
    // Обработка каждой строки без загрузки всего файла в память
    if (line.includes('ERROR')) results.push(line.trim());
  }
  return results;
}

processLargeFile('app.log').then(errors => {
  console.log(`Found ${errors.length} errors`);
  console.log(errors.slice(0, 10));
});
```

### 7. SSE (Server-Sent Events) — стриминг к фронту

```javascript
const express = require('express');
const app = express();

app.get('/stream', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  });

  const interval = setInterval(() => {
    res.write(`data: ${JSON.stringify({ ts: Date.now(), value: Math.random() })}\n\n`);
  }, 1000);

  req.on('close', () => clearInterval(interval));
});

app.listen(3000);
```

### 8. База данных — SQLite

```javascript
const Database = require('better-sqlite3');
const db = new Database('data.db');

// Создание таблицы
db.exec(`
  CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// Вставка
const insert = db.prepare('INSERT INTO logs (level, message) VALUES (?, ?)');
insert.run('info', 'Server started');

// Выборка
const logs = db.prepare('SELECT * FROM logs ORDER BY id DESC LIMIT 20').all();
console.log(logs);
```

## Управление процессами

```bash
# Запуск в фоне (Windows)
start /B node server.js

# Список процессов Node
tasklist /FI "IMAGENAME eq node.exe"

# Остановить все Node-процессы
taskkill /IM node.exe /F

# Остановить конкретный процесс (по PID)
taskkill /PID 12345 /F

# Мониторинг в реальном времени
powershell "Get-Process node | Format-Table Id,CPU,WorkingSet64,StartTime"
```

## Установка пакетов

```bash
# Инициализация проекта
npm init -y

# Основные пакеты
npm install express          # веб-фреймворк
npm install fastify          # быстрый фреймворк
npm install ws               # WebSocket
npm install axios            # HTTP-клиент
npm install better-sqlite3   # SQLite
npm install pg               # PostgreSQL
npm install mongodb          # MongoDB
npm install socket.io        # Socket.IO
npm install cors             # CORS middleware
npm install dotenv           # Переменные окружения

# Dev-зависимости
npm install --save-dev nodemon  # авто-перезапуск
```

## Шаблоны проекта

```
my-node-server/
├── package.json
├── server.js          # точка входа
├── routes/
│   ├── index.js
│   └── api.js
├── middleware/
│   └── auth.js
├── lib/
│   └── db.js
└── .env               # конфигурация
```

## environment (.env)

```
PORT=3000
NODE_ENV=development
DATABASE_URL=./data.db
API_KEY=secret-key
AGENT_URL=http://127.0.0.1:7860
```

## Интеграция с OWL Agent

Node.js-сервер может работать как мост между внешними клиентами и OWL Agent:

1. Node.js принимает HTTP/WebSocket запросы
2. Проксирует их к Python-агенту (`http://127.0.0.1:7860/api/chat`)
3. Возвращает ответ клиенту
4. Добавляет свою логику (кэширование, rate limiting, трансформация)

Это позволяет построить API-слой без изменения основного сервера агента.
