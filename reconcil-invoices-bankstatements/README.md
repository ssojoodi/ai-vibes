## One shot prompt for Claude Sonnet 4

```
My problem is reconciling my invoices in one system, with payments received at my bank which provides monthly statements in PDF format. 

Details about inputs:
- statements are available monthly in a multi-page PDF format. The statements are placed in a subfolder. Make sure each bank statement PDF gets processed only once.
- each bank statement has a list of transactions like a typical bank statement. Also each statement has an opening and closing balance so you can use that information to ensure the transactions in the statement are understood and digitized correctly. 
- all invoices are available as a CSV file. 
- all “invoice_payments” which are the payments we have previously reconciled against invoices are in another CSV file. Note that there may be multiple invoice_payments (or reductions) against a single Invoice.

Reconciling process:
- based on the payer name and amount of a transaction on a bank statement, as well as outstanding payable amounts on invoices, suggest the invoice which most likely is the one a payment was received against. 
- allow for user inputs: “yes”, “no”; yes appends to the “invoice_payments” file.
```

## How to deploy and run the system locally

```bash
# Create and activate virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Create .env file with OPENAI_API_KEY=your-key

# Run setup to create directories and sample files
python setup_environment.py

# Place bank statement PDFs in bank_statements/ folder
# Ensure invoices.csv exists with columns: invoice_id, customer_name, invoice_date, invoice_amount, due_date

# Run reconciliation
python reconcile.py  # Processes new PDFs, matches transactions to invoices, prompts for confirmation

# Manage cache (optional)
python manage_cache.py  # View cache stats or clear cached transaction data
```
