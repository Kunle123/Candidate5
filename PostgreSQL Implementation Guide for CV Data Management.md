# PostgreSQL Implementation Guide for CV Data Management

## Database Setup Instructions

1. **Create the database schema:**

```sql
-- Main CV profile table
CREATE TABLE cv_profiles (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Work experience table with order preservation
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

-- Education table with order preservation
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

-- Skills table
CREATE TABLE skills (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  UNIQUE(cv_profile_id, skill)
);

-- Projects table with order preservation
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  order_index INTEGER NOT NULL,
  UNIQUE(cv_profile_id, order_index)
);

-- Certifications table with order preservation
CREATE TABLE certifications (
  id SERIAL PRIMARY KEY,
  cv_profile_id INTEGER REFERENCES cv_profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  issuer TEXT,
  year TEXT,
  order_index INTEGER NOT NULL,
  UNIQUE(cv_profile_id, order_index)
);

-- Add indexes for better performance
CREATE INDEX idx_work_exp_profile_order ON work_experiences(cv_profile_id, order_index);
CREATE INDEX idx_education_profile_order ON education(cv_profile_id, order_index);
CREATE INDEX idx_projects_profile_order ON projects(cv_profile_id, order_index);
CREATE INDEX idx_certifications_profile_order ON certifications(cv_profile_id, order_index);
```

2. **Create functions for JSON import:**

```sql
-- Function to import CV JSON into database tables
CREATE OR REPLACE FUNCTION import_cv_json(
  p_name TEXT,
  p_email TEXT,
  p_cv_json JSONB
) RETURNS INTEGER AS $$
DECLARE
  v_profile_id INTEGER;
  v_work_exp JSONB;
  v_education JSONB;
  v_skill TEXT;
  v_project JSONB;
  v_cert JSONB;
  v_order INTEGER;
BEGIN
  -- Create profile
  INSERT INTO cv_profiles (name, email)
  VALUES (p_name, p_email)
  RETURNING id INTO v_profile_id;
  
  -- Import work experiences
  v_order := 0;
  FOR v_work_exp IN SELECT * FROM jsonb_array_elements(p_cv_json->'work_experience')
  LOOP
    INSERT INTO work_experiences (
      cv_profile_id, company, title, start_date, end_date, description, order_index
    ) VALUES (
      v_profile_id,
      v_work_exp->>'company',
      v_work_exp->>'title',
      v_work_exp->>'start_date',
      v_work_exp->>'end_date',
      v_work_exp->>'description',
      v_order
    );
    v_order := v_order + 1;
  END LOOP;
  
  -- Import education (similar pattern)
  v_order := 0;
  FOR v_education IN SELECT * FROM jsonb_array_elements(p_cv_json->'education')
  LOOP
    INSERT INTO education (
      cv_profile_id, institution, degree, field, start_date, end_date, description, order_index
    ) VALUES (
      v_profile_id,
      v_education->>'institution',
      v_education->>'degree',
      v_education->>'field',
      v_education->>'start_date',
      v_education->>'end_date',
      v_education->>'description',
      v_order
    );
    v_order := v_order + 1;
  END LOOP;
  
  -- Import skills
  FOR v_skill IN SELECT * FROM jsonb_array_elements_text(p_cv_json->'skills')
  LOOP
    INSERT INTO skills (cv_profile_id, skill)
    VALUES (v_profile_id, v_skill)
    ON CONFLICT (cv_profile_id, skill) DO NOTHING;
  END LOOP;
  
  -- Import projects
  v_order := 0;
  FOR v_project IN SELECT * FROM jsonb_array_elements(p_cv_json->'projects')
  LOOP
    INSERT INTO projects (
      cv_profile_id, name, description, order_index
    ) VALUES (
      v_profile_id,
      v_project->>'name',
      v_project->>'description',
      v_order
    );
    v_order := v_order + 1;
  END LOOP;
  
  -- Import certifications
  v_order := 0;
  FOR v_cert IN SELECT * FROM jsonb_array_elements(p_cv_json->'certifications')
  LOOP
    INSERT INTO certifications (
      cv_profile_id, name, issuer, year, order_index
    ) VALUES (
      v_profile_id,
      v_cert->>'name',
      v_cert->>'issuer',
      v_cert->>'year',
      v_order
    );
    v_order := v_order + 1;
  END LOOP;
  
  RETURN v_profile_id;
END;
$$ LANGUAGE plpgsql;
```

3. **Create function to export to JSON:**

