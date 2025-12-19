# Database
## Stepik course

<img width="721" height="585" alt="image" src="https://github.com/user-attachments/assets/702de022-3b56-4090-9d01-0639f6df380b" />

# Final Project

# Grocery ERP System

**Grocery ERP System** is a professional web-based solution designed for managing grocery store networks. The system allows owners to track sales, manage product catalogs, monitor operational expenses, and analyze financial performance (Revenue and Net Profit) in real-time.

---

## 🛠 Tech Stack

* **Backend:** Python 3.10+, Flask (Web Framework)
* **Database:** PostgreSQL (DBMS), Psycopg2
* **Frontend:** HTML5, CSS3, Bootstrap 5, FontAwesome
* **Analytics:** SQL Views for real-time KPI calculation

---

## 🚀 Key Features

* **Multi-Branch Management:** Seamlessly switch between different store locations. All transactions and expenses are automatically linked to the active branch.
* **Financial Dashboard:** Automatic calculation of Revenue, Cost of Goods (COGS), Expenses, and Net Profit specifically for the **current month**.
* **Product Management:** * Create and manage product categories.
    * Register products with SKU, purchase, and retail prices.
    * Real-time inventory tracking (Stock-in/Stock-out).
* **POS Interface:** Interactive shopping cart with automatic inventory deduction upon checkout.

## ER Diagram

<img width="1745" height="1280" alt="diagram" src="https://github.com/user-attachments/assets/5087e987-7d92-4a06-bdc5-3725b0de4911" />

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/AZADEVV/database/tree/main/grocery_project
cd grocery-erp
2. Configure Environment
It is recommended to use a virtual environment:

Bash

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install flask psycopg2-binary
3. Database Initialization
Open pgAdmin 4 and create a database named grocery_db.

Open Query Tool and execute your schema.sql to create tables.

Required: Ensure you have created the view_simple_kpi for the dashboard to function correctly.

🖥 Running the Project
Run the Flask application:

Bash

python app.py
The website will be available at: http://127.0.0.1:5000

💡 User Flow
Select Branch: Use the navbar to pick a store location.

Manage Catalog: Create categories and add products in the Management section.

Process Sales: Add items to the cart on the Showcase page and click "Checkout".

Analyze: Check the Dashboard for real-time financial health reports.

📊 Database Structure
stores – Management of physical locations.

products – Product data (Name, SKU, Prices, Stock).

categories – Product grouping.

orders & order_items – Sales records.

expenses – Operational costs (Rent, Utilities, etc.).

Developed for efficient retail management and data-driven decision making.
