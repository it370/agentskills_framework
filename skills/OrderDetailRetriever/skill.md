---
name: OrderDetailRetriever
description: Entry point for processing an Order, Retrieves Order Details, performs initial screening and returns findings and data for further processing. 
requires: 
  - order_number
produces:
  - order_details
# executor: rest
# rest:
#   url: http://localhost:8000/mock/orders/{order_number}
#   method: GET
#   timeout: 5
---

# OrderDetailRetriever

## Purpose
Fetches an order detail from external REST API using the order number provided.
use the url http://localhost:8000/mock/orders/{order_number}

## Output Schema (reference)
- order_details: Object

