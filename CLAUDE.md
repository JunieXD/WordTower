# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

请使用简体中文和我交流

## Project Overview

WordTower is a gamified English vocabulary learning platform backend built with FastAPI, PostgreSQL, and SQLModel. Users progress through levels (floors) by answering word questions, earning experience and coins, while managing their character's HP, attack, and critical rate stats.

## Development Commands

### Database Setup & Migration
```bash
# Initialize database (creates all tables)
uv run python -m app.scripts.init_db

# Run Alembic migrations (preferred for production)
cd app
uv run alembic upgrade head

# Import words from StarDict SQLite database
uv run python -m app.scripts.import_words <sqlite_db_path> [batch_size]
# Example:
uv run python -m app.scripts.import_words app/scripts/stardict.db 10000
```

### Running the Application
```bash
# Development server with hot reload
uv run uvicorn app.main:app --reload
```

## Architecture

### Core Domain Model

The application implements a **tower-climbing game** where users learn vocabulary:

- **User**: Player with RPG-like stats (HP, attack, crit_rate) and progression (max_floor, exp, coins)
- **Word**: Vocabulary with difficulty levels, phonetics, meanings, and tags
- **Level**: Represents floors in the tower, containing questions
- **Question**: Word-based challenges linked to levels via `LevelQuestionLink`
- **Challenge**: A user's attempt at a level, tracks HP, status (in_progress/completed/failed), and rewards
- **Library**: User-created or public word collections, linked to words via `LibraryWordLink`
- **Buff/Prop**: Power-ups and items users can use in challenges via link tables
- **UserWordRecord**: Tracks individual word mastery and review schedules
- **UserUserLink**: Friend relationships with status tracking

### Database Architecture

**SQLModel** (SQLAlchemy + Pydantic) is used for ORM with PostgreSQL. All models inherit from `SQLModel` with `table=True`.

**Link Tables** (many-to-many relationships):
- `ChallengeBuffLink`, `ChallengePropLink`: Items used in challenges
- `LevelQuestionLink`: Questions assigned to levels
- `LibraryWordLink`: Words in libraries
- `QuestionWordLink`: Words associated with questions
- `UserUserLink`: Friend connections

**Database Configuration**: Set via environment variable `DATABASE_URL` in `app/utils/config.py` (defaults to `postgresql://postgres:123456@localhost:5432/wordtower`).

**Alembic** is used for schema migrations. Migration files are in `app/alembic/versions/`. Always run migrations from the `app/` directory.

### Authentication & Security

- **Password Hashing**: Argon2 via passlib (`app/utils/security.py`)
- **JWT Tokens**: HS256 algorithm with 1-day expiration, includes `jti` (unique token ID)
- **Token Storage**: HTTP-only cookies (configured in API responses)
- **Dependencies**: `get_current_user` in `app/api/dependencies.py` validates JWT from cookies
- **Secret Key**: Configured via `SECRET_KEY` environment variable (defaults to "wordtower")

### API Response Pattern

All API responses use standardized helpers from `app/api/api_responses.py`:
- `success_response()`: 200 OK with optional cookie setting
- `created_response()`: 201 Created
- `not_found_response()`: 404 Not Found
- `conflict_response()`: 409 Conflict

Responses can set or delete authentication cookies via `cookie` and `delete_cookie` parameters.

### CORS Configuration

CORS middleware is configured in `app/main.py` using origins from `app/utils/cors.py`. Allows credentials (cookies) and all methods/headers.

### Project Structure
```
app/
├── alembic/           # Database migrations
├── api/
│   ├── routes/        # API endpoints (e.g., auth.py)
│   ├── dependencies.py # Auth dependency injection
│   └── api_responses.py # Standardized response helpers
├── db/
│   ├── database.py    # SQLModel engine & session management
│   └── user.py        # User-specific DB operations
├── models/            # SQLModel definitions (all domain models)
├── scripts/
│   ├── init_db.py     # Database initialization
│   ├── import_words.py # Word import from SQLite
│   └── stardict.py    # SQLite dictionary utilities (3rd party)
├── utils/
│   ├── config.py      # Settings (DATABASE_URL, SECRET_KEY)
│   ├── security.py    # Password & JWT handling
│   └── cors.py        # CORS origins
└── main.py            # FastAPI app entry point
```

### Session Management

Use `SessionDep` (type alias for `Annotated[Session, Depends(get_session)]`) for dependency injection in route handlers. Sessions are automatically managed via context manager in `get_session()`.

### Model Patterns

Models follow this pattern:
- **Base class** (e.g., `UserBase`): Shared fields
- **Table model** (e.g., `User`): Inherits base + `table=True`, includes sensitive fields (password_hash)
- **Schema models** (e.g., `UserCreate`, `UserRead`, `UserLogin`): Pydantic models for API validation

Enums are string-based (e.g., `UserStatus`, `ChallengeStatus`, `LibraryVisibility`) stored as strings in DB via `sa_column=Column(String)`.

### Word Import System

`app/scripts/import_words.py` migrates vocabulary from StarDict SQLite format to PostgreSQL:
- Maps collins/oxford/bnc/frq scores to difficulty levels (1-5)
- Extracts tags from word metadata
- Batch inserts for performance (default 10,000 per batch)
- Skips existing words to avoid duplicates
- StarDict schema has 15 fields including phonetic, definition, translation, exchange forms, detail JSON

## Key Implementation Notes

- Always use `uv run` to execute Python commands (project uses UV package manager)
- Database timestamps use `datetime.now(timezone.utc)` for consistency
- All routes are prefixed (e.g., `/api/auth`)
- FastAPI automatic validation via Pydantic models in route parameters
- User progression: earn exp/coins from challenges, unlock higher floors (max_floor)