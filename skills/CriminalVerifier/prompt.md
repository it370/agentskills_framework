Produce the following outputs based on the provided inputs:
- criminal_status: "clear" or "record_found".
- risk_score: number between 0 and 100.
- scoresheet.risk.final_score: same numeric value as risk_score.

Keep any reasoning internal; return only the fields.
Given a full name and date of birth, check for criminal records. Return a concise criminal_status string and a numeric risk_score (0-100). If no records are found, use a low risk score.

