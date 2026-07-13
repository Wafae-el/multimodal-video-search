# ADR-0001 Project Structure

## Status

Accepted

## Context

The project requires a modular architecture separating the API, workers, reusable packages, infrastructure and tests.

## Decision

Use the following repository layout:

- apps
- workers
- packages
- infrastructure
- migrations
- tests
- docs

## Consequences

The architecture improves modularity, maintainability and scalability.