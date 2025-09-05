# Construction Crew Time Tracking System

A web-based timesheet and labor costing system designed for multi-crew construction firms. The system captures field hours, applies accurate cost codes, and provides real-time labor performance visibility to help project managers control costs and improve efficiency.

## What It Does

The system manages the complete timesheet workflow from field entry to payroll approval. Workers can log hours individually or through bulk crew uploads, with each entry tagged to specific cost codes for accurate job costing. Timesheets flow through a multi-step approval process: Draft → Superintendent → Project Manager → Payroll → Approved. The dashboard provides real-time labor summaries showing actual vs budgeted hours with variance tracking and utilization metrics.

Key features include role-based access control for different user types (Workers, Crew Admins, Superintendents, Project Managers, Payroll, and Admins), project and cost code management, crew organization, and comprehensive reporting tools that help identify labor overruns before they become costly problems.

## Quick Start

1. **Install dependencies:**
   ```bash
   # create a Python Virtual Env
   python -m venv venv
   source ./venv/bin/activate

   pip install -r requirements.txt
   ```

2. **Initialize the database:**
   ```bash
   source ./venv/bin/activate

   python init_db.py
   ```

3. **Run the application:**
   ```bash
   source ./venv/bin/activate

   python app.py
   ```

