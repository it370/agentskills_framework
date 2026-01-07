---
name: LogbookVerification
description: Retrieves company's contact information from logbook.
requires:
  - order_details.employer_company_name
produces:
  - is_found_in_logbook
  - company_name
  - verification_method
optional_produces:
  - contacts.phone
  - contacts.email
  - contacts.fax
---

# LogbookVerification

## Purpose
To retrieve from external REST API services (http://localhost:8000/mock/logbook) a list of known company and their preferred mode of contact.
Returns company's known contact options like preferred mode of contact, phone, email and/or faxes if a match is found

## Matching Logic
A company is found to be matching if it satisfies any or all of the below conditions:
- Names matches exactly
- Given name is an abbreviation of logbook's company name
- Treat Pvt Ltd., Org, Inc. as different companies even with similar/same names

## Output Schema (reference)
- company_name: str
- verification_method: str
- is_found_in_logbook: boolean
- contacts.phone: str (Optional)
- contacts.email: str (Optional)
- contacts.fax: str (Optional)

