"""Built-in messy sample datasets for instant testing and demos."""

from __future__ import annotations

import pandas as pd


def get_sample_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": "retail_sales",
            "name": "Messy Retail Sales (CSV)",
            "filename": "messy_retail_sales.csv",
            "description": "Order records with currency strings ($1,250.50), mixed dates, duplicate rows, irregular spaces, and N/A placeholders.",
        },
        {
            "id": "hr_employees",
            "name": "HR Employees Directory",
            "filename": "hr_employees_dirty.csv",
            "description": "Employee salaries, departments, hire dates, boolean active flags, missing salaries, and duplicate entries.",
        },
        {
            "id": "ecommerce_orders",
            "name": "E-Commerce Transactions",
            "filename": "ecommerce_transactions.csv",
            "description": "Customer orders across regions and payment methods with discounts, messy headers, and empty rows.",
        },
    ]


def load_sample_dataframe(sample_id: str) -> tuple[str, pd.DataFrame]:
    """Return (filename, raw_messy_dataframe) for a built-in sample."""
    if sample_id == "retail_sales":
        rows = [
            {"Order ID": "1001", " Order Date ": "2024-01-05", "Customer Name": "  Alice Johnson ", "Region": "North", "Category": "Electronics", "Product": "Laptop Pro", "Quantity": "2", "Revenue ($)": "$2,400.00", "Profit ($)": "$480.00", "Status": "Completed"},
            {"Order ID": "1002", " Order Date ": "01/12/2024", "Customer Name": "Bob Smith", "Region": "South", "Category": "Furniture", "Product": "Ergonomic Chair", "Quantity": "4", "Revenue ($)": "$1,200.00", "Profit ($)": "$300.00", "Status": "Completed"},
            {"Order ID": "1003", " Order Date ": "Jan 18, 2024", "Customer Name": "Carol White", "Region": "East", "Category": "Electronics", "Product": "Wireless Mouse", "Quantity": "10", "Revenue ($)": "$350.00", "Profit ($)": "$120.00", "Status": "Pending"},
            {"Order ID": "1004", " Order Date ": "2024/02/03", "Customer Name": "David Lee", "Region": "West", "Category": "Office Supplies", "Product": "Standing Desk", "Quantity": "1", "Revenue ($)": "$650.00", "Profit ($)": "$190.00", "Status": "Completed"},
            {"Order ID": "1004", " Order Date ": "2024/02/03", "Customer Name": "David Lee", "Region": "West", "Category": "Office Supplies", "Product": "Standing Desk", "Quantity": "1", "Revenue ($)": "$650.00", "Profit ($)": "$190.00", "Status": "Completed"},
            {"Order ID": "1005", " Order Date ": "2024-02-14", "Customer Name": "Eva   Martinez", "Region": "N/A", "Category": "Electronics", "Product": "4K Monitor", "Quantity": "3", "Revenue ($)": "$1,350.00", "Profit ($)": "null", "Status": "Completed"},
            {"Order ID": "1006", " Order Date ": "2024-03-01", "Customer Name": "Frank Chen", "Region": "North", "Category": "Furniture", "Product": "Bookshelf", "Quantity": "2", "Revenue ($)": "$420.50", "Profit ($)": "$95.50", "Status": "Cancelled"},
            {"Order ID": "1007", " Order Date ": "03/15/2024", "Customer Name": "Grace Kim", "Region": "East", "Category": "Electronics", "Product": "Noise Cancelling Headphones", "Quantity": "5", "Revenue ($)": "$1,125.00", "Profit ($)": "$340.00", "Status": "Completed"},
            {"Order ID": "1008", " Order Date ": "2024-03-22", "Customer Name": "Henry Patel", "Region": "South", "Category": "Office Supplies", "Product": "Printer Paper Box", "Quantity": "12", "Revenue ($)": "$360.00", "Profit ($)": "$80.00", "Status": "Completed"},
            {"Order ID": "", " Order Date ": "", "Customer Name": "", "Region": "", "Category": "", "Product": "", "Quantity": "", "Revenue ($)": "", "Profit ($)": "", "Status": ""},
            {"Order ID": "1009", " Order Date ": "2024-04-04", "Customer Name": "Ivy Nguyen", "Region": "West", "Category": "Electronics", "Product": "Tablet Air", "Quantity": "3", "Revenue ($)": "$1,800.00", "Profit ($)": "$450.00", "Status": "Completed"},
            {"Order ID": "1010", " Order Date ": "2024-04-19", "Customer Name": "Jack Wilson", "Region": "North", "Category": "Furniture", "Product": "Conference Table", "Quantity": "1", "Revenue ($)": "$2,100.00", "Profit ($)": "$520.00", "Status": "Pending"},
            {"Order ID": "1011", " Order Date ": "2024-05-08", "Customer Name": "Karen Lopez", "Region": "East", "Category": "Electronics", "Product": "Laptop Pro", "Quantity": "1", "Revenue ($)": "$1,200.00", "Profit ($)": "$240.00", "Status": "Completed"},
            {"Order ID": "1012", " Order Date ": "2024-05-20", "Customer Name": "Liam Brown", "Region": "South", "Category": "Office Supplies", "Product": "Desk Lamp", "Quantity": "6", "Revenue ($)": "$270.00", "Profit ($)": "-", "Status": "Completed"},
        ]
        return "messy_retail_sales.csv", pd.DataFrame(rows)

    if sample_id == "hr_employees":
        rows = [
            {"Emp ID": "E01", "Full Name": "  Sarah Connor ", "Department": "Engineering", "Role": "Senior Engineer", "Salary ($)": "$125,000", "Hire Date": "2021-03-15", "Active?": "Yes", "Location": "San Francisco"},
            {"Emp ID": "E02", "Full Name": "John Reese", "Department": "Engineering", "Role": "Staff Engineer", "Salary ($)": "$145,000", "Hire Date": "06/01/2020", "Active?": "yes", "Location": "New York"},
            {"Emp ID": "E03", "Full Name": "Maya Lin", "Department": "Product", "Role": "Product Manager", "Salary ($)": "$118,000", "Hire Date": "2022-08-10", "Active?": "true", "Location": "San Francisco"},
            {"Emp ID": "E04", "Full Name": "Carlos Ruiz", "Department": "Sales", "Role": "Account Executive", "Salary ($)": "$92,000", "Hire Date": "2023-01-20", "Active?": "Yes", "Location": "Austin"},
            {"Emp ID": "E04", "Full Name": "Carlos Ruiz", "Department": "Sales", "Role": "Account Executive", "Salary ($)": "$92,000", "Hire Date": "2023-01-20", "Active?": "Yes", "Location": "Austin"},
            {"Emp ID": "E05", "Full Name": "Nina Brooks", "Department": "Marketing", "Role": "Growth Lead", "Salary ($)": "N/A", "Hire Date": "2022-11-05", "Active?": "Yes", "Location": "Chicago"},
            {"Emp ID": "E06", "Full Name": "Omar Farooq", "Department": "Engineering", "Role": "Data Engineer", "Salary ($)": "$115,000", "Hire Date": "2023-04-12", "Active?": "Yes", "Location": "New York"},
            {"Emp ID": "E07", "Full Name": "Priya Nair", "Department": "HR", "Role": "People Partner", "Salary ($)": "$85,000", "Hire Date": "2020-09-30", "Active?": "No", "Location": "Austin"},
            {"Emp ID": "E08", "Full Name": "Lucas Meyer", "Department": "Sales", "Role": "Sales Director", "Salary ($)": "$138,000", "Hire Date": "2019-07-22", "Active?": "Yes", "Location": "Chicago"},
            {"Emp ID": "E09", "Full Name": "Hannah Abbott", "Department": "Product", "Role": "UX Designer", "Salary ($)": "$105,000", "Hire Date": "2024-02-01", "Active?": "Yes", "Location": "San Francisco"},
            {"Emp ID": "E10", "Full Name": "Daniel Park", "Department": "Marketing", "Role": "Content Strategist", "Salary ($)": "$78,000", "Hire Date": "2023-09-14", "Active?": "false", "Location": "none"},
        ]
        return "hr_employees_dirty.csv", pd.DataFrame(rows)

    if sample_id == "ecommerce_orders":
        rows = [
            {"Transaction #": "TX-901", "Order Timestamp": "2024-06-01", "Country": "USA", "Channel": "Web", "Payment Method": "Card", "Items": "3", "Order Total": "$249.99", "Discount %": "10%", "Returned": "No"},
            {"Transaction #": "TX-902", "Order Timestamp": "2024-06-02", "Country": "Canada", "Channel": "Mobile App", "Payment Method": "PayPal", "Items": "1", "Order Total": "$89.50", "Discount %": "0%", "Returned": "No"},
            {"Transaction #": "TX-903", "Order Timestamp": "2024-06-04", "Country": "UK", "Channel": "Web", "Payment Method": "Card", "Items": "2", "Order Total": "$175.00", "Discount %": "15%", "Returned": "Yes"},
            {"Transaction #": "TX-904", "Order Timestamp": "2024-06-06", "Country": "USA", "Channel": "Mobile App", "Payment Method": "Apple Pay", "Items": "4", "Order Total": "$410.00", "Discount %": "5%", "Returned": "No"},
            {"Transaction #": "TX-905", "Order Timestamp": "2024-06-08", "Country": "Germany", "Channel": "Web", "Payment Method": "Card", "Items": "2", "Order Total": "$320.00", "Discount %": "N/A", "Returned": "No"},
            {"Transaction #": "TX-906", "Order Timestamp": "2024-06-10", "Country": "USA", "Channel": "Web", "Payment Method": "PayPal", "Items": "5", "Order Total": "$540.25", "Discount %": "20%", "Returned": "No"},
            {"Transaction #": "TX-906", "Order Timestamp": "2024-06-10", "Country": "USA", "Channel": "Web", "Payment Method": "PayPal", "Items": "5", "Order Total": "$540.25", "Discount %": "20%", "Returned": "No"},
            {"Transaction #": "TX-907", "Order Timestamp": "2024-06-12", "Country": "Canada", "Channel": "Web", "Payment Method": "-", "Items": "1", "Order Total": "$65.00", "Discount %": "0%", "Returned": "Yes"},
            {"Transaction #": "TX-908", "Order Timestamp": "2024-06-15", "Country": "UK", "Channel": "Mobile App", "Payment Method": "Apple Pay", "Items": "3", "Order Total": "$295.00", "Discount %": "10%", "Returned": "No"},
        ]
        return "ecommerce_transactions.csv", pd.DataFrame(rows)

    raise ValueError(f"Unknown sample id: {sample_id}")
