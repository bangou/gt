## Purpose

Transparent overlay HUD and main window for presenting GTO strategy
recommendations in real time during WePoker play. The HUD floats above
the game without intercepting mouse input; the main window provides
detailed breakdowns.

## Requirements

### Requirement: HUD Overlay Window

The system SHALL render a topmost, transparent, click-through HUD
window using `WS_EX_LAYERED` + `WS_EX_TRANSPARENT` styles.

#### Scenario: HUD visible and click-through

- **WHEN** the HUD is toggled on via hotkey
- **THEN** a semi-transparent window appears above the game, displays
  the recommended action with frequencies, and does not intercept mouse
  clicks.

#### Scenario: HUD hidden

- **WHEN** the user presses the configured toggle hotkey while the HUD
  is visible
- **THEN** the HUD window is hidden (not destroyed — it can be shown
  again).

#### Scenario: Opacity adjustment

- **WHEN** the user moves the opacity slider in configuration
- **THEN** the HUD transparency updates in real time and the new value
  is saved to `config.json`.

### Requirement: HUD Content

The system SHALL display a compact strategy summary on the HUD.

#### Scenario: Strategy available

- **WHEN** a GTO strategy with `confidence: "high"` is returned
- **THEN** the HUD shows the recommended action, main action
  frequencies (e.g. "Fold 15% / Call 21% / Raise 64%"), and a green
  confidence indicator.

#### Scenario: Low-confidence strategy

- **WHEN** `confidence` is `"low"`
- **THEN** the HUD displays a warning icon and the text "Low
  confidence — use with caution".

#### Scenario: No strategy available

- **WHEN** the solver returns `status: "error"`
- **THEN** the HUD displays "No recommendation available".

### Requirement: Main Window

The system SHALL provide a main application window with the full
strategy breakdown.

#### Scenario: Detailed breakdown

- **WHEN** the main window is open and a strategy is available
- **THEN** it displays fold / call / raise percentages, raise-size
  frequencies, equity, and the current game-state summary (hero hand,
  board, pot).

#### Scenario: Range matrix placeholder

- **WHEN** the backend data includes range information
- **THEN** the main window MAY render a 13×13 hand-range heatmap.

### Requirement: Hotkey Toggle

The system SHALL support a configurable global hotkey to show / hide
the HUD.

#### Scenario: Hotkey registered

- **WHEN** the application starts
- **THEN** the configured hotkey (default: Ctrl+Shift+H) is registered
  as a global hotkey that toggles HUD visibility.
