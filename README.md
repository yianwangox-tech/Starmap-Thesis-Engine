# 🌌 StarMap Thesis Engine

A local, AI-powered literature review and thesis management workspace. StarMap helps researchers and students organize academic papers, compute semantic similarities locally, and visualize literature relationships through interactive graphs—all while keeping API costs to an absolute minimum.

## ✨ Key Features

* **🔒 Privacy-First Local Embeddings:** Uses `Xenova/transformers.js` to run the `all-MiniLM-L6-v2` embedding model directly in your browser. This means semantic similarity comparisons (cosine similarity) cost zero API tokens and your reading data stays local.
* **🤖 Multi-LLM PDF Parsing:** Automatically extracts Title, Authors, Year, Abstract, and Keywords from uploaded PDFs. Compatible with Groq (Llama 3.1), Google Gemini, DeepSeek, and OpenAI.
* **🕸️ Interactive Visualizations:** Powered by ECharts, switch between three dynamic views:
    * *Orbital View:* Papers orbit your central "Target Thesis" based on semantic similarity.
    * *Network View:* A bi-directional force graph showing pairwise similarities between your top papers.
    * *Citation Graph:* A directed graph visualizing "who cited whom" using OpenAlex metadata.
* **🌐 Academic Metadata Enrichment:** Deep integration with OpenAlex and Crossref to auto-fill missing metadata, fetch citation counts, and build reference lists.
* **📚 Zotero Sync:** Connect your Zotero User ID and API Key to import collections directly into your workspace.
* **📝 Auto-Literature Review:** Automatically clusters your core papers into thematic groups and drafts a literature review based on your project's context.

## 🚀 Quick Start (Demo Ready)

This repository includes a pre-populated `database.db` so you can experience the visualization and semantic clustering right out of the box!

### Prerequisites
* Python 3.8 or higher
* A modern web browser (Chrome, Edge, Safari, Firefox)

### Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/ywangox-boop/Starmap-Thesis-Engine.git
   cd Starmap-Thesis-Engine
   
2. **Install the backend dependencies:** pip install fastapi uvicorn pydantic
3. **Start the backend server:** python main.py
And the server will start securely on http://127.0.0.1:8001.

4. Launch the Frontend:
Simply double-click the index.html file to open it in your web browser.

Using the Demo Dataset
Since a demo database is included, you can log in using the existing test account (or register a new one). Click on the existing project in the Dashboard to instantly see the interactive graphs and test the AI clustering tools.
(Note: You will need to configure your own LLM API keys in the dashboard to parse new PDFs or generate text).

## ⚙️ Configuration & Security
All external API configurations are managed securely from the Dashboard -> 🤖 AI Parser Settings:

LLM API Keys: Stored safely in your browser's localStorage. They are never saved to the SQLite database.

Zotero API: Required only if you wish to sync your remote reference library.

OpenAlex Email: We recommend adding your email to utilize the OpenAlex "Polite Pool" for faster metadata fetching.

🏗️ Tech Stack
Frontend: Vanilla HTML/CSS/JavaScript. No Node.js build steps required.

Backend: Python, FastAPI, SQLite (Lightweight and highly portable).

AI/ML: @xenova/transformers.js (Client-side embeddings).

Visualization: Apache ECharts.

PDF Processing: PDF.js.

🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

📄 License
This project is open-source and available under the MIT License.

   
