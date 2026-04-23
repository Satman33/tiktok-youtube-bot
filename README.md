# Video Downloader Bot

Telegram bot and admin console for downloading TikTok and YouTube media.

## Stack

- Backend: Python 3.11+, FastAPI, aiogram, SQLAlchemy
- Database: PostgreSQL
- Cache: Redis
- Downloader: yt-dlp
- Frontend: React + Vite
- Migrations: Alembic

## Project Layout

```text
.
├── app/                    # bot, api, db, services
├── alembic/                # database migrations
├── deploy/                 # systemd examples
├── frontend/               # admin frontend
├── docker-compose.yml      # local/dev compose
├── docker-compose.prod.yml # production compose
├── Dockerfile              # backend image
└── .env.example
```

## Local Development

### 1. Create environment file

```powershell
Copy-Item .env.example .env
```

Fill in:

- `BOT_TOKEN`
- `DATABASE_URL`
- `REDIS_URL`
- `YTDLP_COOKIES_PATH`

For PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://botuser:botpass@localhost:5432/botdb
```

### 2. Install backend dependencies

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 3. Run migrations

```powershell
alembic upgrade head
```

### 4. Run backend

API:

```powershell
python -m app.main
```

Bot:

```powershell
python -m app.bot.main
```

### 5. Run frontend

```powershell
cd frontend
npm install
npm run dev
```

## Docker Compose

### Local / development

```bash
docker compose up --build
```

### Production

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Production compose includes:

- PostgreSQL
- Redis
- FastAPI API
- Telegram bot
- Nginx-served frontend on port `80`

## Ubuntu 22 Production Notes

Recommended minimum:

- Docker Engine + Docker Compose plugin
- Node.js only if you build frontend outside Docker
- valid `cookies.txt` for restricted YouTube videos

Typical flow:

```bash
git clone <private-repo-url> video-downloader
cd video-downloader
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

## Database

The project is now PostgreSQL-first.

- Use `alembic upgrade head` before starting services.
- SQLite may still work for local experiments, but PostgreSQL is the recommended runtime database.

## Cookies

Age-restricted or authenticated YouTube videos require `cookies.txt`.

- Keep `cookies.txt` out of Git
- Mount it in Docker or place it in project root
- Refresh it when YouTube invalidates the session

## Before Pushing to Git

Make sure these are not committed:

- `.env`
- `cookies.txt`
- `botdb.sqlite`
- `frontend/node_modules`
- `frontend/dist`

`.gitignore` already excludes them.

## Git Push Example

Create private repo, then:

```bash
git init
git add .
git commit -m "Initial production-ready bot setup"
git branch -M main
git remote add origin <your-private-repo-url>
git push -u origin main
```

## Important Security Note

If a real bot token was ever shared in logs, screenshots or chat, rotate it in `@BotFather` before deployment.
