---
name: DatabaseUserFetcher
description: Fetch user profile data from PostgreSQL database
requires:
  - user_id
produces:
  - user_profile
  - profile_found
executor: action

action:
  type: data_query
  source: postgres
  query: "select id, name, age, sex from testdb_users WHERE id={user_id}" # Removed quotes - id is integer
  credential_ref: "postgres_aiven_cloud_db"  # References credential in secure vault
  timeout: 10.0
---

# DatabaseUserFetcher

## Purpose
Fetch user profile directly from the database using SQL query with secure credentials.
