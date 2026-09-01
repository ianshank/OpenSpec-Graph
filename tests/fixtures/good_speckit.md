# Feature Specification: Demo Capability

**Feature Branch**: `001-demo-capability`
**Created**: 2026-01-01
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - Attest every write (Priority: P1)

A user's write is attested so it can be verified later.

**Why this priority**: Core guarantee the feature exists for.

**Acceptance Scenarios**:

1. **Given** an attested writer, **When** a write occurs, **Then** an evidence id is recorded.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST attest every write.
- **FR-002**: The system MUST record an evidence id for every attested write.

## Success Criteria

- **SC-001**: 95% of writes are attested within 1 second.
