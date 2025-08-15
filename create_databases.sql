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
