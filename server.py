"""
Notion Job Tracker MCP Server
A Model Context Protocol server that tracks job applications in Notion.
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from notion_client import Client

# Load environment variables from .env if present
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_JOB_TRACKER_DB_ID = os.getenv("NOTION_JOB_TRACKER_DB_ID", "")

# Clean database ID (strip dashes or URL components if user pasted a full URL)
def clean_id(raw_id: str) -> str:
    if not raw_id:
        return ""
    # If a full URL was provided, extract the 32-hex character ID
    cleaned = raw_id.split("?")[0].rstrip("/").split("/")[-1].replace("-", "")
    return cleaned

NOTION_JOB_TRACKER_DB_ID = clean_id(NOTION_JOB_TRACKER_DB_ID)

# Initialize MCP Server
app = MCPServer("notion-job-tracker")

def get_notion_client() -> Client:
    api_key = os.getenv("NOTION_API_KEY", NOTION_API_KEY)
    if not api_key:
        raise ValueError("NOTION_API_KEY is not set. Please set it in your .env or environment.")
    return Client(auth=api_key)

def get_db_id() -> str:
    db_id = clean_id(os.getenv("NOTION_JOB_TRACKER_DB_ID", NOTION_JOB_TRACKER_DB_ID))
    if not db_id:
        raise ValueError("NOTION_JOB_TRACKER_DB_ID is not set. Please set it in your .env or environment.")
    return db_id

def inspect_database_schema(client: Client, db_id: str) -> Dict[str, Any]:
    """Inspects the database schema to dynamically map property names and types."""
    try:
        db = client.databases.retrieve(database_id=db_id)
        props = db.get("properties", {})
        
        schema = {
            "title_prop": None,
            "role_prop": None,
            "status_prop": None,
            "url_prop": None,
            "date_prop": None,
            "location_prop": None,
            "status_options": []
        }
        
        for name, data in props.items():
            prop_type = data.get("type")
            lower_name = name.lower()
            
            if prop_type == "title" and not schema["title_prop"]:
                schema["title_prop"] = name
            elif prop_type == "url" and not schema["url_prop"]:
                schema["url_prop"] = name
            elif prop_type == "date" and not schema["date_prop"]:
                schema["date_prop"] = name
            elif prop_type in ("select", "status") and not schema["status_prop"]:
                if any(k in lower_name for k in ["status", "stage", "state"]):
                    schema["status_prop"] = name
                    opts = data.get(prop_type, {}).get("options", [])
                    schema["status_options"] = [opt.get("name") for opt in opts]
            elif prop_type in ("rich_text", "select") and not schema["role_prop"]:
                if any(k in lower_name for k in ["role", "position", "title", "job"]):
                    schema["role_prop"] = name
            elif prop_type in ("rich_text", "select") and not schema["location_prop"]:
                if any(k in lower_name for k in ["location", "type", "place", "workplace"]):
                    schema["location_prop"] = name

        # Fallbacks if specific matches weren't found by keyword
        if not schema["title_prop"]:
            for name, data in props.items():
                if data.get("type") == "title":
                    schema["title_prop"] = name
                    break

        if not schema["status_prop"]:
            for name, data in props.items():
                if data.get("type") in ("select", "status"):
                    schema["status_prop"] = name
                    opts = data.get(data.get("type"), {}).get("options", [])
                    schema["status_options"] = [opt.get("name") for opt in opts]
                    break

        return schema
    except Exception as e:
        raise RuntimeError(f"Error inspecting Notion database ({db_id}): {str(e)}")

def build_notion_blocks(
    summary: str = "",
    match_points: Optional[List[str]] = None,
    notes: str = "",
    job_url: str = "",
    location: str = ""
) -> List[Dict[str, Any]]:
    """Builds clean, structured Notion blocks for the page body."""
    blocks: List[Dict[str, Any]] = []

    # Overview Callout
    overview_text = []
    if location:
        overview_text.append(f"📍 **Location:** {location}")
    if job_url:
        overview_text.append(f"🔗 **Job Link:** {job_url}")
    overview_text.append(f"📅 **Added on:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": "\n".join(overview_text)}}],
            "icon": {"type": "emoji", "emoji": "💼"}
        }
    })

    # Summary
    if summary:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📌 Role Overview"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": summary}}]
            }
        })

    # Key Match Points / Tailoring Notes
    if match_points:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "🎯 Key Match Points & Tailoring"}}]
            }
        })
        for pt in match_points:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": pt}}]
                }
            })

    # Notes & Follow-ups
    if notes:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📝 Notes & Next Steps"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": notes}}]
            }
        })

    return blocks

def query_database_pages(client: Client, db_id: str, query_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Helper to query database pages across notion-client versions."""
    body = {}
    if query_filter:
        body["filter"] = query_filter
    try:
        # Standard Notion database query endpoint
        res = client.request(path=f"databases/{db_id}/query", method="POST", body=body)
        return res.get("results", [])
    except Exception as e:
        # Fallback to data_sources.query if available
        try:
            res = client.data_sources.query(data_source_id=db_id, **body)
            return res.get("results", [])
        except Exception:
            raise e

