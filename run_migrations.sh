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
