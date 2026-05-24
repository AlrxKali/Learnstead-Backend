# Learnstead Backend

REST API backend for the Learnstead platform, built with FastAPI and Supabase.

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- [UV](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Supabase CLI](https://supabase.com/docs/guides/cli/getting-started) (for local development)

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd Learnstead-Backend
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Set up environment variables

Copy the example env file and fill in your Supabase credentials:

```bash
cp .env.example .env
```

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### 4. Set up Supabase (local development)

Start the local Supabase instance:

```bash
supabase start
```

This starts PostgreSQL, Auth, and the REST API locally. The local credentials will be printed to the console — update your `.env` accordingly:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_KEY=<anon-key-from-supabase-start>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key-from-supabase-start>
```

Run database migrations:

```bash
supabase db push
```

## Running the app

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

Interactive API docs are at `http://127.0.0.1:8000/docs`.

## API Endpoints

### Auth (`/auth`)

| Method | Endpoint        | Description              |
|--------|-----------------|--------------------------|
| POST   | `/auth/signup`  | Create a new user        |
| POST   | `/auth/login`   | Log in and get JWT tokens|

### Businesses (`/businesses`)

| Method | Endpoint                                                  | Description                         |
|--------|-----------------------------------------------------------|-------------------------------------|
| GET    | `/businesses/categories`                                  | List all categories                 |
| POST   | `/businesses/categories`                                  | Create a category                   |
| GET    | `/businesses/subcategories`                               | List subcategories                  |
| POST   | `/businesses/subcategories`                               | Create a subcategory                |
| POST   | `/businesses/categories/{category_id}/subcategories`      | Link subcategory to category        |
| DELETE | `/businesses/categories/{category_id}/subcategories/{id}` | Unlink subcategory from category    |
| POST   | `/businesses`                                             | Create a business (authenticated)   |
| GET    | `/businesses/me`                                          | Get current user's business         |
| PUT    | `/businesses/me`                                          | Update current user's business      |
| DELETE | `/businesses/me`                                          | Delete current user's business      |

## Project Structure

```
app/
├── main.py            # FastAPI app entry point
├── config.py          # Settings (env vars via pydantic-settings)
├── dependencies.py    # Auth & DB dependencies
├── routers/
│   ├── auth.py        # Auth endpoints
│   └── businesses.py  # Business endpoints
└── schemas/
    ├── auth.py        # Auth request/response models
    └── businesses.py  # Business request/response models
supabase/
├── config.toml        # Local Supabase config
└── migrations/        # SQL migration files
```
