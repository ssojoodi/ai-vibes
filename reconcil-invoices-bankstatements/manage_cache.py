#!/usr/bin/env python3
"""
Cache management utility for Invoice Reconciliation System
"""

import sys
from pathlib import Path
from reconcile import InvoiceReconciliationSystem


def show_cache_info(reconciler):
    """Display detailed cache information"""
    print("\n" + "=" * 60)
    print("TRANSACTION CACHE INFORMATION")
    print("=" * 60)

    cache_stats = reconciler.get_cache_statistics()
    print(f"Cache file: {cache_stats['cache_file']}")
    print(f"Cached PDFs: {cache_stats['cached_pdfs']}")
    print(f"Total cached transactions: {cache_stats['total_cached_transactions']}")

    if cache_stats["cached_pdfs"] > 0:
        print("\nCached PDFs:")
        print("-" * 40)
        for cache_key, data in reconciler.transaction_cache.items():
            pdf_name = data.get("pdf_name", "Unknown")
            transaction_count = len(data.get("transactions", []))
            processed_date = data.get("processed_date", "Unknown")
            print(f"• {pdf_name}")
            print(f"  Transactions: {transaction_count}")
            print(f"  Processed: {processed_date}")
            print()


def clear_cache(reconciler):
    """Clear the transaction cache"""
    cache_stats = reconciler.get_cache_statistics()
    if cache_stats["cached_pdfs"] == 0:
        print("Cache is already empty.")
        return

    print(
        f"This will clear {cache_stats['cached_pdfs']} cached PDFs with {cache_stats['total_cached_transactions']} transactions."
    )
    confirm = input("Are you sure? (y/N): ").strip().lower()

    if confirm == "y":
        reconciler.clear_transaction_cache()
        print("✅ Cache cleared successfully!")
    else:
        print("Cache clear cancelled.")


def main():
    """Main cache management interface"""
    print("Invoice Reconciliation System - Cache Manager")
    print("=" * 50)

    try:
        reconciler = InvoiceReconciliationSystem()
    except Exception as e:
        print(f"Error initializing system: {e}")
        sys.exit(1)

    while True:
        print("\nCache Management Options:")
        print("1. Show cache information")
        print("2. Clear cache")
        print("3. Exit")

        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == "1":
            show_cache_info(reconciler)
        elif choice == "2":
            clear_cache(reconciler)
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()
