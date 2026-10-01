# UI Audit (Milestone 20)

Findings from auditing the product before the v1.0 release candidate. Kept as
the record of what was wrong and what was decided, so later work does not
re-litigate it.

## Measured inconsistencies

| Finding | Measurement |
| --- | --- |
| Hardcoded colors, no tokens | **78 distinct hex values**, zero CSS variables |
| Near-duplicate near-blacks | `#0d1012` `#0d0f11` `#0b0d0f` `#090c0f` `#101316` `#101417` `#11161a` |
| Near-duplicate near-whites | `#eef3f5` `#eef7fa` `#e8f0f2` `#e9f1f4` `#e7eef1` `#f8faf9` |
| Near-duplicate borders | `#354046` `#354047` `#334046` `#31404a` `#36464f` `#2f3940` |
| Ad-hoc spacing | **10 distinct `gap` values** (3,4,5,6,7,8,9,10,12,16px) |
| Ad-hoc padding | `9px`, `0 7px`, `0 9px` alongside 8/10/12/16 |
| Stray border radius | exactly **one** `border-radius` in 1289 lines -- the System panel added in M19, which broke the otherwise square industrial language |

The square-cornered language is deliberate and was kept; the one rounded panel
was the outlier and was squared.

## Decisions

- Introduce a small token set on `:root` (surfaces, text, border, accent,
  status, spacing, control heights). Not a design system -- just enough to stop
  the drift.
- Collapse the near-duplicate families to one token each.
- Normalize spacing onto a 4px scale.
- Keep the existing direction: near-black graphite, silver text, restrained
  cyan accent, amber warning, red danger, green success.

## Gaps found and addressed

| Area | Gap | Resolution |
| --- | --- | --- |
| Onboarding | Empty state had 2 actions and terse example labels | Three actions (part / assembly / open), full example prompts |
| AI state | Absence only visible in the launcher terminal | Non-blocking banner in the workspace |
| Prompt | Only free-text log lines; no lifecycle | Explicit state machine with 7 states |
| Errors | Backend message shown raw in a log line | Titled error panel, plain-language text, details toggle |
| Loading | `busy` boolean with no context | Labelled loading states per operation |
| Mode | PART vs ASSEMBLY only inferable from which panel had data | Mode badge in the header |
| Viewer | Controls present but ungrouped and untitled | Grouped VIEW / DISPLAY / TOOLS with shortcut hints in tooltips |
| Shortcuts | Ctrl+K/Z/Shift+Z/Esc/? only | Added F, 0, 1, 2, 3 for views, guarded against text input |
| Accessibility | Modals lacked roles, labels, focus handling | Roles, labels, Escape, focus trap on dialogs |
| Export | Unsupported formats looked actionable | Availability shown per format |
| Interference | "overlap" did not say how it was computed | Explicit bounding-box vs precise wording |

## Deliberately out of scope

Full redesign, component library, phone layouts, theming beyond the single dark
direction, and animation work. The milestone is polish, not a rewrite.
