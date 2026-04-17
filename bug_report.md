# Bug Report & Fix Backlog

**Project:** FieldServicePRo
**Date:** April 16, 2026
**Prepared for:** Claude Code
**Total Issues:** 24

---

## How to Use This Document

Each issue below includes a unique ID, affected area, description, and expected behavior. Address issues in priority order. Where behavior is ambiguous, the **Expected Behavior** column defines the correct outcome.

---

## Issue Index

| ID | Area | Title | Priority |
|----|------|-------|----------|
| BUG-01 | Jobs | Job records not opening correctly | High |
| BUG-02 | Change Orders | Change Order sidebar redirects to Jobs tab | High |
| BUG-03 | Sidebar | Sidebar resets scroll position on tab click | Medium |
| BUG-04 | Vendors | Vendor sidebar links redirect to wrong tab | Medium |
| BUG-05 | Sidebar | AR Aging / Statements / Approvals redirect to Invoice tab | Medium |
| BUG-06 | AI Chatbot | AI Chatbot sidebar entry not at top of sidebar | Medium |
| BUG-07 | AI Chatbot | Floating action button should open AI Chatbot | High |
| BUG-08 | AI Chatbot | AI Chatbot interface needs UI/UX improvements | Medium |
| BUG-09 | Profile | Profile and Settings both route to Settings page | Medium |
| BUG-10 | Branding | Favicon is incorrect or missing | Low |
| BUG-11 | Feedback | Feedback page shows random string instead of empty state | Medium |
| BUG-12 | Invoices | Status filter does not sync financial summary amounts | High |
| BUG-13 | Invoices | Date filter not working | High |
| BUG-14 | Dashboard | Recent Activity scroll list has white gap at bottom | Low |
| BUG-15 | Invoices | Division tab filter not working | High |
| BUG-16 | Schedule | Division tab filter not working | High |
| BUG-17 | Change Orders | No option to add a new Change Order | High |
| BUG-18 | Equipment | No option to add new equipment or asset | High |
| BUG-19 | Recurring Jobs | "New Schedule" throws an error | High |
| BUG-20 | Clients | No required field validation when creating a new client | Medium |
| BUG-21 | Quotes | "New Quote" button not working | High |
| BUG-22 | Statements | Statement period filter not working | High |
| BUG-23 | Notifications | Notification preferences not persisted after refresh | High |
| BUG-24 | Notifications | Division tab on Notifications page redirects to Dashboard | High |

---

## Detailed Issue Descriptions

---

### BUG-01 — Jobs Tab: Some Job Records Not Opening

**Area:** Jobs  
**Priority:** High

**Description:**  
Not all jobs in the Jobs tab can be opened. Clicking on certain job entries does not navigate to the job detail view.

**Steps to Reproduce:**
1. Navigate to the **Jobs** tab.
2. Click on various job records in the list.

**Expected Behavior:**  
Every job record in the list should open its corresponding detail view when clicked.

**Actual Behavior:**  
Some job records do not respond to clicks or fail to open their detail view.

---

### BUG-02 — Change Order Sidebar: Redirects to Jobs Tab

**Area:** Change Orders / Sidebar  
**Priority:** High

**Description:**  
Clicking the "Change Order" item in the sidebar redirects the user to the Jobs tab instead of the Change Orders page.

**Steps to Reproduce:**
1. Click **Change Order** in the sidebar.

**Expected Behavior:**  
User should be navigated to the Change Orders page.

**Actual Behavior:**  
User is redirected to the Jobs tab.

---

### BUG-03 — Sidebar: Scroll Position Resets on Tab Click

**Area:** Sidebar / Navigation  
**Priority:** Medium

**Description:**  
Each time a tab is clicked in the sidebar, the sidebar scrolls back to the top, losing the user's position.

**Steps to Reproduce:**
1. Scroll down in the sidebar.
2. Click any sidebar tab.

**Expected Behavior:**  
The sidebar should retain its scroll position when navigating between tabs.

**Actual Behavior:**  
Sidebar resets to the top on every tab click.

---

### BUG-04 — Vendors Section: Sidebar Links Redirect to Vendor Tab Incorrectly

**Area:** Vendors / Sidebar  
**Priority:** Medium

**Description:**  
Tab links inside the Vendors section of the sidebar all redirect the active tab indicator to the "Vendor" tab, though the correct page does open in the main content area.

**Steps to Reproduce:**
1. Expand the **Vendors** section in the sidebar.
2. Click any sub-link (e.g., Vendor Contacts, Purchase Orders).

**Expected Behavior:**  
The active/highlighted tab in the sidebar should reflect the sub-link that was clicked.

**Actual Behavior:**  
All sub-links highlight the parent "Vendor" tab in the sidebar, even though the correct page loads.

---

### BUG-05 — AR Aging / Statements / Approvals: Sidebar Highlights Invoice Tab

**Area:** Sidebar / Invoices  
**Priority:** Medium

**Description:**  
When navigating to AR Aging, Statements, or Approvals, the sidebar incorrectly highlights the Invoice tab as active, though the correct page loads.

