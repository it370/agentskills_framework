16 Jan 2026
Changes:
Nelvin's Note


# Node Produces list and Key mappings
This doc defines how output mapping is performed in Data Pipeline

```
Produces List: [] Empty
Pipeline Results: {a,b,c,d,e,f}
Final Output: {a,b,c,d,e,f}

Produces List: [a]
Pipeline Results: [d,a,b,c]
Final Output: {a}

Produces List: [a]
Pipeline Results: [b,c,d]
Final Output: Missing: Error, failes

Produces List: [a,b]
Pipeline Results: [a,b,c,d]
Final Output: {a, b}

Produces List: [a]
Pipeline Results: a
Final Output: {a}

```
- The overall idea is if produces is left empty, all results of pipeline steps are returned to state.
- If produces is defined, then an exact match is returned.
- If any missing expected keys arises, program stops there.