# --- Tools ---

@app.tool(name="verify_notion_connection", description="Checks the Notion API key and database connection, reporting configured properties.")
def verify_notion_connection() -> str:
    """Verifies that the Notion API key and database ID are valid and connected."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)
        
        return (
            "✅ Successfully connected to Notion!\n"
            f"- Database ID: {db_id}\n"
            f"- Title Property: {schema.get('title_prop') or 'Not found'}\n"
            f"- Role Property: {schema.get('role_prop') or 'Not configured (will use body)'}\n"
            f"- Status Property: {schema.get('status_prop') or 'Not found'}\n"
            f"- URL Property: {schema.get('url_prop') or 'Not configured (will use body)'}\n"
            f"- Date Property: {schema.get('date_prop') or 'Not configured'}\n"
            f"- Location Property: {schema.get('location_prop') or 'Not configured'}\n"
            f"- Detected Status Options: {', '.join(schema.get('status_options', [])) or 'None'}"
        )
    except Exception as e:
        return (
            f"❌ Connection failed: {str(e)}\n\n"
            "Please check:\n"
            "1. NOTION_API_KEY starts with 'ntn_' or 'secret_'.\n"
            "2. NOTION_JOB_TRACKER_DB_ID is the correct 32-character database ID.\n"
            "3. You have shared the database with your Notion integration (click '...' -> 'Connections' -> Add integration)."
        )

@app.tool(
    name="track_job_application",
    description="Logs a new job application or updates an existing one in Notion with company, role, URL, status, and rich notes."
)
def track_job_application(
    company: str,
    role: str,
    job_url: str = "",
    status: str = "Applied",
    location: str = "",
    applied_date: str = "",
    summary: str = "",
    match_points: Optional[List[str]] = None,
    notes: str = ""
) -> str:
    """Tracks a job application in the Notion database."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company") or "Company"
        role_prop = schema.get("role_prop")
        status_prop = schema.get("status_prop")
        url_prop = schema.get("url_prop")
        date_prop = schema.get("date_prop")
        location_prop = schema.get("location_prop")

        # Check if this company & role already exists
        existing_pages = query_database_pages(
            client,
            db_id,
            query_filter={
                "property": title_prop,
                "title": {"equals": company}
            }
        )

        target_page_id = None
        for page in existing_pages:
            target_page_id = page["id"]
            break

        # Prepare properties payload
        properties: Dict[str, Any] = {
            title_prop: {
                "title": [{"type": "text", "text": {"content": company}}]
            }
        }

        if role_prop and role:
            properties[role_prop] = {
                "rich_text": [{"type": "text", "text": {"content": role}}]
            }

        if status_prop and status:
            properties[status_prop] = {
                "select": {"name": status}
            }

        if url_prop and job_url:
            properties[url_prop] = {"url": job_url}

        if date_prop:
            d_val = applied_date if applied_date else datetime.now().strftime("%Y-%m-%d")
            properties[date_prop] = {"date": {"start": d_val}}

        if location_prop and location:
            properties[location_prop] = {
                "rich_text": [{"type": "text", "text": {"content": location}}]
            }

        blocks = build_notion_blocks(
            summary=summary,
            match_points=match_points,
            notes=notes,
            job_url=job_url,
            location=location
        )

        if target_page_id:
            # Update existing page properties and append a timestamped update note
            client.pages.update(page_id=target_page_id, properties=properties)
            
            update_block = [
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": f"🔄 Updated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"}}]
                    }
                }
            ]
            if notes:
                update_block.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": notes}}]}
                })
            
            client.blocks.children.append(block_id=target_page_id, children=update_block)
            return f"✅ Updated existing application for **{company}** ({role or 'Role'}) with status **{status}** in Notion."
        else:
            # Create new page
            new_page = client.pages.create(
                parent={"database_id": db_id},
                properties=properties,
                children=blocks
            )
            page_url = new_page.get("url", "")
            return f"✅ Logged new application: **{company}** - **{role}** (Status: *{status}*).\nNotion URL: {page_url}"

    except Exception as e:
        return f"❌ Failed to track job application: {str(e)}"

