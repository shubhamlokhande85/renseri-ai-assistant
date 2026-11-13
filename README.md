## 🚀 RENSERI AI ASSISTANT

### AI-Powered Data Analytics | Business Intelligence | Automated Data Cleaning

<p align="center">
<strong>Transform raw datasets into clean data, interactive dashboards, executive reports, and actionable business insights — powered by AI.</strong>
</p>

<p align="center">
<img src="https://img.shields.io/badge/Python-3.10--3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi" />
<img src="https://img.shields.io/badge/Groq-LLaMA%203.3%2070B-F55036?style=for-the-badge" />
<img src="https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google" />
<img src="https://img.shields.io/badge/SQLite3-Database-003B57?style=for-the-badge&logo=sqlite" />
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
<img src="https://img.shields.io/badge/Tests-23%2F23%20Passing-success?style=for-the-badge&logo=pytest" />
</p>

### 📌 Navigation

Overview

Architecture

Features

Technology Stack

Installation

VS Code Guide

Testing

Project Structure

License

### 🌟 Overview

RENSERI AI ASSISTANT is an end-to-end AI-powered Data Analytics and Business Intelligence platform.

It automates the data analysis lifecycle — from raw dataset ingestion and cleaning to interactive dashboards, executive reports, and strategic recommendations.

### 🎯 Key Highlights

Feature	Capability

AI Assistant	Groq + Gemini dual-engine

Data Ingestion	CSV, XLSX, XLS, JSON, Parquet, TSV, Text

Data Cleaning	Automated cleaning and validation

Dashboard	5 dynamic slicers

KPI Cards	5 analytical indicators

Visualizations	6+ interactive charts

Transformation	10 Power Query-style tools

Business Reports	Executive and department analysis

Recommendations	5 prioritized action items

Export	CSV, Excel, SQLite

Testing	23 automated tests

### 🏗️ System Architecture

mermaid

flowchart TD

    A["📂 Raw Dataset Ingestion"]
    A --> B["CSV / Excel / JSON / Parquet / TSV"]
    A --> C["Clipboard / Raw Text"]

    B --> D["🧹 Data Cleaning Pipeline"]
    C --> D

    D --> E["Pandas + NumPy"]
    E --> F["SQLite In-Memory Sandbox"]
    F --> G["FastAPI Backend"]

    G --> H["📊 Interactive Dashboard"]
    G --> I["📄 Executive Reports"]
    G --> J["🎯 Strategic Recommendations"]
    G --> K["🤖 AI Assistant"]

    K --> L["Groq LLaMA 3.3 70B"]
    K --> M["Google Gemini 2.5 Flash"]
    K --> N["🌐 Web Grounding"]

    H --> O["Chart.js"]
    I --> P["Business Insights"]
    J --> Q["Management Actions"]

### ✨ Key Features

🤖 1. AI Research Assistant

Groq LLaMA 3.3 70B integration.

Google Gemini 2.5 Flash fallback.

Wikipedia OpenSearch entity discovery.

DuckDuckGo web research.

Wikimedia image galleries.

Voice input using Web Speech API.

### 📂 2. Universal Dataset Ingestion

Supports multiple data formats:

CSV, XLSX, XLS

JSON, Parquet, TSV

Clipboard and raw text

Additional features:

Drag-and-drop uploading.

Dataset preview and schema inspection.

One-click sample dataset loaders.

### 🧹 3. Automated Data Cleaning

Missing-value detection and handling.

Duplicate identification and removal.

Whitespace cleaning.

Data-type correction.

Date standardization.

Data validation and cleaning audit logs.

### 📊 4. Interactive BI Dashboard


5 Dynamic Slicers

Category

Department

Product

Date

Segment

5 KPI Cards

Total Observations

Volume

Average

Median

Data Quality Health Score

6+ Interactive Charts

Time-series analysis.

Category distribution.

Department performance.

Ranked comparisons.

Segment analysis.

Business trends.

### 📄 5. Executive Business Reports


Automatically generates structured analytical insights:

Executive Business Summary.

Department Performance Analysis.

Business trends and performance gaps.

Data quality observations.

### 🎯 6. Strategic Recommendations


Generates five prioritized business recommendations:

🔴 HIGH – Critical improvements.

🟠 MEDIUM – Operational optimization.

🟢 LOW – Long-term improvements.

### ⚡ 7. Dataset Transformation Suite

Three analytical subtabs:

Dataset Summary – Rows, columns, data types, missing values and duplicates.

EDA Summary – Descriptive statistics, distributions and data quality.

Power Query Suite – 10 transformation tools.

#### 10 Data Transformation Tools

No.	Tool

1	Find & Replace

2	Split Column

3	Extract Text

4	Change Data Type

5	Filter Rows

6	Sort Data

7	Fill Values

8	Drop Columns

9	Column Operations

10	Data Transformation

### 📤 8. Data Export

Export processed datasets into:

CSV (.csv)

Excel (.xlsx)

SQLite (.db)

### 🛠️ Technology Stack
Category	Technologies

Language	Python 3.10–3.12

Backend	FastAPI, Uvicorn

Data Processing	Pandas, NumPy

File Processing	OpenPyXL, PyArrow

Database	SQLite3

AI Models	Groq, Gemini