```sql
-- Function to export CV data back to JSON
CREATE OR REPLACE FUNCTION export_cv_to_json(p_profile_id INTEGER) 
RETURNS JSONB AS $$
DECLARE
  v_result JSONB;
BEGIN
  SELECT jsonb_build_object(
    'work_experience', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'id', id,
          'company', company,
          'title', title,
          'start_date', start_date,
          'end_date', end_date,
          'description', description
        ) ORDER BY order_index
      )
      FROM work_experiences
      WHERE cv_profile_id = p_profile_id
    ),
    'education', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'id', id,
          'institution', institution,
          'degree', degree,
          'field', field,
          'start_date', start_date,
          'end_date', end_date,
          'description', description
        ) ORDER BY order_index
      )
      FROM education
      WHERE cv_profile_id = p_profile_id
    ),
    'skills', (
      SELECT jsonb_agg(skill)
      FROM skills
      WHERE cv_profile_id = p_profile_id
    ),
    'projects', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'id', id,
          'name', name,
          'description', description
        ) ORDER BY order_index
      )
      FROM projects
      WHERE cv_profile_id = p_profile_id
    ),
    'certifications', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'id', id,
          'name', name,
          'issuer', issuer,
          'year', year
        ) ORDER BY order_index
      )
      FROM certifications
      WHERE cv_profile_id = p_profile_id
    )
  ) INTO v_result;
  
  RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

## Handling Duplicates

To handle duplicates when importing multiple CVs:

1. **Create a duplicate detection function:**

```sql
CREATE OR REPLACE FUNCTION detect_duplicate_profile(
  p_name TEXT,
  p_email TEXT,
  p_similarity_threshold FLOAT DEFAULT 0.8
) RETURNS TABLE (
  profile_id INTEGER,
  similarity FLOAT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    cp.id,
    CASE
      WHEN p_email IS NOT NULL AND cp.email IS NOT NULL AND cp.email = p_email THEN 1.0
      ELSE similarity(cp.name, p_name)
    END AS sim
  FROM cv_profiles cp
  WHERE 
    (p_email IS NOT NULL AND cp.email = p_email)
    OR
    (similarity(cp.name, p_name) > p_similarity_threshold)
  ORDER BY sim DESC;
END;
$$ LANGUAGE plpgsql;
```

2. **Create a merge function for combining profiles:**

```sql
CREATE OR REPLACE FUNCTION merge_profiles(
  p_source_id INTEGER,
  p_target_id INTEGER,
  p_keep_source BOOLEAN DEFAULT FALSE
) RETURNS VOID AS $$
BEGIN
  -- Transfer work experiences
  UPDATE work_experiences
  SET cv_profile_id = p_target_id,
      order_index = order_index + (SELECT COALESCE(MAX(order_index), -1) + 1 FROM work_experiences WHERE cv_profile_id = p_target_id)
  WHERE cv_profile_id = p_source_id;
  
  -- Transfer education
  UPDATE education
  SET cv_profile_id = p_target_id,
      order_index = order_index + (SELECT COALESCE(MAX(order_index), -1) + 1 FROM education WHERE cv_profile_id = p_target_id)
  WHERE cv_profile_id = p_source_id;
  
  -- Transfer skills (with duplicate handling)
  INSERT INTO skills (cv_profile_id, skill)
  SELECT p_target_id, skill
  FROM skills
  WHERE cv_profile_id = p_source_id
  ON CONFLICT (cv_profile_id, skill) DO NOTHING;
  
  -- Transfer projects
  UPDATE projects
  SET cv_profile_id = p_target_id,
      order_index = order_index + (SELECT COALESCE(MAX(order_index), -1) + 1 FROM projects WHERE cv_profile_id = p_target_id)
  WHERE cv_profile_id = p_source_id;
  
  -- Transfer certifications
  UPDATE certifications
  SET cv_profile_id = p_target_id,
      order_index = order_index + (SELECT COALESCE(MAX(order_index), -1) + 1 FROM certifications WHERE cv_profile_id = p_target_id)
  WHERE cv_profile_id = p_source_id;
  
  -- Delete source profile if not keeping it
  IF NOT p_keep_source THEN
    DELETE FROM cv_profiles WHERE id = p_source_id;
  END IF;
END;
$$ LANGUAGE plpgsql;
```

## Editing Entries

For editing entries while preserving order:

1. **Update a work experience entry:**

```sql
-- Example: Update a work experience entry
UPDATE work_experiences
SET 
  company = 'New Company Name',
  title = 'Updated Title',
  description = 'Updated description'
WHERE id = 123;  -- specific entry ID
```

2. **Change the order of entries:**

```sql
-- Function to reorder entries
CREATE OR REPLACE FUNCTION reorder_entries(
  p_table_name TEXT,
  p_profile_id INTEGER,
  p_entry_id INTEGER,
  p_new_position INTEGER
) RETURNS VOID AS $$
DECLARE
  v_current_pos INTEGER;
  v_sql TEXT;
BEGIN
  -- Get current position
  EXECUTE format('
    SELECT order_index 
    FROM %I 
    WHERE id = $1 AND cv_profile_id = $2', p_table_name)
    INTO v_current_pos
    USING p_entry_id, p_profile_id;
  
  IF v_current_pos IS NULL THEN
    RAISE EXCEPTION 'Entry not found';
  END IF;
  
  -- Move entries to make space
  IF v_current_pos < p_new_position THEN
    -- Moving down: shift entries in between up
    EXECUTE format('
      UPDATE %I
      SET order_index = order_index - 1
      WHERE cv_profile_id = $1
        AND order_index > $2
        AND order_index <= $3', p_table_name)
      USING p_profile_id, v_current_pos, p_new_position;
  ELSE
    -- Moving up: shift entries in between down
    EXECUTE format('
      UPDATE %I
      SET order_index = order_index + 1
      WHERE cv_profile_id = $1
        AND order_index >= $2
        AND order_index < $3', p_table_name)
      USING p_profile_id, p_new_position, v_current_pos;
  END IF;
  
  -- Set new position
  EXECUTE format('
    UPDATE %I
    SET order_index = $1
    WHERE id = $2', p_table_name)
    USING p_new_position, p_entry_id;
END;
$$ LANGUAGE plpgsql;
```

## Recommended Changes to Your Setup

1. **Add a PostgreSQL extension for text similarity:**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

2. **Add versioning for tracking changes:**
```sql
-- Add version tracking to cv_profiles
ALTER TABLE cv_profiles ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE cv_profiles ADD COLUMN last_modified_by TEXT;

-- Create a trigger to increment version on update
CREATE OR REPLACE FUNCTION update_cv_version()
RETURNS TRIGGER AS $$
BEGIN
  NEW.version = OLD.version + 1;
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER cv_version_trigger
BEFORE UPDATE ON cv_profiles
FOR EACH ROW
EXECUTE FUNCTION update_cv_version();
```

3. **Create a simple API layer** for your application to interact with these functions, which will make it easier for your team to use this database structure without writing complex SQL.
