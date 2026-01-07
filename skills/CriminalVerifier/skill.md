---
name: CriminalVerifier
description: Checks criminal records given full name and date of birth; HITL required.
requires:
  - full_name
  - dob
produces:
  - criminal_status
  - risk_score
hitl_enabled: true
---

# CriminalVerifier

## Purpose
Query background data sources to assess criminal record status and risk.

## Output Schema (reference)
- criminal_status: string
- risk_score: number

