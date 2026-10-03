# Notion Job Tracker MCP Server 💼

A Model Context Protocol (MCP) server that empowers your AI assistant (like Claude Desktop or Antigravity) to track job applications, update application stages, log tailored CV notes, and review your pipeline directly in **Notion**.

---

## 🌟 Features

* **`track_job_application`**: Logs or updates an application with Company, Role, URL, Location, Status, CV file path (PDF/DOCX/URL), and structured body notes.
* **`attach_cv`**: Uploads and attaches a tailored CV file directly to an existing job application in Notion (disambiguates if multiple positions exist).
* **`update_job_status`**: Easily updates an application stage (e.g. from *Applied* to *Interview* or *Offer*) and appends timestamped interview notes.
* **`list_job_applications`**: Formats a Markdown overview table of all tracked applications (optionally filtered by status).
* **`get_job_details`**: Retrieves full notes, match points, attached CVs, and history for any company application.
* **`verify_notion_connection`**: Tests your Notion token and validates database property mapping (including the `CV` column).

---

## 🛠️ Setup Instructions

### 1. Notion Integration Token
1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations).
2. Click **+ New integration**.
3. Name it **`Job Tracker Agent`** and submit.
4. Copy the **Internal Integration Secret** (`ntn_...` or `secret_...`).

### 2. Notion Database Setup
1. In your Notion workspace, create a new full-page database called **`Job Applications`**.
2. Add the following properties (the server dynamically adapts to these):
   * **`Company`** &rarr; Type: **Title**
   * **`Role`** &rarr; Type: **Text**
   * **`Status`** &rarr; Type: **Select** (e.g. `Wishlist`, `Applied`, `Screening`, `Interview`, `Offer`, `Rejected`)
   * **`Job URL`** &rarr; Type: **URL**
   * **`Location / Type`** &rarr; Type: **Text** or **Select** (e.g. `Remote`, `Hybrid`, `Onsite`)
   * **`Applied Date`** &rarr; Type: **Date**
3. **Connect the database to your integration:**
   * In Notion, open the database page.
   * Click the **`...`** (top-right menu) &rarr; **Connections** &rarr; Search for and select your integration.
4. **Copy your Database ID:**
   * From your browser address bar:
     `https://www.notion.so/workspace/{DATABASE_ID}?v=...`
   * Copy the 32-character string `{DATABASE_ID}`.

### 3. Environment Configuration
Create a `.env` file in this directory:
```bash
cp .env.example .env
```
Fill in your credentials:
```env
NOTION_API_KEY=ntn_your_notion_integration_token_here
NOTION_JOB_TRACKER_DB_ID=your_32_character_database_id
```

---

## 🔌 Connecting to Claude Desktop

Add this server to your `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notion-job-tracker": {
      "command": "/home/ahmed-khalifa/Projects/Personal/notion-tracker-mcp/.venv/bin/python",
      "args": [
        "/home/ahmed-khalifa/Projects/Personal/notion-tracker-mcp/server.py"
      ],
      "env": {
        "NOTION_API_KEY": "ntn_your_token_here",
        "NOTION_JOB_TRACKER_DB_ID": "your_database_id_here"
      }
    }
  }
}
```

---

## 💬 Example Agent Prompts

* *"Can you verify my Notion connection?"*
* *"I just applied for Senior Backend Engineer at Acme Corp: https://acme.com/jobs/123. Location is Remote. Here is why my CV fits: 5 years Python experience and distributed systems expertise. Please log it to Notion."*
* *"Update Acme Corp status to Interview and note that I have a screening call this Thursday at 2 PM."*
* *"Show me all jobs currently in Interview status."*
