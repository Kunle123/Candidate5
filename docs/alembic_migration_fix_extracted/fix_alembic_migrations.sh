#!/bin/bash

echo "🔧 Fixing Alembic Migration Configuration Issues"
echo "================================================"

# Create backup directory
echo "📁 Creating backup directory..."
mkdir -p migration_backups
cp -r migrations migration_backups/root_migrations_backup_$(date +%Y%m%d_%H%M%S)
cp -r apps/ai/ai_service/migrations migration_backups/ai_service_migrations_backup_$(date +%Y%m%d_%H%M%S)

echo "✅ Backups created in migration_backups/"

# 1. Remove problematic root migration configuration
echo "🗑️  Removing problematic root migration configuration..."
rm -rf migrations/
rm -f alembic.ini

echo "✅ Root migration configuration removed"

# 2. Remove AI service migration configuration (not needed)
echo "🗑️  Removing AI service migration configuration (stateless service)..."
rm -rf apps/ai/ai_service/migrations/
rm -f apps/ai/ai_service/alembic.ini

echo "✅ AI service migration configuration removed"

# 3. Apply fixed env.py files to each service
echo "🔄 Applying corrected env.py configurations..."

# Arc service
cp fixed_arc_service_env.py apps/arc/arc_service/migrations/env.py
echo "✅ Arc service env.py updated"

# CV service  
cp fixed_cv_service_env.py apps/cvs/cv_service/migrations/env.py
echo "✅ CV service env.py updated"

# User service
cp fixed_user_service_env.py apps/user_service/migrations/env.py
echo "✅ User service env.py updated"

# 4. Create environment variable template
echo "📝 Creating environment variable template..."
cat > .env.template << 'EOF'
# Database URLs for each service
# Replace with your actual database credentials and hosts

# Arc Service Database (manages user arc data, CV tasks, work experience)
ARC_DATABASE_URL=postgresql://username:password@localhost:5432/arc_db

# CV Service Database (manages CV documents and related data)  
CV_DATABASE_URL=postgresql://username:password@localhost:5432/cv_db

# User Service Database (manages user profiles and credits)
USER_DATABASE_URL=postgresql://username:password@localhost:5432/user_db

# Fallback database URL (will show warnings if used)
DATABASE_URL=postgresql://username:password@localhost:5432/default_db
EOF

echo "✅ Environment variable template created (.env.template)"

# 5. Create migration helper script
echo "📝 Creating migration helper script..."
cat > run_migrations.sh << 'EOF'
#!/bin/bash

echo "🚀 Running Alembic Migrations for All Services"
echo "=============================================="

# Function to run migration for a service
run_service_migration() {
    local service_name=$1
    local service_path=$2
    
    echo "📦 Processing $service_name..."
    cd "$service_path"
    
    # Check if alembic is initialized
    if [ ! -d "migrations/versions" ]; then
        echo "   Creating initial migration for $service_name..."
        alembic revision --autogenerate -m "Initial migration for $service_name"
    fi
    
    echo "   Running migrations for $service_name..."
    alembic upgrade head
    
    cd - > /dev/null
    echo "✅ $service_name migrations completed"
    echo ""
}

# Run migrations for each service
run_service_migration "Arc Service" "apps/arc/arc_service"
run_service_migration "CV Service" "apps/cvs/cv_service"  
run_service_migration "User Service" "apps/user_service"

echo "🎉 All migrations completed successfully!"
EOF

chmod +x run_migrations.sh
echo "✅ Migration helper script created (run_migrations.sh)"

# 6. Create database creation script
echo "📝 Creating database creation script..."
cat > create_databases.sql << 'EOF'
-- Create databases for each service
-- Run this script as a PostgreSQL superuser

CREATE DATABASE arc_db;
CREATE DATABASE cv_db;
CREATE DATABASE user_db;

-- Optional: Create dedicated users for each service
-- CREATE USER arc_user WITH PASSWORD 'your_password';
-- CREATE USER cv_user WITH PASSWORD 'your_password';
-- CREATE USER user_service_user WITH PASSWORD 'your_password';

-- GRANT ALL PRIVILEGES ON DATABASE arc_db TO arc_user;
-- GRANT ALL PRIVILEGES ON DATABASE cv_db TO cv_user;
-- GRANT ALL PRIVILEGES ON DATABASE user_db TO user_service_user;
EOF

echo "✅ Database creation script created (create_databases.sql)"

# Clean up temporary files
rm -f fixed_arc_service_env.py fixed_cv_service_env.py fixed_user_service_env.py

echo ""
echo "🎉 Alembic Migration Fix Complete!"
echo "=================================="
echo ""
echo "Next Steps:"
echo "1. Set up your environment variables using .env.template as a guide"
echo "2. Create the databases using create_databases.sql"
echo "3. Run ./run_migrations.sh to initialize and run all migrations"
echo ""
echo "Each service now has its own properly configured Alembic setup:"
echo "- Arc Service: apps/arc/arc_service/ (uses ARC_DATABASE_URL)"
echo "- CV Service: apps/cvs/cv_service/ (uses CV_DATABASE_URL)"
echo "- User Service: apps/user_service/ (uses USER_DATABASE_URL)"
echo ""
echo "The problematic root migration and AI service migration have been removed."

