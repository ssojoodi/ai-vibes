#!/usr/bin/env python3
"""
Setup script for Invoice Reconciliation System
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def setup_environment():
    """Setup the environment for the reconciliation system"""
    print("Invoice Reconciliation System Setup")
    print("=" * 50)

    # Load environment variables from .env file
    load_dotenv()

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ OPENAI_API_KEY environment variable not found!")
        print("\nTo set up your OpenAI API key:")
        print("1. Get your API key from https://platform.openai.com/api-keys")
        print("2. Set the environment variable:")
        print("   - On macOS/Linux: export OPENAI_API_KEY='your-api-key-here'")
        print("   - On Windows: set OPENAI_API_KEY=your-api-key-here")
        print("   - Or add it to your shell profile (.bashrc, .zshrc, etc.)")
        print("\n3. Restart your terminal and run this script again")
        return False
    else:
        print("✅ OpenAI API key found")

    # Create required directories
    directories = ["bank_statements", "logs"]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created/verified directory: {directory}/")

    # Create sample files if they don't exist
    sample_files = {
        "invoices.csv": """invoice_id,customer_name,invoice_date,invoice_amount,due_date
INV-001,SOLUTIO Ltd,2024-01-01,14616.75,2024-01-31
INV-002,B.C. UN Corp,2024-01-10,79100.00,2024-02-10""",
        "invoice_payments.csv": """invoice_id,payment_date,amount,payer_name,bank_reference,reconciled_date""",
    }

    for filename, content in sample_files.items():
        file_path = Path(filename)
        if not file_path.exists():
            with open(file_path, "w") as f:
                f.write(content)
            print(f"✅ Created sample file: {filename}")
        else:
            print(f"✅ Found existing file: {filename}")

    print("\n" + "=" * 50)
    print("Setup completed successfully!")
    print("\nNext steps:")
    print("1. Place your bank statement PDFs in the bank_statements/ folder")
    print("2. Update invoices.csv with your actual invoice data")
    print("3. Run: python reconcile.py")
    print("\nThe system will process PDFs using OpenAI's vision API to extract")
    print("transaction data and help you reconcile them with your invoices.")

    return True


if __name__ == "__main__":
    if setup_environment():
        sys.exit(0)
    else:
        sys.exit(1)
