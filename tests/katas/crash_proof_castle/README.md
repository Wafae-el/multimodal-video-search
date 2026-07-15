# Crash-Proof Castle

## Overview

Crash-Proof Castle is the Coding Quest for Week 1 of the Multimodal Video Search project.

The objective is to design a retry-safe state machine capable of handling crashes, retries, and duplicate events while ensuring that processing never produces duplicate final artifacts.

This kata is completed before implementing the production ingestion workflow.

---

## Objectives

This coding quest implements the following requirements:

- Define processing states and events using Python Enums.
- Implement a pure `next_state(state, event)` transition function.
- Compute a deterministic `operation_key` using SHA-256.
- Simulate random event sequences.
- Verify that random executions produce at most one final artifact.

---

## Project Structure

```
crash_proof_castle/
│
├── state_machine.py
├── operation_key.py
├── random_events.py
├── test_state_machine.py
├── test_operation_key.py
├── test_random_events.py
└── README.md
```

---

## Components

### state_machine.py

Defines:

- ProcessingState
- ProcessingEvent
- next_state()

The state machine models upload processing and retry behaviour.

---

### operation_key.py

Implements a deterministic SHA-256 operation key:

```
SHA256(
asset_checksum +
step +
step_version +
model_version
)
```

The operation key guarantees idempotent processing.

---

### random_events.py

Generates random event sequences to simulate:

- upload completion
- worker crashes
- retries
- duplicate deliveries
- existing outputs

The simulation checks that processing never creates more than one final artifact.

---

## Running the Tests

From the project root:

```bash
pytest tests/katas/crash_proof_castle
```

Expected output:

```
10 passed
```

---

## Technologies

- Python 3.12
- pytest
- hashlib
- Enum

---

## Learning Outcomes

This coding quest demonstrates:

- Finite State Machines
- Idempotent processing
- Retry-safe workflow design
- Deterministic hashing
- Unit testing