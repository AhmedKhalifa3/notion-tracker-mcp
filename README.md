# Notion Job Tracker MCP Server 💼

> An intelligent, autonomous Model Context Protocol (MCP) server that connects your AI assistant (Claude Desktop, Cursor, Antigravity) to Notion to track job applications, upload tailored CVs, compute pipeline analytics, draft recruiter follow-ups, and generate pre-interview cheat sheets.

---

## 🌟 Key Features

* 💼 **`track_job_application`**: Logs or updates applications with Company, Role, URL, Location, Status, Contact, Follow-up date, and structured notes. Distinguishes multiple roles at the same company!
* 📎 **`attach_cv`**: Direct binary upload of tailored CV files (`.pdf`, `.docx`, etc.) directly into Notion storage and page blocks.
* 📊 **`get_application_insights`**: Real-time pipeline dashboard computing:
  * Application counters (Applied, Screening, Interview, Offer, Rejected, Wishlist).
  * Positive response rate percentage.
  * Monthly application velocity.
  * Career domain breakdown (AI/ML, Backend, Data, DevOps, Fullstack).
  * Stale application alerts (> 14 days without an update).
* ✉️ **`draft_followup_message`**: Crafts tailored LinkedIn or Email follow-up notes referencing application dates and highlighted strengths.
* 🎯 **`generate_interview_prep`**: Instant pre-interview cheat sheet with a 30-second elevator pitch, key CV match points, likely technical questions, and reverse-interview questions.
* 🔄 **`update_job_status`**: Easily update stages (*Applied &rarr; Screening &rarr; Interview &rarr; Offer &rarr; Rejected*) and append timestamped notes.
* 📋 **`list_job_applications`**: Overview Markdown table of tracked applications with direct links.
* 🔍 **`get_job_details`**: Retrieves full notes, match points, and history for any company application.
* 📥 **`list_discovered_jobs`**: Queries freshly scouted leads from your Job Discovery Inbox database (filter by `New`, `Approved`, etc.).
* 🏷️ **`update_discovered_job_status`**: Marks discovery leads as `Approved`, `Dismissed`, or `Moved to Pipeline`.
* 🚀 **`run_job_scout`**: Runs the autonomous Job Scout scraper on demand to discover new openings from ATS systems (Personio, Ashby, Greenhouse, Lever).
* 🔌 **`verify_notion_connection`**: Validates Notion token and dynamic database schema mapping.

---

## 🔗 The Complete Career Pipeline: Pair with Overleaf CV Agent

This MCP server is designed to work hand-in-hand with [Overleaf CV Agent](https://github.com/AhmedKhalifa3/overleaf-cv-agent) to automate your entire application workflow:

```text
┌────────────────────────────────────────────────────────┐
│  AI Assistant (Claude Desktop / Cursor)                │
│  1. Analyzes target Job Description                    │
│  2. Tailors LaTeX resume to match JD keywords          │
└───────────────────────────┬────────────────────────────┘
                            │ Calls: compile_cv(role, latex)
                            ▼
┌────────────────────────────────────────────────────────┐
│  Overleaf CV Agent                                     │
│  • Compiles LaTeX via headless Overleaf cloud compiler │
│  • Saves ready-to-send PDF to local output             │
└───────────────────────────┬────────────────────────────┘
                            │ Returns: /path/to/tailored_cv.pdf
                            ▼
┌────────────────────────────────────────────────────────┐
│  Notion Job Tracker MCP                                │
│  • Calls: track_job_application(cv_file_path=...)      │
│  • Uploads PDF directly to Notion S3 storage           │
│  • Creates application card with status 'Applied'      │
│  • Categorizes role & logs match points                │
└───────────────────────────┬────────────────────────────┘
                            │ Persistent Tracking & Intelligence
                            ▼
┌────────────────────────────────────────────────────────┐
│  Your Notion Board & Career Cockpit                    │
│  • 1-Click PDF preview on Mobile & Desktop             │
│  • Real-time conversion & response analytics           │
│  • Pre-interview cheat sheets & recruiter follow-ups   │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ Setup Guide

### 1. Installation

```bash
git clone https://github.com/AhmedKhalifa3/notion-tracker-mcp.git
cd notion-tracker-mcp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

### 2. Notion Setup

1. **Create an Integration Token:**
   * Go to [notion.so/my-integrations](https://www.notion.so/my-integrations).
   * Click **+ New integration**, name it **`Job Tracker Agent`**, and submit.
   * Copy the **Internal Integration Secret** (`ntn_...`).

2. **Create the Database in Notion:**
   * Create a new full-page database called **`Job Applications`**.
   * Add the following columns (the server dynamically adapts to your naming):
     | Column Name | Notion Property Type | Purpose |
     | :--- | :--- | :--- |
     | **`Company 1`** | Title | Company Name |
     | **`Role`** | Text / Rich Text | Job Title |
     | **`Status`** | Select | `Wishlist`, `Applied`, `Screening`, `Interview`, `Offer`, `Rejected` |
     | **`Job URL`** | URL | Link to job posting |
     | **`Location / Type`** | Text | Remote / Hybrid / Onsite |
     | **`Applied Date`** | Date | Date submitted |
     | **`Priority`** | Select | High / Medium / Low |
     | **`Contact`** | Text | Recruiter / Hiring Manager name or email |
     | **`Next follow-up`** | Date | Next scheduled touchpoint |
     | **`CV`** | Files & media | Uploaded PDF / DOCX resume |
     | **`Notes`** | Text | High-level notes |

3. **Share with Integration:**
   * Click the **`...`** (top-right menu) on the database page &rarr; **Connections** &rarr; Connect to **`Job Tracker Agent`**.
   * Copy the 32-character **Database ID** from the page URL:
     `https://www.notion.so/workspace/{DATABASE_ID}?v=...`

---

### 3. Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```
Add your credentials:
```env
NOTION_API_KEY=ntn_your_notion_integration_token_here
NOTION_JOB_TRACKER_DB_ID=your_32_character_database_id_here
```

---

## 🔌 Connecting to Claude Desktop

Add this server to your `claude_desktop_config.json`:
* **Linux**: `~/.config/Claude/claude_desktop_config.json`
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "notion-job-tracker": {
      "command": "/absolute/path/to/notion-tracker-mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/notion-tracker-mcp/server.py"
      ]
    }
  }
}
```

*(Restart Claude Desktop completely after editing the configuration).*

---

## 💬 Example Agent Prompts

### 1. End-to-End Application Logging with CV
> *"I just applied to Stripe for Senior AI Engineer: https://stripe.com/jobs/123. Location is Remote. Log it to Notion as Applied, note my background with distributed systems, and attach my compiled CV from `/path/to/stripe_cv.pdf`."*

### 2. Multi-Role Disambiguation
> *"I got an interview at Stripe!"*
> *(If multiple roles exist at Stripe, Claude prompts which role to update, updating only the target position).*

### 3. Analytics & Pipeline Insights
> *"Show me my job hunt analytics and stats."*
> *(Returns total submitted, active interviews, response rate %, monthly velocity, and stale applications).*

### 4. Recruiter Follow-Up Drafter
> *"Draft a LinkedIn follow-up note for the recruiter at Stripe for my AI Engineer application."*

### 5. Pre-Interview Cheat Sheet
> *"I have an interview with Google for Senior Backend Engineer tomorrow. Prep me with an elevator pitch, my key CV points, and technical questions."*

---

## 📄 License

MIT License. Free to use and customize for your career search!