**Steps to Reproduce:**
1. Click **AR Aging**, **Statements**, or **Approvals** in the sidebar.

**Expected Behavior:**  
The sidebar should highlight the correct tab matching the current page.

**Actual Behavior:**  
The Invoice tab is highlighted regardless of which of the three pages is active.

---

### BUG-06 — AI Chatbot: Sidebar Position Should Be at Top

**Area:** AI Chatbot / Sidebar  
**Priority:** Medium

**Description:**  
The AI Chatbot entry in the sidebar is not at the top. It should be the first item in the sidebar for easy access.

**Expected Behavior:**  
AI Chatbot sidebar link should appear at the very top of the sidebar navigation list.

---

### BUG-07 — Floating Button: Should Launch AI Chatbot (Replace Quick Log)

**Area:** AI Chatbot / UI  
**Priority:** High

**Description:**  
The current green floating action button (FAB) opens Quick Log Communication. This should be replaced with the AI Chatbot. Clicking the FAB should open the AI Chatbot interface.

**Expected Behavior:**  
- The floating button should trigger the AI Chatbot, not the Quick Log.
- The Quick Log feature, if still needed, should be accessible elsewhere.

**Actual Behavior:**  
Floating button opens Quick Log Communication.

---

### BUG-08 — AI Chatbot: Interface Needs UI/UX Improvements

**Area:** AI Chatbot / UI  
**Priority:** Medium

**Description:**  
The AI Chatbot interface looks unpolished. It needs a more professional and clean design.

**Expected Behavior:**  
The AI Chatbot interface should look professional, with:
- Clean message bubbles with clear user/assistant distinction.
- Proper spacing, typography, and color scheme.
- A well-styled input field with a send button.
- Smooth scroll behavior within the chat window.
- Loading/typing indicators while waiting for a response.

---

### BUG-09 — Profile Dropdown: Profile and Settings Route to Same Page

**Area:** Profile / Navigation  
**Priority:** Medium

**Description:**  
In the profile dropdown menu, both the "Profile" and "Settings" options navigate to the same Settings page. The Profile page does not exist or is not correctly linked.

**Steps to Reproduce:**
1. Click the profile icon/avatar in the top navigation.
2. Click **Profile**.
3. Click the profile icon again and click **Settings**.

**Expected Behavior:**  
- "Profile" should open the user's profile page (name, avatar, contact info, etc.).
- "Settings" should open the application settings page.

**Actual Behavior:**  
Both options navigate to the Settings page.

---

### BUG-10 — Favicon: Incorrect or Missing

**Area:** Branding  
**Priority:** Low

**Description:**  
The website favicon (the small icon shown in browser tabs) is either missing or displaying an incorrect/default icon.

**Expected Behavior:**  
The correct application favicon should be displayed in the browser tab.

---

### BUG-11 — Feedback Page: Shows Random String Instead of Empty State

**Area:** Feedback  
**Priority:** Medium

**Description:**  
When no ratings have been submitted, the Feedback page displays a random/garbage string instead of a proper empty state message.

**Expected Behavior:**  
When there are no ratings, the page should display a clear empty state such as: *"No ratings yet. Be the first to leave feedback."*

**Actual Behavior:**  
A random/unformatted string is displayed in place of the empty state.

---

### BUG-12 — Invoices: Status Filter Doesn't Sync Financial Summary

**Area:** Invoices  
**Priority:** High

**Description:**  
When a status filter is applied on the Invoices page, the summary amounts (Paid Amount, Outstanding Amount, Overdue Amount) shown at the top do not update to reflect the filtered results.

**Steps to Reproduce:**
1. Go to the **Invoices** page.
2. Apply a **Status** filter (e.g., "Paid" or "Overdue").

**Expected Behavior:**  
The Paid, Outstanding, and Overdue summary amounts should recalculate based on the currently filtered invoice set.

**Actual Behavior:**  
Summary amounts remain unchanged regardless of the applied status filter.

---

### BUG-13 — Invoices: Date Filter Not Working

**Area:** Invoices  
**Priority:** High

**Description:**  
The date filter on the Invoices page does not filter the invoice list when a date range is selected.

**Steps to Reproduce:**
1. Go to the **Invoices** page.
2. Select a date range using the date filter.

**Expected Behavior:**  
The invoice list should filter to show only invoices within the selected date range.

**Actual Behavior:**  
The list does not change after applying the date filter.

---

### BUG-14 — Dashboard: Recent Activity Scroll List Has White Gap at Bottom

**Area:** Dashboard / UI  
**Priority:** Low

**Description:**  
In the Recent Activity section of the Dashboard, the scrollable list does not fully fill its container div. A white/empty bar appears at the bottom of the list.

**Expected Behavior:**  
The scrollable list should fill the container completely with no visible gap or white bar at the bottom.

---

### BUG-15 — Invoices: Division Tab Filter Not Working

**Area:** Invoices  
**Priority:** High

**Description:**  
The Division tab filter on the Invoices page does not filter the invoice list when a different division is selected.

**Steps to Reproduce:**
1. Go to the **Invoices** page.
2. Click a **Division** tab filter.

