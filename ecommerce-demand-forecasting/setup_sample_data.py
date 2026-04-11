# setup_sample_data.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


def generate_sample_sales_data():
    """Generate sample sales data CSV"""
    np.random.seed(42)

    # Generate 90 days of data for 5 products
    start_date = datetime.now() - timedelta(days=90)
    products = ["SKU001", "SKU002", "SKU003", "SKU004", "SKU005"]
    product_names = [
        "Kitchen Towels",
        "Cleaning Spray",
        "Storage Bins",
        "Dish Soap",
        "Sponges",
    ]

    data = []

    for i, (sku, name) in enumerate(zip(products, product_names)):
        base_demand = 20 + i * 5  # Different base demands per product

        for day in range(90):
            date = start_date + timedelta(days=day)

            # Add seasonality and trend
            seasonal_factor = 1 + 0.3 * np.sin(2 * np.pi * day / 30)  # Monthly cycle
            trend_factor = 1 + (day / 365) * 0.1  # Slight upward trend
            noise = np.random.normal(1, 0.2)  # Random noise

            demand = base_demand * seasonal_factor * trend_factor * noise
            demand = max(0, int(demand))  # Ensure non-negative integer

            revenue = demand * (10 + i * 2)  # Different prices per product
            cost = revenue * 0.6  # 60% cost ratio

            data.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "product_sku": sku,
                    "product_name": name,
                    "quantity_sold": demand,
                    "revenue": round(revenue, 2),
                    "cost": round(cost, 2),
                }
            )

    df = pd.DataFrame(data)
    df.to_csv("sample_sales_data.csv", index=False)
    print("Generated sample_sales_data.csv")


def generate_sample_inventory_data():
    """Generate sample inventory data CSV"""
    products = ["SKU001", "SKU002", "SKU003", "SKU004", "SKU005"]
    current_date = datetime.now()

    data = []

    for sku in products:
        base_stock = np.random.randint(50, 200)
        reorder_point = base_stock * 0.3
        max_stock = base_stock * 1.5

        data.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "product_sku": sku,
                "current_stock": base_stock,
                "reorder_point": int(reorder_point),
                "max_stock": int(max_stock),
            }
        )

    df = pd.DataFrame(data)
    df.to_csv("sample_inventory_data.csv", index=False)
    print("Generated sample_inventory_data.csv")


if __name__ == "__main__":
    print("Generating sample data files...")
    generate_sample_sales_data()
    generate_sample_inventory_data()
    print("Sample data generation complete!")