Research APIs	DuckDuckGo, Wikipedia

Media	Wikimedia Commons

Frontend	HTML5, CSS3, JavaScript

Visualization	Chart.js

Voice	Web Speech API

Testing	Pytest

### ⚙️ Installation & Quick Start

#### 1. Clone Repository

bash

git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git

cd YOUR_REPOSITORY

#### 2. Create Virtual Environment

bash

python -m venv venv


Windows:

bash

venv\Scripts\activate


Mac / Linux:

bash

source venv/bin/activate

#### 3. Install Dependencies

bash

pip install -r requirements.txt

#### 4. Configure API Keys

Create a .env file:


env

GROQ_API_KEY=your_groq_api_key

GEMINI_API_KEY=your_gemini_api_key

#### 5. Run Application

bash

python app.py


The application supports configured port fallback:

text

8000 → 8001 → 8002


Open the application URL displayed in your terminal.

💻 VS Code Play & Debug

▶️ Run Application


Open the project in VS Code.

Open app.py.

Select your Python interpreter.

Click the Run button.

### 🐞 Debug Application

Open Run and Debug.

Configure Python debugging.

Set breakpoints.

Press F5.

Monitor execution in Debug Console.

Example .vscode/launch.json:

json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "RENSERI AI Assistant",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/app.py",
      "console": "integratedTerminal",
      "justMyCode": true
    }
  ]
}

### 🧪 Testing

Run the automated test suite:

bash

python -m pytest -v



<p align="center">
<img src="https://img.shields.io/badge/Total%20Tests-23-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/Passed-23-success?style=for-the-badge" />
<img src="https://img.shields.io/badge/Failed-0-critical?style=for-the-badge" />
</p>

Reported test status: 23/23 passing.

Run the command to verify the current codebase.

### 📁 Project Structure

renseri-ai-assistant/

├── app.py                      # Primary application entrypoint & browser launcher

├── run.py                      # Alternative launcher with automatic port discovery


├── requirements.txt            # Python dependencies (FastAPI, Pandas, Chart.js, etc.)

├── README.md                   # Complete GitHub documentation, architecture & quickstart

├── .env.example                # Example template showing required API key variable names

├── .gitignore                  # Git ignore rules (prevents uploading keys & cache)

│

├── app/                        # Main application source code


│   ├── __init__.py             # Package marker

│   ├── main.py                 # FastAPI app, API routing, endpoints

│   ├── assistant.py            # AI assistant routing (Groq LLaMA 3.3 + Gemini fallback)

│   ├── ai_config.py            # Dynamic AI settings & API key manager

│   ├── chatbot.py              # Context & conversational handler

│   ├── cleaner.py              # Ingestion engine & 10-module Power Query suite

│   ├── dashboard.py            # SQL aggregations, charts, & multi-point Executive Report

│   ├── db_engine.py            # Sandboxed SQLite execution & query safety guardrails

│   ├── nl2sql.py               # Natural language to SQL query translator

│   ├── samples.py              # Realistic sample datasets (Retail, HR, E-Commerce)

│   ├── voice.py                # Audio handling & voice transcription

│   ├── web_search.py           # DuckDuckGo search + Wikipedia entity & gallery fetcher

│   └── static/                 # Frontend assets (Zero node_modules required)

│       ├── index.html          # Web UI layout & ribbon navigation

│       ├── app.js              # Client state, event listeners, dashboard rendering

│       └── styles.css          # Dark glassmorphism stylesheet & responsive layout

│

├── tests/                      # Automated test suite (23 passing tests)

│   ├── test_api.py             # API endpoints & upload/export flow tests

│   ├── test_cleaner.py         # Data cleaning & type inference tests

│   └── test_nl2sql.py          # NL-to-SQL, guardrails, & search tests

│

└── .vscode/                    # (Recommended) 1-Click Play & Debug configs

├── launch.json             # F5 debugger setup

  ├── tasks.json              # VS Code run tasks
  
  └── settings.json           # Python interpreter settings


Adjust the structure to match your actual repository.

#### 🔐 Security

Never commit API keys or .env files.

Validate uploaded datasets.

Protect sensitive business information.

Restrict access to exported files.

### 🚀 Future Enhancements

Predictive analytics.

Anomaly detection.

Natural-language-to-SQL.

Power BI integration.

Automated PDF reports.

Cloud deployment.

Multi-user authentication.

### 🤝 Contributing

Contributions and suggestions are welcome!

bash

git checkout -b feature/your-feature-name

git add .

git commit -m "Add: new feature"

git push origin feature/your-feature-name


Submit a Pull Request to contribute.

### 📜 License

Distributed under the MIT License.

⭐ Support the Project

If you find RENSERI AI ASSISTANT useful:

⭐ Star the repository.

🍴 Fork the project.

🐛 Report bugs.

💡 Suggest improvements.

🤝 Contribute to development.


<p align="center">
<strong>🚀 RENSERI AI ASSISTANT</strong>
<br/>
<em>From Raw Data to Intelligent Business Decisions.</em>
<br/><br/>
Built with ❤️ using Python, AI & Business Intelligence.
</p>




<img width="945" height="435" alt="image" src="https://github.com/user-attachments/assets/ce4a8b8e-ac5b-4f57-afd2-020ff9b33209" />
