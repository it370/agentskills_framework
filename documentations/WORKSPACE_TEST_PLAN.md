# Workspace Isolation Test Plan

Quick manual checks to validate the workspace changes:

1. **Workspace lifecycle**
   - Login and call `GET /workspaces` – confirm a `default` workspace exists.
   - Create a new workspace via UI header; verify it appears in the dropdown and becomes active when chosen.
   - Switch between workspaces and confirm API responses include `workspace_id` and skills reload without errors.

2. **Skills visibility**
   - In Workspace A, create a private skill; ensure it shows in the list only for that workspace.
   - Mark the skill as public; switch to Workspace B and confirm it appears with a Public badge and can be opened.
   - Delete/update skills and confirm operations are restricted to the owning user/workspace.

3. **Runs scoping**
   - Start a run in Workspace A; ensure it appears in the Runs list and detail pages only for that workspace.
   - Switch to Workspace B and verify the run is hidden; switch back and confirm visibility returns.
   - Approve/pause/resume flows continue to work when `workspace_id` is supplied.

4. **Re-registration**
   - After switching workspaces, call `POST /workspaces/switch` (triggered by UI) and confirm the response includes `skills_loaded` without errors.
   - Reload skills via UI “Reload” action and ensure it succeeds while scoped.

5. **Persistence**
   - Refresh the browser; confirm the previously selected workspace remains active from localStorage and API calls include `workspace_id`.
