import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import json
from difflib import SequenceMatcher
import logging
import fitz  # PyMuPDF for PDF to image conversion
import base64
import openai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class InvoiceReconciliationSystem:
    def __init__(self, config_file="reconciliation_config.json"):
        """Initialize the reconciliation system with configuration"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.processed_statements = self.load_processed_statements()
        self.transaction_cache = self.load_transaction_cache()
        self.setup_openai()

    def setup_openai(self):
        """Setup OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.logger.error("OPENAI_API_KEY environment variable not set")
            raise ValueError("OpenAI API key is required")

        self.openai_client = openai.OpenAI(api_key=api_key)

    def load_config(self, config_file):
        """Load configuration or create default"""
        default_config = {
            "bank_statements_folder": "bank_statements/",
            "invoices_csv": "invoices.csv",
            "invoice_payments_csv": "invoice_payments.csv",
            "processed_statements_file": "processed_statements.json",
            "transaction_cache_file": "transaction_cache.json",
            "similarity_threshold": 0.6,
            "amount_tolerance": 0.01,
            "openai_model": "gpt-4o",
        }

        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path, "r") as f:
                return {**default_config, **json.load(f)}
        else:
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=4)
            return default_config

    def setup_logging(self):
        """Setup logging for tracking processing"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("reconciliation.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def load_processed_statements(self):
        """Load list of already processed statement files"""
        processed_file = Path(self.config["processed_statements_file"])
        if processed_file.exists():
            with open(processed_file, "r") as f:
                return set(json.load(f))
        return set()

    def load_transaction_cache(self):
        """Load cached transaction data"""
        cache_file = Path(self.config["transaction_cache_file"])
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                self.logger.warning(f"Error loading transaction cache: {str(e)}")
                return {}
        return {}

    def save_transaction_cache(self, cache_data):
        """Save transaction cache data"""
        try:
            with open(self.config["transaction_cache_file"], "w") as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving transaction cache: {str(e)}")

    def get_pdf_cache_key(self, pdf_path):
        """Generate a cache key for a PDF file based on path and modification time"""
        try:
            stat = pdf_path.stat()
            return f"{pdf_path.name}_{stat.st_size}_{int(stat.st_mtime)}"
        except Exception:
            return pdf_path.name

    def save_processed_statements(self):
        """Save list of processed statements"""
        with open(self.config["processed_statements_file"], "w") as f:
            json.dump(list(self.processed_statements), f)

    def pdf_to_images(self, pdf_path):
        """Convert PDF pages to images for OpenAI vision processing"""
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(doc.page_count):
                page = doc[page_num]
                # Convert page to image
                mat = fitz.Matrix(2.0, 2.0)  # Higher resolution
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")

                # Convert to base64 for API
                img_base64 = base64.b64encode(img_data).decode()
                images.append(img_base64)

            doc.close()
            return images
        except Exception as e:
            self.logger.error(f"Error converting PDF to images: {str(e)}")
            return []

    def extract_transactions_with_openai(self, images):
        """Extract transactions using OpenAI vision API"""
        if not images:
            return [], None, None

        try:
            # Create messages for all pages
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this bank statement and extract all transaction data. Return the information as a JSON object with this exact structure:

{
    "opening_balance": <number or null>,
    "closing_balance": <number or null>,
    "transactions": [
        {
            "date": "MM/DD/YYYY",
            "description": "transaction description",
            "amount": <positive number for deposits/credits, negative for debits/cheques>,
            "type": "credit" or "debit"
        }
    ]
}

For the bank statement format shown:
- Extract the opening balance if shown
- Extract the closing balance if shown  
- For each transaction row:
  - Convert date to MM/DD/YYYY format
  - Use the full description text
  - For amounts in "Deposits & Credits" column, use positive numbers
  - For amounts in "Cheques & Debits" column, use negative numbers
  - Set type as "credit" for deposits/credits, "debit" for cheques/debits
  
Only include actual transaction entries, not headers or summary lines. Be precise with amounts and descriptions.""",
                        }
                    ],
                }
            ]

            # Add each page image
            for img_base64 in images:
                messages[0]["content"].append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    }
                )

            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model=self.config["openai_model"],
                messages=messages,
                max_tokens=4000,
                temperature=0,
            )

            # Parse response
            content = response.choices[0].message.content

            # Extract JSON from response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)

                # Process transactions to add payer names
                transactions = []
                for txn in data.get("transactions", []):
                    # Only include positive amounts (deposits/credits)
                    if txn["amount"] > 0:
                        txn["payer_name"] = self.extract_payer_name(txn["description"])
                        transactions.append(txn)

                return (
                    transactions,
                    data.get("opening_balance"),
                    data.get("closing_balance"),
                )
            else:
                self.logger.error("Could not extract JSON from OpenAI response")
                return [], None, None

        except Exception as e:
            self.logger.error(f"Error extracting transactions with OpenAI: {str(e)}")
            return [], None, None

    def extract_transactions_from_pdf(self, pdf_path):
        """Extract transactions from bank statement PDF using OpenAI vision"""
        self.logger.info(f"Processing PDF: {pdf_path}")

        # Generate cache key for this PDF
        cache_key = self.get_pdf_cache_key(pdf_path)

        # Check if we have cached data for this PDF
        if cache_key in self.transaction_cache:
            self.logger.info(f"Using cached transaction data for {pdf_path.name}")
            cached_data = self.transaction_cache[cache_key]
            return (
                cached_data.get("transactions", []),
                cached_data.get("opening_balance"),
                cached_data.get("closing_balance"),
            )

        # No cached data, process with OpenAI
        self.logger.info(f"No cached data found, processing with OpenAI API")

        # Convert PDF to images
        images = self.pdf_to_images(pdf_path)
        if not images:
            return [], None, None

        # Extract transactions using OpenAI
        transactions, opening_balance, closing_balance = (
            self.extract_transactions_with_openai(images)
        )

        # Cache the results if successful
        if transactions is not None:
            cache_data = {
                "transactions": transactions,
                "opening_balance": opening_balance,
                "closing_balance": closing_balance,
                "processed_date": datetime.now().isoformat(),
                "pdf_name": pdf_path.name,
            }

            self.transaction_cache[cache_key] = cache_data
            self.save_transaction_cache(self.transaction_cache)
            self.logger.info(f"Cached transaction data for {pdf_path.name}")

        return transactions, opening_balance, closing_balance

    def extract_payer_name(self, description):
        """Extract payer name from transaction description"""
        # Remove common banking terms
        clean_desc = re.sub(
            r"\b(transfer|payment|deposit|from|to|ref|reference)\b",
            "",
            description,
            flags=re.IGNORECASE,
        )

        # Extract what looks like a company or person name
        name_match = re.search(
            r"([A-Za-z\s&\.,-]+(?:ltd|llc|inc|corp|company)?)",
            clean_desc,
            re.IGNORECASE,
        )
        if name_match:
            return name_match.group(1).strip()

        return description.strip()

    def load_invoices_and_payments(self):
        """Load invoices and existing payments"""
        try:
            invoices_df = pd.read_csv(self.config["invoices_csv"])

            # Load existing payments
            payments_path = Path(self.config["invoice_payments_csv"])
            if payments_path.exists():
                payments_df = pd.read_csv(payments_path)
            else:
                # Create empty payments file with headers
                payments_df = pd.DataFrame(
                    columns=[
                        "invoice_id",
                        "payment_date",
                        "amount",
                        "payer_name",
                        "bank_reference",
                        "reconciled_date",
                    ]
                )
                payments_df.to_csv(payments_path, index=False)

            return invoices_df, payments_df

        except Exception as e:
            self.logger.error(f"Error loading CSV files: {str(e)}")
            return None, None

    def calculate_outstanding_amounts(self, invoices_df, payments_df):
        """Calculate outstanding amounts for each invoice"""
        # Group payments by invoice
        payment_totals = payments_df.groupby("invoice_id")["amount"].sum().to_dict()

        # Calculate outstanding amounts
        invoices_df["paid_amount"] = (
            invoices_df["invoice_id"].map(payment_totals).fillna(0)
        )
        invoices_df["outstanding_amount"] = (
            invoices_df["invoice_amount"] - invoices_df["paid_amount"]
        )

        # Only return invoices with outstanding amounts
        return invoices_df[invoices_df["outstanding_amount"] > 0].copy()

    def find_matching_invoices(self, transaction, outstanding_invoices):
        """Find potential matching invoices for a transaction"""
        matches = []

        for _, invoice in outstanding_invoices.iterrows():
            # Calculate name similarity
            name_similarity = SequenceMatcher(
                None,
                transaction["payer_name"].lower(),
                str(invoice.get("customer_name", "")).lower(),
            ).ratio()

            # Check amount match (within tolerance)
            amount_diff = abs(transaction["amount"] - invoice["outstanding_amount"])
            amount_match = amount_diff <= self.config["amount_tolerance"]

            # Calculate overall score
            score = name_similarity
            if amount_match:
                score += 0.4  # Bonus for exact amount match

            if score >= self.config["similarity_threshold"] or amount_match:
                matches.append(
                    {
                        "invoice": invoice,
                        "score": score,
                        "name_similarity": name_similarity,
                        "amount_match": amount_match,
                        "amount_diff": amount_diff,
                    }
                )

        # Sort by score
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:5]  # Return top 5 matches

    def present_matching_options(self, transaction, matches):
        """Present matching options to user"""
        print("\n" + "=" * 80)
        print(f"TRANSACTION TO RECONCILE:")
        print(f"Date: {transaction['date']}")
        print(f"Amount: ${transaction['amount']:,.2f}")
        print(f"Payer: {transaction['payer_name']}")
        print(f"Description: {transaction['description']}")
        print("\n" + "-" * 80)

        if not matches:
            print("No matching invoices found.")
            return None

        print("POTENTIAL MATCHES:")
        for i, match in enumerate(matches, 1):
            invoice = match["invoice"]
            print(f"\n{i}. Invoice #{invoice['invoice_id']}")
            print(f"   Customer: {invoice.get('customer_name', 'N/A')}")
            print(f"   Outstanding: ${invoice['outstanding_amount']:,.2f}")
            print(f"   Match Score: {match['score']:.2f}")

            if match["amount_match"]:
                amount_match_str = "Yes"
            else:
                amount_match_str = f"No (diff: ${match['amount_diff']:.2f})"
            print(f"   Amount Match: {amount_match_str}")

        print(f"\n0. Skip this transaction")
        print(f"q. Quit reconciliation")

        while True:
            choice = input("\nEnter your choice (number/0/q): ").strip().lower()

            if choice == "q":
                return "quit"
            elif choice == "0":
                return None
            elif choice.isdigit() and 1 <= int(choice) <= len(matches):
                return matches[int(choice) - 1]["invoice"]
            else:
                print("Invalid choice. Please try again.")

    def save_payment_record(self, transaction, invoice):
        """Save a payment record to the CSV file"""
        new_payment = {
            "invoice_id": invoice["invoice_id"],
            "payment_date": transaction["date"],
            "amount": transaction["amount"],
            "payer_name": transaction["payer_name"],
            "bank_reference": transaction["description"],
            "reconciled_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Append to CSV
        payments_df = pd.read_csv(self.config["invoice_payments_csv"])
        payments_df = pd.concat(
            [payments_df, pd.DataFrame([new_payment])], ignore_index=True
        )
        payments_df.to_csv(self.config["invoice_payments_csv"], index=False)

        self.logger.info(
            f"Payment recorded: Invoice {invoice['invoice_id']} - ${transaction['amount']}"
        )
        print(f"✓ Payment recorded successfully!")

    def process_bank_statements(self):
        """Main process to reconcile bank statements"""
        statements_folder = Path(self.config["bank_statements_folder"])

        if not statements_folder.exists():
            print(f"Bank statements folder '{statements_folder}' not found!")
            return

        # Find unprocessed PDF files
        pdf_files = [
            f
            for f in statements_folder.glob("*.pdf")
            if f.name not in self.processed_statements
        ]

        if not pdf_files:
            print("No new bank statements to process.")
            return

        # Load invoices and payments
        invoices_df, payments_df = self.load_invoices_and_payments()
        if invoices_df is None:
            return

        print(f"Found {len(pdf_files)} new bank statement(s) to process.")

        for pdf_file in pdf_files:
            print(f"\nProcessing: {pdf_file.name}")

            # Extract transactions
            transactions, opening_bal, closing_bal = self.extract_transactions_from_pdf(
                pdf_file
            )

            if not transactions:
                print(f"No transactions found in {pdf_file.name}")
                self.processed_statements.add(pdf_file.name)
                continue

            print(f"Found {len(transactions)} transactions")
            if opening_bal is not None and closing_bal is not None:
                print(f"Opening Balance: ${opening_bal:,.2f}")
                print(f"Closing Balance: ${closing_bal:,.2f}")

            # Calculate current outstanding invoices
            outstanding_invoices = self.calculate_outstanding_amounts(
                invoices_df, payments_df
            )

            # Process each transaction
            for transaction in transactions:
                matches = self.find_matching_invoices(transaction, outstanding_invoices)
                selected_invoice = self.present_matching_options(transaction, matches)

                # Handle different return types from present_matching_options
                if isinstance(selected_invoice, str) and selected_invoice == "quit":
                    return
                elif selected_invoice is not None:
                    self.save_payment_record(transaction, selected_invoice)

                    # Reload payments to update outstanding amounts
                    _, payments_df = self.load_invoices_and_payments()
                    outstanding_invoices = self.calculate_outstanding_amounts(
                        invoices_df, payments_df
                    )

            # Mark statement as processed
            self.processed_statements.add(pdf_file.name)
            self.save_processed_statements()
            print(f"✓ Completed processing {pdf_file.name}")

        print("\nReconciliation process completed!")

    def get_cache_statistics(self):
        """Get statistics about the transaction cache"""
        cache_size = len(self.transaction_cache)
        total_transactions = sum(
            len(data.get("transactions", []))
            for data in self.transaction_cache.values()
        )

        return {
            "cached_pdfs": cache_size,
            "total_cached_transactions": total_transactions,
            "cache_file": self.config["transaction_cache_file"],
        }

    def clear_transaction_cache(self):
        """Clear all cached transaction data"""
        self.transaction_cache = {}
        self.save_transaction_cache(self.transaction_cache)
        self.logger.info("Transaction cache cleared")

    def remove_pdf_from_cache(self, pdf_path):
        """Remove a specific PDF from the cache"""
        cache_key = self.get_pdf_cache_key(pdf_path)
        if cache_key in self.transaction_cache:
            del self.transaction_cache[cache_key]
            self.save_transaction_cache(self.transaction_cache)
            self.logger.info(f"Removed {pdf_path.name} from cache")
            return True
        return False


def main():
    """Main function to run the reconciliation system"""
    print("Invoice Reconciliation System")
    print("=" * 50)

    reconciler = InvoiceReconciliationSystem()

    # Show cache statistics
    cache_stats = reconciler.get_cache_statistics()
    if cache_stats["cached_pdfs"] > 0:
        print(
            f"📋 Cache Status: {cache_stats['cached_pdfs']} PDFs cached with {cache_stats['total_cached_transactions']} transactions"
        )
    else:
        print("📋 Cache Status: No cached data")

    reconciler.process_bank_statements()


if __name__ == "__main__":
    main()
