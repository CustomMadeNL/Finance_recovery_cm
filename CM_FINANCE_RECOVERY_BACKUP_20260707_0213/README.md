# CM Finance Recovery Engine

AI-assisted Moneybird recovery tool for processing historical incoming documents, supplier matching, VAT classification, ledger suggestions and future bank matching.

## Current status
- Moneybird API connected
- 1,438 documents imported from export
- Dashboard v0.1 working
- Contact sync working
- Prototype matcher working

## Core principles
- Read-only first
- No automatic write-back without confidence threshold
- No fuzzy-only automatic booking
- Full audit trail
- Batch processing before full automation

## Modules
- Analyzer
- Vendor Engine
- Ledger Engine
- VAT Engine
- Confidence Engine
- Moneybird Client
- Dashboard