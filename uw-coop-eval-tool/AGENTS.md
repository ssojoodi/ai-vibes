# Agent handoff

## Start here

Read README.md, inspect the current branch and worktree, and read the relevant code. This directory is a subproject of the larger `ai-vibes` repository; keep changes scoped here unless asked otherwise. Do not assume a branch or PR from earlier conversations is still active. Commit or push only when requested.

Preserve the static vanilla HTML/CSS/JavaScript, no-build, no-backend workflow unless a requested feature requires a deliberate change.

## File boundaries

- `forms.js` dispatches through `document.body.dataset.formType` (`mid-term` or `end-term`). Its initialization functions own field lists and form events.
- `pdf-export.js` exposes `window.EvaluationPdf.midTerm(data, filename)` and `window.EvaluationPdf.endTerm(data, filename, competencySections, overallRatingGuidance)`. Each returns whether the print window opened. Keep report markup and print CSS here; keep validation and toasts in `forms.js`.
- Both HTML pages load `pdf-export.js` before `forms.js`.
- `COMPETENCY_SECTIONS`, `RATING_CHOICES`, and `OVERALL_RATING_GUIDANCE` live in `initEndTerm()`. Guidance is passed to the PDF renderer, not duplicated there.
- UI styles belong in `common.css`; PDF styles are separate and require their own visual checks.

## Data compatibility

Existing JSON field names and rating strings are a compatibility contract. Text fields use HTML IDs; checkbox groups are arrays. Detailed rating keys are generated as `${section.id}_${index}`. Reordering items or changing section IDs changes stored data meaning.

Optional top-level `rating_comments` maps those same rating keys to trimmed comment strings. Empty notes are omitted; the object is omitted when no notes exist. Older files without it must still import. Preserve flat rating values rather than replacing them with nested objects.

| Local storage key | Contents |
| --- | --- |
| `uw_draft` | Mid-term draft |
| `uw_end_term_draft` | End-term draft including saved internal notes |
| `uw_theme` | Shared theme preference |

End-term import clears the form before applying imported values. Ordinary inputs autosave; note editing is transactional. Only Save note or Cmd+Enter persists editor text. Closing or cancelling must not save unfinished edits.

Filename dates use UTC (`toISOString()`). Mid-term filenames use student and term; end-term filenames use student and reviewer (`q_your_name`, not `pi_supervisor`). Segments are sanitized and have fallbacks.

## Behavior to preserve

- Only detailed ratings 1 and 2 mandate internal notes. Ratings 3, 4, and Not observed are explicitly optional.
- Selecting 1 or 2 without a note opens the anchored editor. Export checks also open the first missing required note and stop export.
- Use one in-place popover for adding, editing, and viewing notes. Do not restore browser prompts or a separate note dialog.
- Save and Cmd+Enter validate, persist, and close. The shortcut must not fire during IME composition.
- The info icon and amber dot appear for saved notes at any rating, and for missing required notes.
- Tooltips appear immediately on hover or keyboard focus. Populate previews using text content, not HTML interpolation or the delayed browser `title` tooltip.
- Internal notes must never appear in PDFs. Retain this boundary in future report changes.
- The low-rating confirmation is separate from required notes: it reminds reviewers to include student-facing improvement guidance and applies to both export formats.
- Overall rating criteria appear in the UI and selected PDF section, not in JSON.
- Escape user input in report HTML.

## Verification

Run `node --check forms.js`, `node --check pdf-export.js`, and `git diff --check`. There is no committed test runner. Use a fresh browser context and synthetic student data to avoid overwriting real drafts.

1. Open both pages locally. Check light/dark themes and a narrow viewport.
2. Select 1 or 2 without a note: editor opens, empty save is blocked, and the indicator remains after cancelling.
3. Select 3, 4, or N.O.: no mandatory-note prompt. Add an optional note; confirm the indicator and immediate tooltip.
4. Save via the button and Cmd+Enter separately. Both close the editor; reopening and reloading retain saved text. Cancelled edits do not replace it.
5. Clear an optional note and save. Its indicator disappears unless the rating requires a note.
6. Round-trip JSON with notes, then import an older file without `rating_comments`. Ratings retain their meaning; old files clear previously loaded notes.
7. Attempt both exports with missing required notes. Complete them, then exercise Yes and No in the low-rating confirmation.
8. Export PDFs for both forms. Check selected guidance, long/multiline text, HTML-sensitive characters, page breaks, and absence of a recognizable internal test note.
9. Check blocked-pop-up feedback. Importing or clearing one form must not erase the other form's draft.

## Known gaps and history

HTML `required` attributes do not currently gate export: buttons use `type="button"` and handlers do not call `reportValidity()`. Do not claim complete required-field enforcement without implementing and testing it. JSON is parsed and mapped without a formal schema. Native dialog/Popover support is assumed without a fallback.

Historical references: `d293cb4` contains the latest note workflow; `e53c03b` merged the earlier report and rating-feedback changes (PR #8). Check Git for current remote, branch, and deployment state rather than inferring it from these references.

The prior release-note DOCX was generated under `output/` using synthetic UI screenshots. It is not a runtime dependency and may be absent in a fresh clone. Temporary capture/document scripts from earlier sessions are not maintained project tooling.
