---
name: DemoRestSkill
description: Demonstrates a REST-executed skill that resumes after a callback.
requires: []
produces:
  - mock_result
  - echoed_inputs
executor: rest
rest:
  url: http://localhost:8000/demo/rest-task
  method: POST
  timeout: 5
---

# DemoRestSkill

## Purpose
Show how a skill can dispatch to an external REST API, pause the workflow, and
resume when a callback arrives. This demo endpoint waits ~10 seconds before
invoking the callback with mock data.

## Output Schema (reference)
- mock_result: string
- echoed_inputs: object

