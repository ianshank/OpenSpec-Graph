# Spec delta — Demo capability

## ADDED Requirements

### Requirement: the writer SHALL attest every write

Prose obligation.

#### Scenario: attested writes record an evidence id

- **GIVEN** an attested writer
- **WHEN** `make regression` runs the suite
- **THEN** an evidence id is recorded

#### Scenario: an unattested write is caught before merge

- **GIVEN** a writer with no attestation
- **WHEN** the suite runs
- **THEN** the check fails and names the offending file