@app.tool(
    name="update_job_status",
    description="Updates the status of an existing job application (e.g. Wishlist, Applied, Screening, Interview, Offer, Rejected) and appends notes."
)
def update_job_status(
    company: str,
    new_status: str,
    role: str = "",
    update_notes: str = ""
) -> str:
    """Updates status and appends notes to an existing job application."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company") or "Company"
        status_prop = schema.get("status_prop")

        if not status_prop:
            return "❌ No status property found in Notion database schema."

        # Search for the company
        results = query_database_pages(
            client,
            db_id,
            query_filter={
                "property": title_prop,
                "title": {"equals": company}
            }
        )

        if not results:
            # Try contains if exact match didn't find anything
            results = query_database_pages(
                client,
                db_id,
                query_filter={
                    "property": title_prop,
                    "title": {"contains": company}
                }
            )

        if not results:
            return f"❌ Could not find an existing application for company '{company}' in Notion."

        page = results[0]
        page_id = page["id"]

        # Update status
        client.pages.update(
            page_id=page_id,
            properties={
                status_prop: {"select": {"name": new_status}}
            }
        )

        # Append notes if provided
        if update_notes:
            note_blocks = [
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": f"📌 Status changed to {new_status} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"}
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": update_notes}}]
                    }
                }
            ]
            client.blocks.children.append(block_id=page_id, children=note_blocks)

        return f"✅ Status for **{company}** updated to **{new_status}**."
    except Exception as e:
        return f"❌ Failed to update job status: {str(e)}"

@app.tool(
    name="list_job_applications",
    description="Lists tracked job applications from Notion, optionally filtering by status (e.g. 'Interview', 'Applied')."
)
def list_job_applications(status_filter: str = "") -> str:
    """Lists tracked job applications with their status, role, and URL."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company") or "Company"
        role_prop = schema.get("role_prop")
        status_prop = schema.get("status_prop")
        url_prop = schema.get("url_prop")

        query_filter = None
        if status_filter and status_prop:
            query_filter = {
                "property": status_prop,
                "select": {"equals": status_filter}
            }

        pages = query_database_pages(client, db_id, query_filter)
        if not pages:
            msg = "No job applications found"
            if status_filter:
                msg += f" with status '{status_filter}'"
            return msg + " in your Notion tracker."

        output = [f"### 📋 Job Applications Tracker ({len(pages)} entries)\n"]
        output.append("| Company | Role | Status | Job URL |")
        output.append("| :--- | :--- | :--- | :--- |")

        for page in pages:
            props = page.get("properties", {})

            # Company / Title
            company_title_list = props.get(title_prop, {}).get("title", [])
            company = company_title_list[0].get("plain_text", "Unnamed") if company_title_list else "Unnamed"

            # Role
            role = "-"
            if role_prop and role_prop in props:
                role_texts = props[role_prop].get("rich_text", [])
                if role_texts:
                    role = role_texts[0].get("plain_text", "-")

            # Status
            status = "-"
            if status_prop and status_prop in props:
                st_data = props[status_prop]
                if st_data.get("type") == "select" and st_data.get("select"):
                    status = st_data["select"].get("name", "-")
                elif st_data.get("type") == "status" and st_data.get("status"):
                    status = st_data["status"].get("name", "-")

            # URL
            url = "-"
            if url_prop and url_prop in props:
                raw_url = props[url_prop].get("url")
                if raw_url:
                    url = f"[Link]({raw_url})"

            output.append(f"| **{company}** | {role} | `{status}` | {url} |")

        return "\n".join(output)
    except Exception as e:
        return f"❌ Failed to list applications: {str(e)}"

@app.tool(
    name="get_job_details",
    description="Retrieves the detailed notes and status of a specific job application from Notion."
)
def get_job_details(company: str) -> str:
    """Retrieves full details and blocks for a job application."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company") or "Company"

        results = query_database_pages(
            client,
            db_id,
            query_filter={
                "property": title_prop,
                "title": {"contains": company}
            }
        )

        if not results:
            return f"❌ No application found for company '{company}' in Notion."

        page = results[0]
        page_id = page["id"]

        # Retrieve blocks
        blocks_res = client.blocks.children.list(block_id=page_id)
        blocks = blocks_res.get("results", [])

        details = [f"## 🏢 Job Details for {company}\n"]
        for block in blocks:
            b_type = block.get("type", "")
            data = block.get(b_type, {})
            text_items = data.get("rich_text", [])
            text_content = "".join([t.get("plain_text", "") for t in text_items])

            if b_type.startswith("heading_"):
                details.append(f"\n### {text_content}\n")
            elif b_type == "bulleted_list_item":
                details.append(f"* {text_content}")
            elif b_type == "callout":
                details.append(f"> 💡 {text_content}")
            elif b_type == "paragraph" and text_content:
                details.append(text_content)

        return "\n".join(details)
    except Exception as e:
        return f"❌ Failed to retrieve job details: {str(e)}"

if __name__ == "__main__":
    app.run(transport="stdio")
