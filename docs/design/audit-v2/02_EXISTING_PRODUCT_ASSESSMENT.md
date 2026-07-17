# CareerPilot AI V2.0 - 02 Existing Product Assessment

> Date: 2026-07-15  
> Scope: Existing local product at `http://127.0.0.1:3001`  
> Destination: This local audit folder  
> Evidence: Screenshots captured in this audit run; code is used only to confirm implementation details.

## 1. Assessment Basis

CareerPilot AI is an existing single-page, 12-module job-search workspace. V2.0 should improve the current product incrementally and preserve the existing Next.js, React, TypeScript, Tailwind CSS, FastAPI, SQLAlchemy, API, database, business-rule and tab-navigation foundations.

The supplied V2.0 specification is a product direction, not a source of truth for implemented capabilities. Current code does not contain shadcn/ui or JWT authentication, local development uses SQLite, and the default AI path is deterministic local AI. Design and engineering work must follow the repository and verified runtime when those claims conflict.

## 2. Captured Flow

| Step | Screenshot | What the user sees | General health |
|---|---|---|---|
| 1 | `01-current-start.png` | Default AI interview workspace, 12-module navigation and repeated project-status rail. | Usable, visually consistent, but vertically heavy for an operations product. |
| 2 | `02-job-search.png` | Job-search filters and the separate Zhaopin official-site import action. | Functional, but two search concepts compete and applied profile defaults are invisible. |
| 3 | `03-job-search-result.png` | One imported Zhaopin job with salary and hard requirements. | Clear and scannable; provenance and match state need stronger labels. |
| 4 | `04-submission-automation.png` | Zhaopin connection, risk notice, automatic matching entry and manual task creation. | Safety boundary is visible, but action hierarchy and terminology are ambiguous. |
| 5 | `05-submission-plan.png` | A 60-job scan reduced to four pending candidates with per-job exclusion and action controls. | Core workflow works; score and action wording can lead to overconfidence or accidental submission. |

## 3. What Already Works Well

1. The visual language is coherent: blue primary actions, restrained slate text, compact spacing, light borders and limited radii fit an operational job-search tool.
2. Forms use consistent labels, helper text, borders and focus treatment. The imported job row exposes salary, education, experience, company size and source without requiring a detail page.
3. The automation risk notice is placed before the workflow and uses a distinct warning treatment without hiding the primary task.
4. The pending list supports per-job exclusion next to the primary action, which matches the required human-control model.
5. The product keeps all modules in one workspace and reuses the same user, resume, job and application data instead of creating disconnected flows.

## 4. Priority Findings

### P0 - Safety and trust

1. **The pending-row action says “立即投递” even though it opens a preview.** In Step 5 this wording implies an immediate external action, while the code only prepares the task and requires a later confirmation. Rename it to “预览并确认”; reserve “确认并投递” for the final external action.
2. **Every eligible row displays “匹配 100 分”.** A perfect score implies strong relevance, but the current score mostly reflects passing hard rules. Jobs such as “海外主播/有运营团队” and “tiktok经纪人” can therefore look like perfect matches. Separate “已通过硬性条件” from a future relevance score, or label the current value as a rule score.
3. **The scan and skip counts describe different populations.** Step 5 says “官网扫描 60 个，符合 4 个” but also “已跳过 0 个不符合条件的岗位”. The latter only counts local imported jobs and reads as a contradiction. Show “官网筛除 56 个” and label any local skip count separately.

### P1 - Workflow clarity

4. **Job Search exposes two search actions without explaining their scope.** “搜索并导入” searches Zhaopin with profile defaults, while “搜索岗位” filters local records. Rename the latter to “筛选本地职位”, and show the active profile-derived query as compact read-only criteria before external search.
5. **The page header repeats the panel title and consumes significant vertical space.** Step 1 and Step 4 show a large page title, then the same title again inside the panel. Keep the product identity, but reduce duplicate headings on non-interview modules.
6. **The fixed project-status rail has low task value.** “12 / 12” and the same three policy lines consume about one sixth of the desktop width on every module. Replace the generic module count with context-sensitive status, such as profile completeness, selected resume, Zhaopin connection or pending tasks.
7. **The 12-tab row is scan-heavy.** It works on wide desktop, but horizontal scrolling is the only small-screen strategy and there is no visible overflow cue. Preserve the same modules and order, but add a clear scroll affordance or a compact “More” treatment at narrow widths.

### P2 - Accessibility and responsive quality

8. **Buttons do not have a shared visible keyboard focus style.** Inputs have a focus ring, but the global button and tab styles only define hover/active states. Add `:focus-visible` treatment to buttons, tabs and links.
9. **Some helper and placeholder text is visually light.** The `#98a2b3` placeholder and small `0.68rem-0.7rem` status text may be difficult at common Windows scaling levels. Confirm contrast with automated checks and raise critical helper text to at least the existing `#667085` token.
10. **Responsive behavior is only partly evident.** Screenshots confirm desktop layout only. The navigation, right status rail, multi-column forms, automation summary and pending-job action group still need keyboard and mobile viewport testing.

## 5. Recommended Incremental Sequence

1. Correct safety wording and scan-count semantics in the submission flow.
2. Clarify external Zhaopin search versus local job filtering.
3. Add shared `focus-visible` styles and run keyboard/contrast checks.
4. Reduce duplicate page headings and make the status rail contextual without changing module routes or names.
5. Test the existing layout at 390 px, 768 px, 1280 px and 2048 px before considering broader visual refinements.

## 6. Evidence Limits

- The screenshots prove visible desktop states only; they do not prove screen-reader labels, tab order, keyboard traps, color contrast ratios, motion preferences or mobile behavior.
- No external application button was clicked during this audit. The pending-list capture used local draft generation only.
- The audit does not validate the factual quality of every imported job. It identifies how the current rule score and labels communicate certainty.

## 7. First Incremental Design Pass

Completed immediately after the assessment without changing routes, APIs or layout:

- “立即投递” on pending rows is now “预览并确认”; the final action remains “确认并投递”.
- The automatic entry is now “搜索并生成清单”, which describes its actual behavior.
- “匹配 100 分” is now “规则 100 分”, avoiding the claim of a perfect semantic match.
- The pending-list header now distinguishes official-site filtering from local skipped jobs, for example “官网筛除 56 个；本地跳过 0 个”.
- The local job action is now “筛选本地职位”, distinct from the Zhaopin “搜索并导入” action.
- Buttons and links now receive a shared visible `focus-visible` outline.
- If official-site import succeeds but draft-plan creation fails, the live status now reports the partial success explicitly and refreshes local data instead of collapsing both stages into “请求失败”.
