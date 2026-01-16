---
name: ParallelPipelineDemo
description: |
  Demonstrates parallel execution in data pipelines.
  Shows how to run multiple independent steps (queries, transforms, skills) 
  concurrently for optimal performance.

requires:
  - company_id
  - date_range

produces:
  - analytics_report

executor: action

action:
  type: data_pipeline
  steps:
    # PARALLEL BLOCK 1: Fetch data from multiple sources simultaneously
    - type: parallel
      name: fetch_all_data_sources
      steps:
        # Query 1: Sales data
        - type: query
          name: fetch_sales
          source: postgres
          credential_ref: postgres_aiven_cloud_db
          query: "SELECT * FROM sales WHERE company_id = {company_id} AND date >= {date_range}"
          output: sales_data
        
        # Query 2: Customer data (runs concurrently with Query 1!)
        - type: query
          name: fetch_customers
          source: postgres
          credential_ref: postgres_aiven_cloud_db
          query: "SELECT * FROM customers WHERE company_id = {company_id}"
          output: customer_data
        
        # Query 3: Inventory data (runs concurrently with Query 1 & 2!)
        - type: query
          name: fetch_inventory
          source: postgres
          credential_ref: postgres_aiven_cloud_db
          query: "SELECT * FROM inventory WHERE company_id = {company_id}"
          output: inventory_data
    
    # All 3 queries complete in MAX(query1_time, query2_time, query3_time)!
    # Outputs are auto-merged: sales_data, customer_data, inventory_data are all available
    
    # PARALLEL BLOCK 2: Process different datasets independently
    - type: parallel
      name: process_datasets
      steps:
        # Transform 1: Analyze sales trends
        - type: transform
          name: analyze_sales
          function: analyze_sales_trends
          inputs: [sales_data]
          output: sales_analysis
        
        # Transform 2: Segment customers (runs concurrently!)
        - type: transform
          name: segment_customers
          function: segment_customer_base
          inputs: [customer_data]
          output: customer_segments
        
        # Skill: AI-powered inventory forecast (runs concurrently!)
        - type: skill
          name: forecast_inventory
          skill: InventoryForecaster
          inputs: [inventory_data]
          # Produces: inventory_forecast (auto-merged to context)
    
    # PARALLEL BLOCK 3: Generate reports for different departments
    - type: parallel
      name: generate_reports
      steps:
        # Report 1: Sales report
        - type: transform
          name: create_sales_report
          function: format_sales_report
          inputs: [sales_analysis, customer_segments]
          output: sales_report
        
        # Report 2: Inventory report (runs concurrently!)
        - type: transform
          name: create_inventory_report
          function: format_inventory_report
          inputs: [inventory_forecast, sales_analysis]
          output: inventory_report
    
    # Final step: Combine all reports into one master analytics report
    - type: transform
      name: combine_reports
      function: create_master_report
      inputs: [sales_report, inventory_report]
      output: analytics_report

---

# Parallel Pipeline Demo

This skill demonstrates the power of **parallel execution** in data pipelines.

## Performance Comparison

### Sequential Execution (OLD):
```
Step 1: Query Sales       → 500ms
Step 2: Query Customers   → 400ms  
Step 3: Query Inventory   → 600ms
Step 4: Transform Sales   → 200ms
Step 5: Transform Customers → 150ms
Step 6: Skill Forecast    → 1000ms
Step 7: Report 1          → 100ms
Step 8: Report 2          → 100ms
Total: 3,050ms (3.05 seconds)
```

### Parallel Execution (NEW):
```
Parallel Block 1 (3 queries):        MAX(500, 400, 600) = 600ms
Parallel Block 2 (2 transforms + skill): MAX(200, 150, 1000) = 1000ms  
Parallel Block 3 (2 reports):        MAX(100, 100) = 100ms
Total: 1,700ms (1.7 seconds) → 44% faster! 🚀
```

## How It Works

1. **Automatic Merging**: All outputs from parallel steps are automatically merged into the context at the top level. No need for explicit `merge` steps!

2. **Any Step Type**: You can run **any** step type in parallel:
   - `query` - Database queries
   - `transform` - Python functions
   - `skill` - LLM/Action/REST skills
   - Even nested `parallel` blocks!

3. **Dependency Management**: The pipeline ensures steps only run when their inputs are available. Parallel blocks wait for all sub-steps to complete before continuing.

## Usage Example

```yaml
steps:
  - type: parallel
    name: my_parallel_block
    steps:
      - type: query
        name: query1
        source: postgres
        query: "SELECT ..."
        output: data1
      
      - type: skill
        name: analysis
        skill: MyAnalyzer
        inputs: [some_input]
        # Outputs are auto-merged
      
      - type: transform
        name: compute
        function: my_function
        inputs: [other_input]
        output: result1
  
  # After parallel block, all outputs are available:
  # data1, result1, and any outputs from MyAnalyzer skill
```

## Best Practices

1. **Group Independent Operations**: Only parallelize steps that don't depend on each other
2. **Database Limits**: Be mindful of connection pool limits when running many concurrent queries
3. **Error Handling**: If any parallel step fails, the entire parallel block fails
4. **Logging**: Check logs for parallel execution timing to verify performance gains

## Key Benefits

✅ **50%+ faster** for I/O-bound operations (database queries, API calls)  
✅ **Works with all step types** (query, transform, skill, merge)  
✅ **Auto-merging** - No manual merge steps needed  
✅ **Clean syntax** - Just nest steps inside `type: parallel`  
✅ **Performance logs** - Shows actual time saved in logs
