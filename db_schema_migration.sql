-- Career Ark PostgreSQL Normalized Schema Migration Script

-- 1. Main CV profile table
CREATE TABLE cv_profiles (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE, -- Link to app user
  name TEXT NOT NULL,
  email TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Work experience table with order preservation
CREATE TABLE work_experiences (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  description TEXT,
  order_index INTEGER NOT NULL,
  UNIQUE(cv_profile_id, order_index)
);

-- 3. Education table with order preservation
CREATE TABLE education (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  institution TEXT NOT NULL,
  degree TEXT NOT NULL,
  field TEXT,
  start_date TEXT,
  end_date TEXT,
  description TEXT,
  order_index INTEGER NOT NULL,
  UNIQUE(cv_profile_id, order_index)
);

-- 4. Skills table
CREATE TABLE skills (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  UNIQUE(cv_profile_id, skill)
);

-- 5. Projects table with order preservation
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  order_index INTEGER NOT NULL,
  UNIQUE(cv_profile_id, order_index)
);

-- 6. Certifications table with order preservation
CREATE TABLE certifications (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  issuer TEXT,
  year TEXT,
  order_index INTEGER NOT NULL,
  UNIQUE(cv_profile_id, order_index)
);

-- 7. Indexes for performance
CREATE INDEX idx_work_exp_profile_order ON work_experiences(cv_profile_id, order_index);
CREATE INDEX idx_education_profile_order ON education(cv_profile_id, order_index);
CREATE INDEX idx_projects_profile_order ON projects(cv_profile_id, order_index);
CREATE INDEX idx_certifications_profile_order ON certifications(cv_profile_id, order_index); 