# Timesheet & Labor-Costing System for Multi-Crew Construction Firms

## Context

A mid-sized construction company runs several projects in parallel, each staffed by a dedicated field crew. Labor is its single largest variable cost, yet the firm still relies on paper timesheets and ad-hoc spreadsheets. Field workers punch time inconsistently, cost codes are applied late (if at all), and payroll must chase missing hours every Monday. Project managers only see labor over-runs weeks after they happen, when it's too late to course-correct. The business needs a single, job-site-friendly system that captures hours once, tags them with the right cost information, and surfaces real-time labor performance to both operations and finance.

## Problem Statement

Create a lightweight timesheet platform that:
1. Captures hours in the field without friction—whether via individual punches or a bulk crew sheet.
2. Attaches accurate cost code, phase, and activity tags at the moment of entry to feed job-costing and earned-value analysis.
3. Enforces a clear, auditable approval workflow that fits projects of different complexity.
4. Supports fast corrections while maintaining a full version history for compliance.
5. Delivers instant visibility into actual vs. budgeted labor so superintendents and PMs can act before costs escalate.

## Implemented Features

### User Management
- Role-based access control with Worker, Crew Admin, Superintendent, Project Manager, Payroll, and Admin roles
- Bulk user upload via CSV for efficient onboarding of crews
- Active/inactive user status management
- Secure password hashing and authentication

### Project & Cost Code Management
- Project creation with budget hours, start/end dates
- Cost code setup with budget hours, phase, and activity tracking
- Project-specific cost codes for accurate job costing
- Active/inactive status management for projects and cost codes

### Crew Management
- Crew creation and assignment to projects
- Supervisor assignment (Crew Admin or Superintendent)
- Flexible crew membership management
- Active/inactive status for crews and members

### Timesheet Entry
- Individual timesheet entries with hours and overtime
- Bulk timesheet upload via CSV for efficient data entry
- Required cost code assignment for accurate job costing
- Description field for detailed activity tracking
- Automatic timesheet creation based on date and crew

### Approval Workflow
- Multi-step approval process:
  1. Draft → Pending Superintendent
  2. Pending Superintendent → Pending PM
  3. Pending PM → Pending Payroll
  4. Pending Payroll → Approved
- Bulk approval capability for efficient processing
- Full approval history tracking
- Role-based approval permissions
- Ability to submit all draft timesheets at once

### Labor Dashboard
- Real-time labor summary by cost code
- Project filtering for focused analysis
- Date range selection for period analysis
- Visual charts:
  - Labor hours by cost code (regular vs overtime)
  - Budget vs actual comparison
- Detailed labor summary table with:
  - Cost code details
  - Budget hours
  - Actual hours
  - Overtime hours
  - Variance tracking
  - Utilization percentage
- Color-coded variance indicators

### Data Model
- Implemented tables:
  - users
  - projects
  - crews
  - crew_members
  - cost_codes
  - timesheets
  - timesheet_entries
  - approvals
  - timesheet_versions

