## Purpose

Real-time poker table analysis via screen capture. Detects game state —
hero's hand, community cards, pot/bet amounts, dealer position, and
action triggers — without any game-process injection. Provides the
observational input layer for the GTO strategy assistant.

## Requirements

### Requirement: Screen Capture

The system SHALL locate and capture the WePoker game window client area
and return a NumPy BGR array for downstream processing.

#### Scenario: Window found and captured

- **WHEN** a window whose title contains "WePoker" is open on the desktop
- **THEN** the system locates its handle, reads the client-area
  dimensions, and captures a screenshot via `BitBlt` into a NumPy BGR
  array matching the client size.

#### Scenario: Window not found

- **WHEN** no WePoker window exists
- **THEN** the system raises a `WindowNotFoundError` with a descriptive
  message.

#### Scenario: Dynamic coordinate scaling

- **WHEN** the window client size differs from the 1920×1080 reference
  resolution
- **THEN** all region coordinates scale proportionally by
  `actual / reference` in both axes.

### Requirement: Capture Source Abstraction

The system SHALL expose a `CaptureSource` abstract base class so
implementations can be swapped.

#### Scenario: Default implementation

- **WHEN** the system starts without a custom source
- **THEN** `WindowCapture` (single-window `BitBlt` capture) is used as
  the default implementation.

#### Scenario: Future extension point

- **WHEN** a developer implements `CaptureSource` for an OBS virtual
  camera or other source
- **THEN** downstream modules continue to work without modification.

### Requirement: Action Trigger Detection

The system SHALL detect when it is the hero's turn to act by checking
for the presence of action buttons (Fold / Call / Raise) on screen.

#### Scenario: Action buttons visible

- **WHEN** the Fold, Call, and Raise buttons are present on the
  captured screen
- **THEN** `is_hero_turn()` returns `True`.

#### Scenario: Action buttons absent

- **WHEN** none of the action buttons are detected
- **THEN** `is_hero_turn()` returns `False`.

#### Scenario: Manual fallback

- **WHEN** template-based detection is not yet calibrated
- **THEN** the user can trigger recognition manually via a configurable
  hotkey.

### Requirement: Dealer Position Recognition

The system SHALL locate the dealer-button marker and compute the hero's
standard position string from the dealer index plus the user-configured
hero seat number.

#### Scenario: Dealer found

- **WHEN** the dealer marker is visible at seat index 3 and the hero
  is at seat index 1
- **THEN** the system computes the hero's position as the correct
  standard string (e.g. UTG / MP / HJ / CO / BTN / SB / BB) for a
  6-max table.

#### Scenario: Dealer not found

- **WHEN** the dealer marker cannot be detected
- **THEN** the system logs a warning and falls back to the last known
  dealer position or prompts for manual input.

### Requirement: Card Recognition

The system SHALL recognise individual playing cards from hero and
community-card regions using template matching with HSV suit
verification and multi-frame voting to achieve zero-error recognition.

#### Scenario: Five-frame consensus achieved

- **WHEN** 5 consecutive frames are captured and ≥3 frames agree on the
  same rank and suit for every card
- **THEN** the system emits the consensus result.

#### Scenario: Consensus not achieved within retries

- **WHEN** 5-frame consensus fails after 3 retry cycles (15 frames
  total)
- **THEN** the system raises a `RecognitionError` alert and prompts the
  user for manual verification.

#### Scenario: Suit colour override

- **WHEN** template matching returns "hearts" but HSV hue analysis
  indicates a black suit
- **THEN** the system trusts the HSV colour result and corrects the
  suit to "spades" or "clubs" as appropriate.

#### Scenario: Calibration mode

- **WHEN** the user enters calibration mode and clicks card corners
- **THEN** the offsets are saved to `config.json` and used for
  subsequent rank/suit sub-region extraction.

### Requirement: Number Recognition

The system SHALL recognise pot-size and bet-amount digits from fixed
screen regions using digit template matching (0–9 + decimal point).

#### Scenario: Integer amount recognised

- **WHEN** the pot region contains the digits "1", "5", "0"
- **THEN** `read_number_region()` returns `150.0`.

#### Scenario: Decimal amount recognised

- **WHEN** the bet region contains "3", ".", "5"
- **THEN** `read_number_region()` returns `3.5`.

#### Scenario: Manual fallback

- **WHEN** template matching fails to recognise the number
- **THEN** the system falls back to a manual input dialog.

### Requirement: Game State Assembly

The system SHALL accept recognised cards, position, and pot/bet amounts
and produce a GTO Query Protocol JSON payload.

#### Scenario: Complete preflop state

- **WHEN** hero hand is Ah Kh, position is BTN, pot is 1.5 BB, and no
  board cards are present
- **THEN** `assemble_game_state()` returns a valid JSON object matching
  the GTO Query Protocol schema defined in the `gto-solver` spec.

#### Scenario: Missing optional fields

- **WHEN** effective stack or action history is not yet determined
- **THEN** those fields are omitted (not set to null or zero) so the
  GTO solver applies its own defaults.
