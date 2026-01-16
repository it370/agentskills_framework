---
name: CandidateDataEnricher
description: Multi-source data pipeline to enrich candidate profile
requires:
  - candidate_id
produces:
  - enriched_profile
  - data_sources_count
  - enrichment_timestamp
executor: action

action:
  type: data_pipeline
  timeout: 30.0
  steps:
    - type: query
      source: postgres
      query: "SELECT * FROM candidates WHERE id = {candidate_id}"
      output: candidate_base
    
    - type: query
      source: mongodb
      collection: candidate_documents
      filter:
        candidate_id: "{candidate_id}"
      output: documents
    
    - type: query
      source: mongodb
      collection: verification_results
      filter:
        candidate_id: "{candidate_id}"
      output: verifications
    
    - type: merge
      inputs:
        - candidate_base
        - documents
        - verifications
      output: enriched_profile
---

# CandidateDataEnricher

## Purpose
Demonstrate a multi-step data pipeline that:
1. Fetches base candidate data from PostgreSQL
2. Retrieves related documents from MongoDB
3. Gets verification results from MongoDB
4. Merges everything into a unified profile

This showcases the `data_pipeline` action type for complex data operations.

## Pipeline Steps

### Step 1: Query Candidate Base Data
- **Source**: PostgreSQL
- **Table**: `candidates`
- **Output**: `candidate_base`

### Step 2: Query Documents
- **Source**: MongoDB
- **Collection**: `candidate_documents`
- **Filter**: By candidate_id
- **Output**: `documents`

### Step 3: Query Verifications
- **Source**: MongoDB
- **Collection**: `verification_results`
- **Filter**: By candidate_id
- **Output**: `verifications`

### Step 4: Merge Results
- **Type**: merge
- **Inputs**: All previous outputs
- **Output**: `enriched_profile`

## Output Schema
- `enriched_profile`: Unified candidate profile with all data
- `data_sources_count`: Number of data sources accessed (3)
- `enrichment_timestamp`: ISO timestamp of enrichment

## Benefits
- Single atomic operation
- Automatic error handling per step
- Guaranteed execution order
- No LLM cost
