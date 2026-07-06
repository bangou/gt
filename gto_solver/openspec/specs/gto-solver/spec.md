## Purpose

Offline Game-Theory-Optimal strategy lookup. Given a poker game-state
JSON, returns a mixed-strategy recommendation with action frequencies
and confidence metadata. All queries run against a local SQLite
database — no network access required.

## Requirements

### Requirement: GTO Query Protocol Input

The system SHALL accept a JSON string conforming to the GTO Query
Protocol schema and return a JSON string conforming to the GTO Response
Protocol schema via `get_gto_strategy(json_str)`.

#### Scenario: Valid preflop query

- **WHEN** the input JSON describes BTN RFI with AKs at a 6-max 100 BB
  table (no board, no action history)
- **THEN** the system returns a response with `status: "success"` and
  action probabilities (fold / call / raise) summing to 100 %.

#### Scenario: Optional fields omitted

- **WHEN** `effective_stack_bb`, `board`, and `actions_history` are
  absent from the input JSON
- **THEN** the system applies safe defaults (100 BB, empty board, empty
  history) and returns a valid strategy response without treating the
  omission as an error.

#### Scenario: Malformed input JSON

- **WHEN** the input is not valid JSON
- **THEN** the system returns `status: "error"` with a descriptive
  message.

#### Scenario: Unsupported scenario

- **WHEN** the query describes a scenario with no matching data in the
  database and fuzzy matching also fails
- **THEN** the system returns a conservative default strategy
  (heavily weighted toward fold / check) with `confidence: "low"`.

#### Scenario: Postflop query

- **WHEN** the input includes a non-empty board and postflop action
  history
- **THEN** the system attempts fuzzy matching if exact lookup fails,
  and returns the best available strategy with the appropriate
  `confidence` level.

### Requirement: Response Protocol

The system SHALL return responses that natively express all poker
actions (check, bet, fold, call, raise) and include a confidence
indicator.

#### Scenario: Action types in response

- **WHEN** the current street context requires a check or bet decision
- **THEN** the response includes `check` and `bet` as valid action
  types with their probability percentages, not only fold / call /
  raise.

#### Scenario: High confidence match

- **WHEN** the database contains an exact row for the queried hand,
  position, stack depth, street, board texture, and action history
- **THEN** `confidence` is `"high"`.

#### Scenario: Medium confidence match

- **WHEN** the query matches after relaxing action history or board
  texture constraints
- **THEN** `confidence` is `"medium"`.

#### Scenario: Low confidence fallback

- **WHEN** no match is found even after fuzzy relaxation
- **THEN** `confidence` is `"low"` and the returned strategy is a
  conservative default (prefer fold / check).

### Requirement: Storage Schema

The system SHALL store strategy probabilities in a local SQLite
database with a composite unique key.

#### Scenario: Insert or replace

- **WHEN** a new CSV row is imported for a specific
  (table_size, position, effective_stack_bb, street, hand_key,
  board_texture_key, action_history_key) combination
- **THEN** the row is inserted; if the key already exists it is
  replaced.

#### Scenario: Probability integrity

- **WHEN** rows for the same scenario are loaded
- **THEN** the sum of probabilities across all actions for that
  scenario equals 100.

### Requirement: Data Coverage — Preflop

The system SHALL cover preflop 6-max 100 BB strategy for all standard
positions and common preflop situations.

#### Scenario: RFI lookup

- **WHEN** the hero is first to act (RFI) at any 6-max position
- **THEN** a strategy with `confidence: "high"` is returned for every
  hand in the 169-hand simplified range.

#### Scenario: vs RFI lookup

- **WHEN** the hero faces an open-raise from a known position
- **THEN** a strategy is returned for the hero's calling / 3-betting /
  folding decision.

#### Scenario: Blind defence

- **WHEN** the hero is in BB facing a BTN open
- **THEN** a defence strategy is returned.

### Requirement: Data Coverage — Postflop

The system SHALL cover common postflop textures and single-raised-pot
scenarios where data exists, and SHALL fall back to heuristics when
data is absent.

#### Scenario: Common texture available

- **WHEN** the board texture matches a known category (e.g. dry,
  wet, paired) in the database
- **THEN** a postflop strategy is returned.

#### Scenario: Texture not in database

- **WHEN** the board texture is not found
- **THEN** the system falls back to a heuristic strategy based on
  hand strength categories.
