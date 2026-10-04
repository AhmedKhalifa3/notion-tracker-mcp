# Notion Job Tracker MCP Server 💼

> An intelligent, autonomous Model Context Protocol (MCP) server that connects your AI assistant (Claude Desktop, Cursor, Antigravity) to Notion to scout fresh job leads, track applications, upload tailored CVs, compute pipeline analytics, draft recruiter follow-ups, and generate pre-interview cheat sheets.

---

## 🌟 Key Features

* 📥 **`list_discovered_jobs`**: Queries freshly scouted leads from your Job Discovery Inbox database (filter by `New`, `Approved`, etc.).
* 🏷️ **`update_discovered_job_status`**: Marks discovery leads as `Approved`, `Dismissed`, or `Moved to Pipeline`.
* 🚀 **`run_job_scout`**: Runs the autonomous Job Scout scraper on demand to discover new openings from ATS systems (Personio, Ashby, Greenhouse, Lever).
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
* 🔌 **`verify_notion_connection`**: Validates Notion token and dynamic database schema mapping.

---

## 🔗 The Complete Autonomous Career Pipeline

This MCP server serves as the central cockpit connecting your discovery tools and CV compiler:

```text
┌────────────────────────────────────────────────────────┐
│  1. Job Discovery Scout (job-discovery-inbox)          │
│  • Precision ATS dorks: Personio, Ashby, Greenhouse    │
│  • Automatic filtering & scoring                       │
└───────────────────────────┬────────────────────────────┘
                            │ Pushes leads with Status 'New'
                            ▼
┌────────────────────────────────────────────────────────┐
│  2. Notion Job Tracker MCP (This Server)               │
│  • Database 1: Discovery Inbox (Vetting & triage)      │
│  • Database 2: Applications Tracker (Active stages)    │
└───────────────────────────┬────────────────────────────┘
                            │ Select approved role to apply
                            ▼
┌────────────────────────────────────────────────────────┐
│  3. Overleaf CV Agent (overleaf-cv-agent)              │
│  • Analyzes JD keywords & rewrites LaTeX resume        │
│  • Headless CLSI compilation to ready-to-send PDF      │
└───────────────────────────┬────────────────────────────┘
                            │ Returns compiled PDF path
                            ▼
┌────────────────────────────────────────────────────────┐
│  4. Central Cockpit in Notion                          │
│  • Automatically attaches PDF to application card      │
│  • Updates status to 'Applied'                         │
│  • Computes live conversion rates & preps interviews   │
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

2. **Database 1: `Job Applications` (Main Tracker)**
   * Create a full-page database named **`Job Applications`**.
   * Add the following columns (schema dynamically adapts to your naming):
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

   * Share with integration: Click **`...`** (top right) &rarr; **Connections** &rarr; Connect to **`Job Tracker Agent`**.
   * Copy the 32-character **Database ID** from the URL.

3. **Database 2: `Job Discovery Inbox` (Lead Discovery)** *(Recommended)*
   * Create a second full-page database named **`Job Discovery Inbox`**.
   * Add the following columns:
     | Column Name | Notion Property Type | Purpose |
     | :--- | :--- | :--- |
     | **`Company`** | Title | Company Name |
     | **`Role`** | Text | Job Title |
     | **`Job URL`** | URL | Link to posting |
     | **`Location`** | Text | Remote / City / Country |
     | **`Category`** | Select | `Werkstudent`, `Ai Agents`, `Sdet Qa`, `Backend` |
     | **`Score`** | Number | Match Score (1–5) |
     | **`Status`** | Select | `New`, `Approved`, `Dismissed`, `Moved to Pipeline` |
     | **`Date`** | Date | Discovery date |
     | **`Notes`** | Text | Job snippet & match rationale |

   * Share with integration: Click **`...`** (top right) &rarr; **Connections** &rarr; Connect to **`Job Tracker Agent`**.
   * Copy the 32-character **Discovery Database ID** from the URL.

---

### 3. Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` with your credentials:
```env
NOTION_API_KEY=ntn_your_notion_integration_token_here
NOTION_JOB_TRACKER_DB_ID=your_applications_tracker_database_id_here
NOTION_DISCOVERED_JOBS_DB_ID=your_discovered_jobs_database_id_here
```

---

## 🔌 Connecting to Claude Desktop / Cursor / Antigravity

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

*(Restart Claude Desktop or your IDE after editing the configuration).*

---

## 💬 Example Agent Prompts

### 1. Triage Newly Discovered Jobs
> *"Claude, check my Job Discovery Inbox for any new roles found today."*
*(Claude calls `list_discovered_jobs(status_filter="New")` and returns a summary table of leads).*

### 2. End-to-End Discovery to Application
> *"Let's apply to the top match at Stripe from my Discovery Inbox:*
> 1. *Read the job requirements from the link.*
> 2. *Tailor my LaTeX CV to highlight distributed systems and Python.*
> 3. *Compile the PDF with Overleaf CV Agent.*
> 4. *Log it to my Job Applications Tracker as 'Applied' with the compiled PDF attached.*
> 5. *Mark the lead in my Discovery Inbox as 'Approved'."*

### 3. Run Autonomous Job Scout from Chat
> *"Claude, run the Job Scout for the past 24 hours in the 'werkstudent' category."*
*(Claude invokes `run_job_scout`, scrapes live ATS postings, and syncs them to your Notion inbox).*

### 4. Application Logging & Status Updates
> *"I just had a phone screening with Spotify. Update my Spotify application to 'Interview' and add a note that the technical round is next Wednesday."*

### 5. Analytics & Pipeline Insights
> *"Show me my job hunt analytics and response rates."*
*(Returns total submitted, active interviews, response rate %, monthly velocity, and stale applications).*

### 6. Recruiter Follow-Up Drafter
> *"Draft a LinkedIn follow-up note for the recruiter at Stripe for my AI Engineer application."*

### 7. Pre-Interview Cheat Sheet
> *"I have an interview with Google tomorrow for Backend Engineer. Prep me with an elevator pitch, my key CV points, and technical questions."*

---

## 📄 License

MIT License. Free to use and customize for your career search!
