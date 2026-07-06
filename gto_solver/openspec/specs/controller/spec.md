## Purpose

Orchestrates the full recognition → lookup → display pipeline on a
continuous detection loop. Polls for the hero's turn, runs the analysis
pipeline when triggered, clears the HUD when action is no longer
required, and handles errors gracefully without crashing.

## Requirements

### Requirement: Event Loop

The system SHALL poll for the action trigger at a configurable interval
and run the full pipeline when triggered.

#### Scenario: Trigger fires — pipeline runs

- **WHEN** `is_hero_turn()` returns `True`
- **THEN** the controller executes in order: capture 5 frames →
  recognise cards & numbers → parse game state → query GTO solver →
  update HUD + main window.

#### Scenario: Trigger clears — HUD hides

- **WHEN** `is_hero_turn()` transitions from `True` to `False`
- **THEN** the controller clears the HUD display within 1 second.

#### Scenario: Polling interval

- **WHEN** the controller is running
- **THEN** it checks `is_hero_turn()` at the configured interval
  (default 200 ms, adjustable in `config.json`).

### Requirement: Pipeline Timing

The system SHALL complete the full pipeline quickly enough to be useful
during live play.

#### Scenario: End-to-end latency

- **WHEN** the action trigger fires and all modules respond normally
- **THEN** the HUD updates within 1 second of the initial trigger.

### Requirement: Error Resilience

The system SHALL handle errors at any pipeline stage without crashing
the event loop.

#### Scenario: Recognition failure

- **WHEN** card recognition fails to achieve consensus after all
  retries
- **THEN** the controller logs the error, shows "Recognition uncertain"
  on the HUD, and continues the event loop.

#### Scenario: Solver error

- **WHEN** the GTO solver returns `status: "error"`
- **THEN** the controller logs the error, shows "No recommendation
  available" on the HUD, and continues the event loop.

#### Scenario: Loop survives exception

- **WHEN** an unexpected exception occurs in any pipeline stage
- **THEN** the controller catches it, logs the full traceback, and
  continues polling — the next trigger restarts the pipeline cleanly.

### Requirement: Logging

The system SHALL log all pipeline events for debugging and performance
monitoring.

#### Scenario: Normal pipeline run

- **WHEN** each pipeline stage completes
- **THEN** the controller logs a timestamped record of: trigger time,
  recognition result, parser output, solver query, and HUD update.

#### Scenario: Performance log

- **WHEN** any stage exceeds 500 ms
- **THEN** the controller logs a warning with the stage name and
  duration.
