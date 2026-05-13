# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a workflow template for AI-assisted feature development. It defines a structured, three-phase process for converting feature requests into implemented code:

1. **PRD Creation** (`Context/create-prd.md`) — Convert a feature request into a Product Requirements Document
2. **Task Generation** (`Context/generate-tasks.md`) — Break a PRD into a hierarchical task list
3. **Task Execution** (`Context/process-task-list.md`) — Implement tasks one sub-task at a time

## Workflow

### Phase 1: Create a PRD

When asked to create a PRD for a feature:
1. Ask clarifying questions first (problem/goal, target user, core functionality, acceptance criteria, edge cases, scope). Present options as numbered/lettered lists.
2. Generate the PRD only after receiving answers.
3. Save to `/tasks/[n]-prd-[feature-name].md` using zero-padded 4-digit sequence (e.g., `0001-prd-user-authentication.md`).
4. Do **not** start implementing — stop after saving the PRD.

PRD sections: Introduction/Overview, Goals, User Stories, Functional Requirements, Non-Goals, Design Considerations (optional), Technical Considerations (optional), Success Metrics, Open Questions.

Write requirements as if the primary reader is a **junior developer**: explicit, unambiguous, minimal jargon.

### Phase 2: Generate a Task List

When pointed to a PRD file:
1. Read the PRD and assess the existing codebase (patterns, conventions, reusable components).
2. **Phase 2a:** Generate high-level parent tasks (~5) and save the file. Tell the user: *"I have generated the high-level tasks based on the PRD. Ready to generate the sub-tasks? Respond with 'Go' to proceed."* Then wait.
3. **Phase 2b:** After "Go", expand each parent task into sub-tasks covering implementation details.
4. Populate the `Relevant Files` section with files to create or modify, including test files.
5. Save to `/tasks/tasks-[prd-file-name].md` (e.g., `tasks-0001-prd-user-authentication.md`).

Task list format:
```markdown
## Relevant Files
- `path/to/file.ts` - Description of relevance.

### Notes
- Unit tests go alongside source files (e.g., `Component.tsx` and `Component.test.tsx`).
- Use `npx jest [optional/path/to/test/file]` to run tests.

## Tasks
- [ ] 1.0 Parent Task Title
  - [ ] 1.1 Sub-task description
  - [ ] 1.2 Sub-task description
- [ ] 2.0 Parent Task Title
  - [ ] 2.1 Sub-task description
```

### Phase 3: Execute Tasks

When working through a task list:
- **One sub-task at a time.** Do not start the next sub-task until the current one passes all appropriate tests.
- After each sub-task: mark it `[x]`, update the Relevant Files section, then continue.
- When **all sub-tasks** under a parent task are `[x]`:
  1. Run the full test suite.
  2. Only if all tests pass: stage changes, clean up temp files/code, then commit.
  3. Mark the parent task `[x]`.
- Commit format — conventional commits with multi-line `-m` flags:
  ```
  git commit -m "feat: add payment validation logic" -m "- Validates card type and expiry" -m "- Adds unit tests for edge cases" -m "Related to T123 in PRD"
  ```
- Keep the task list file updated as the source of truth for progress.