**Expected Behavior:**  
The invoice list should filter to show only invoices belonging to the selected division.

**Actual Behavior:**  
The invoice list does not change.

---

### BUG-16 — Schedule: Division Tab Filter Not Working

**Area:** Schedule  
**Priority:** High

**Description:**  
The Division tab filter on the Schedule page does not filter results when a division is selected.

**Steps to Reproduce:**
1. Go to the **Schedule** page.
2. Click a **Division** tab filter.

**Expected Behavior:**  
The schedule list/calendar should filter to show only items for the selected division.

**Actual Behavior:**  
Schedule results remain unchanged.

---

### BUG-17 — Change Orders: No Option to Add a New Change Order

**Area:** Change Orders  
**Priority:** High

**Description:**  
The Change Orders page has no visible button, link, or action to create a new change order.

**Expected Behavior:**  
There should be a clearly visible "New Change Order" or "+" button on the Change Orders page that opens a form/modal to create a new change order.

---

### BUG-18 — Equipment: No Option to Add New Equipment or Asset

**Area:** Equipment  
**Priority:** High

**Description:**  
The Equipment page has no button or option to add a new piece of equipment or asset.

**Expected Behavior:**  
There should be a clearly visible "Add Equipment" or "New Asset" button that opens a creation form/modal.

---

### BUG-19 — Recurring Jobs: "New Schedule" Throws an Error

**Area:** Recurring Jobs  
**Priority:** High

**Description:**  
Clicking "New Schedule" on the Recurring Jobs page results in an error: *"Something went wrong."*

**Steps to Reproduce:**
1. Navigate to **Recurring Jobs**.
2. Click **New Schedule**.

**Expected Behavior:**  
A form or modal should open allowing the user to create a new recurring job schedule.

**Actual Behavior:**  
An error message is displayed: *"Something went wrong."*

---

### BUG-20 — Clients: No Required Field Validation on New Client Form

**Area:** Clients  
**Priority:** Medium

**Description:**  
When creating a new client, there is no required field validation. Users can submit the form without filling in mandatory information.

**Expected Behavior:**  
Required fields (at minimum: client name) should be validated before form submission. An appropriate error message or highlight should be shown for any missing required field.

---

### BUG-21 — Quotes: "New Quote" Button Not Working

**Area:** Quotes  
**Priority:** High

**Description:**  
The "New Quote" button on the Quotes page does not respond when clicked.

**Steps to Reproduce:**
1. Navigate to the **Quotes** page.
2. Click the **New Quote** button.

**Expected Behavior:**  
A form or modal should open to create a new quote.

**Actual Behavior:**  
Nothing happens when the button is clicked.

---

### BUG-22 — Statements: Statement Period Filter Not Working

**Area:** Statements  
**Priority:** High

**Description:**  
The statement period filter on the Statements page does not filter the list of statements when a period is selected.

**Steps to Reproduce:**
1. Navigate to the **Statements** page.
2. Select a **Statement Period** filter.

**Expected Behavior:**  
The statements list should update to show only statements within the selected period.

**Actual Behavior:**  
The list remains unchanged after selecting a period.

---

### BUG-23 — Notification Preferences: Not Persisted After Page Refresh

**Area:** Notifications / Settings  
**Priority:** High

**Description:**  
Changes made on the Notification Preferences page are not saved persistently. After refreshing the page, preferences revert to their previous/default state.

**Steps to Reproduce:**
1. Go to **Notification Preferences**.
2. Update one or more preferences and save.
3. Refresh the page.

**Expected Behavior:**  
Saved notification preferences should persist across page refreshes and sessions.

**Actual Behavior:**  
Preferences revert to the previous state after a page refresh.

---

### BUG-24 — Notifications Page: Division Tab Redirects to Dashboard

**Area:** Notifications  
**Priority:** High

**Description:**  
On the Notifications page, clicking any Division tab redirects the user to the Dashboard instead of filtering notifications by division.

**Steps to Reproduce:**
1. Navigate to the **Notifications** page.
2. Click any **Division** tab.

**Expected Behavior:**  
The notifications list should filter to show only notifications for the selected division, remaining on the Notifications page.

**Actual Behavior:**  
User is redirected to the Dashboard.

---

## Summary by Category

| Category | Issue Count | IDs |
|----------|-------------|-----|
| Sidebar / Navigation | 5 | BUG-02, BUG-03, BUG-04, BUG-05, BUG-06 |
| Filters (not working) | 6 | BUG-12, BUG-13, BUG-15, BUG-16, BUG-22, BUG-24 |
| Missing Features / Buttons | 4 | BUG-17, BUG-18, BUG-21, BUG-20 |
| AI Chatbot | 3 | BUG-06, BUG-07, BUG-08 |
| Notifications | 2 | BUG-23, BUG-24 |
| Invoices | 3 | BUG-12, BUG-13, BUG-15 |
| Errors / Crashes | 2 | BUG-01, BUG-19 |
| UI / Display | 3 | BUG-10, BUG-11, BUG-14 |
| Profile / Auth | 1 | BUG-09 |

---

*End of Bug Report — 24 issues documented.*
