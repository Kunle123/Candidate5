# Alembic Migration Configuration Fix Guide

## Problem Summary

Your project had several critical issues with Alembic migration configurations that were causing cross-database references and migration failures:

### Issues Identified:

1. **Root Migration Misconfiguration (CRITICAL)**
   - The root `migrations/env.py` was importing CV service models but connecting to the Arc database
   - This caused migrations to try to create CV tables in the Arc database
   - Database URL was hardcoded to `arc_db` regardless of which models were being used

2. **AI Service Unnecessary Configuration**
   - AI service had Alembic configuration but no database models
   - This service is stateless and doesn't need database migrations
   - The configuration was incomplete with `target_metadata = None`

3. **Database URL Conflicts**
   - All services were using the same `DATABASE_URL` environment variable
   - This meant all services would connect to the same database
   - No separation between different service databases

## Solution Overview

The fix involves:

1. **Removing problematic configurations**
   - Remove root-level migration configuration
   - Remove AI service migration configuration (not needed)

2. **Fixing service-specific configurations**
   - Update each service to use its own database URL
   - Ensure proper model imports for each service
   - Add fallback logic with warnings

3. **Creating proper database separation**
   - Each service gets its own database
   - Dedicated environment variables for each service

## Project Structure After Fix

```
Candidate5/
├── apps/
│   ├── ai/ai_service/           # No migrations (stateless)
│   ├── arc/arc_service/         # Arc database migrations
│   │   ├── migrations/env.py    # ✅ Fixed: Uses ARC_DATABASE_URL
│   │   └── alembic.ini
│   ├── cvs/cv_service/          # CV database migrations  
│   │   ├── migrations/env.py    # ✅ Fixed: Uses CV_DATABASE_URL
│   │   └── alembic.ini
│   └── user_service/            # User database migrations
│       ├── migrations/env.py    # ✅ Fixed: Uses USER_DATABASE_URL
│       └── alembic.ini
├── migrations/                  # ❌ REMOVED (was problematic)
├── alembic.ini                  # ❌ REMOVED (was problematic)
└── fix_alembic_migrations.sh    # ✅ Fix script
```

## Database Architecture

Each service now manages its own database:

| Service | Database | Models | Purpose |
|---------|----------|--------|---------|
| **Arc Service** | `arc_db` | UserArcData, CVTask, WorkExperience | User career data and CV processing tasks |
| **CV Service** | `cv_db` | CV, Experience, Education, Skills, etc. | CV document management |
| **User Service** | `user_db` | UserProfile, TopupCredits | User accounts and billing |
| **AI Service** | None | None | Stateless AI processing |

## Environment Variables

Set these environment variables for proper database separation:

```bash
# Arc Service Database
ARC_DATABASE_URL=postgresql://username:password@localhost:5432/arc_db

# CV Service Database  
CV_DATABASE_URL=postgresql://username:password@localhost:5432/cv_db

# User Service Database
USER_DATABASE_URL=postgresql://username:password@localhost:5432/user_db

# Fallback (will show warnings if used)
DATABASE_URL=postgresql://username:password@localhost:5432/default_db
```

## How to Apply the Fix

1. **Run the fix script:**
   ```bash
   ./fix_alembic_migrations.sh
   ```

2. **Set up environment variables:**
   - Copy `.env.template` to `.env`
   - Update with your actual database credentials

3. **Create the databases:**
   ```bash
   psql -U postgres -f create_databases.sql
   ```

4. **Run migrations:**
   ```bash
   ./run_migrations.sh
   ```

## What the Fix Script Does

1. **Creates backups** of existing migration configurations
2. **Removes problematic configurations:**
   - Root-level migrations directory and alembic.ini
   - AI service migrations directory and alembic.ini
3. **Updates service env.py files** with proper database URL logic
4. **Creates helper scripts** for database setup and migrations
5. **Generates templates** for environment variables

## Migration Commands Per Service

After the fix, run migrations from each service directory:

```bash
# Arc Service
cd apps/arc/arc_service
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# CV Service
cd apps/cvs/cv_service  
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# User Service
cd apps/user_service
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

Or use the provided helper script:
```bash
./run_migrations.sh
```

## Key Improvements

1. **Database Separation**: Each service has its own database
2. **Proper Model Imports**: Each env.py imports only its own models
3. **Flexible Configuration**: Supports service-specific and fallback URLs
4. **Warning System**: Alerts when using fallback configurations
5. **Clean Architecture**: Removed unnecessary configurations

## Troubleshooting

### If you see "WARNING: Using generic DATABASE_URL"
- Set the service-specific environment variable (e.g., `ARC_DATABASE_URL`)

### If migrations fail with "table already exists"
- Check if tables were created in the wrong database
- Drop and recreate databases if needed
- Ensure each service connects to its own database

### If you need to rollback
- Backups are in the `migration_backups/` directory
- Restore from backups if needed

## Testing the Fix

1. **Verify database connections:**
   ```bash
   # Test each service can connect to its database
   cd apps/arc/arc_service && alembic current
   cd apps/cvs/cv_service && alembic current  
   cd apps/user_service && alembic current
   ```

2. **Generate test migrations:**
   ```bash
   # Should create migrations only for relevant models
   cd apps/arc/arc_service && alembic revision --autogenerate -m "test"
   ```

3. **Check migration files:**
   - Arc migrations should only contain Arc-related tables
   - CV migrations should only contain CV-related tables
   - User migrations should only contain User-related tables

The fix ensures each service manages only its own database schema, preventing the cross-database issues you were experiencing.

