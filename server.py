"""
Notion Job Tracker MCP Server
A Model Context Protocol server that tracks job applications in Notion.
Supports both classic Notion databases and Notion's Data Sources architecture.
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

def clean_id(raw_id: str) -> str:
    if not raw_id:
        return ""
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

# In-memory cache for schema and data_source_id
_SCHEMA_CACHE: Dict[str, Any] = {}

def inspect_database_schema(client: Client, db_id: str) -> Dict[str, Any]:
    """Inspects the database schema (supporting both classic and data_sources models)."""
    global _SCHEMA_CACHE
    if db_id in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[db_id]

    try:
        db = client.databases.retrieve(database_id=db_id)
        props = db.get("properties") or {}
        data_source_id = None

        # Handle Notion's data_sources API model
        data_sources = db.get("data_sources") or []
        if not props and data_sources:
            ds_info = data_sources[0]
            data_source_id = ds_info.get("id")
            if data_source_id:
                ds = client.data_sources.retrieve(data_source_id=data_source_id)
                props = ds.get("properties") or {}

        schema = {
            "data_source_id": data_source_id,
            "title_prop": None,
            "role_prop": None,
            "status_prop": None,
            "url_prop": None,
            "date_prop": None,
            "location_prop": None,
            "notes_prop": None,
            "priority_prop": None,
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
                if any(k in lower_name for k in ["applied", "date", "created"]):
                    schema["date_prop"] = name
            elif prop_type in ("select", "status") and not schema["status_prop"] and any(k in lower_name for k in ["status", "stage", "state"]):
                schema["status_prop"] = name
                opts = data.get(prop_type, {}).get("options", [])
                schema["status_options"] = [opt.get("name") for opt in opts]
            elif prop_type == "select" and "priority" in lower_name and not schema["priority_prop"]:
                schema["priority_prop"] = name
            elif prop_type in ("rich_text", "select") and not schema["role_prop"] and any(k in lower_name for k in ["role", "position", "title", "job"]):
                schema["role_prop"] = name
            elif prop_type in ("rich_text", "select") and not schema["location_prop"] and any(k in lower_name for k in ["location", "type", "place", "workplace"]):
                schema["location_prop"] = name
            elif prop_type == "rich_text" and not schema["notes_prop"] and "note" in lower_name:
                schema["notes_prop"] = name

        # Fallbacks if title or status weren't matched by keyword
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

        if not schema["date_prop"]:
            for name, data in props.items():
                if data.get("type") == "date":
                    schema["date_prop"] = name
                    break

        _SCHEMA_CACHE[db_id] = schema
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
    """Builds structured Notion blocks for the page body."""
    blocks: List[Dict[str, Any]] = []

    overview_text = []
    if location:
        overview_text.append(f"📍 Location: {location}")
    if job_url:
        overview_text.append(f"🔗 Job Link: {job_url}")
    overview_text.append(f"📅 Added on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": "\n".join(overview_text)}}],
            "icon": {"type": "emoji", "emoji": "💼"}
        }
    })

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
    """Helper to query database pages across notion-client versions and data_sources."""
    schema = inspect_database_schema(client, db_id)
    ds_id = schema.get("data_source_id")

    kwargs: Dict[str, Any] = {}
    if query_filter:
        kwargs["filter"] = query_filter

    if ds_id:
        try:
            res = client.data_sources.query(data_source_id=ds_id, **kwargs)
            return res.get("results", [])
        except Exception:
            pass

    # Standard database endpoint fallback
    body = {}
    if query_filter:
        body["filter"] = query_filter
    try:
        res = client.request(path=f"databases/{db_id}/query", method="POST", body=body)
        return res.get("results", [])
    except Exception as e:
        raise e

# --- MCP Tools ---

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
            f"- Role Property: {schema.get('role_prop') or 'Not found'}\n"
            f"- Status Property: {schema.get('status_prop') or 'Not found'}\n"
            f"- URL Property: {schema.get('url_prop') or 'Not found'}\n"
            f"- Date Property: {schema.get('date_prop') or 'Not found'}\n"
            f"- Location Property: {schema.get('location_prop') or 'Not found'}\n"
            f"- Notes Property: {schema.get('notes_prop') or 'Not found'}\n"
            f"- Priority Property: {schema.get('priority_prop') or 'Not found'}\n"
            f"- Status Options: {', '.join(schema.get('status_options', [])) or 'None'}"
        )
    except Exception as e:
        return (
            f"❌ Connection failed: {str(e)}\n\n"
            "Please check:\n"
            "1. NOTION_API_KEY starts with 'ntn_' or 'secret_'.\n"
            "2. NOTION_JOB_TRACKER_DB_ID is the correct 32-character database ID.\n"
            "3. You have shared the database with your Notion integration (click '...' -> 'Connections' -> Add integration)."
        )

def get_page_role(page: Dict[str, Any], role_prop: Optional[str]) -> str:
    """Helper to extract plain text role from a Notion page."""
    if not role_prop:
        return ""
    props = page.get("properties", {})
    r_data = props.get(role_prop, {})
    if r_data.get("type") == "rich_text":
        texts = r_data.get("rich_text", [])
        return texts[0].get("plain_text", "").strip() if texts else ""
    elif r_data.get("type") == "select" and r_data.get("select"):
        return r_data["select"].get("name", "").strip()
    return ""

def get_page_company(page: Dict[str, Any], title_prop: str) -> str:
    """Helper to extract plain text company name from a Notion page."""
    props = page.get("properties", {})
    t_data = props.get(title_prop, {})
    titles = t_data.get("title", [])
    return titles[0].get("plain_text", "").strip() if titles else ""

def get_page_status(page: Dict[str, Any], status_prop: Optional[str]) -> str:
    """Helper to extract status string from a Notion page."""
    if not status_prop:
        return "-"
    props = page.get("properties", {})
    s_data = props.get(status_prop, {})
    if s_data.get("type") == "select" and s_data.get("select"):
        return s_data["select"].get("name", "-")
    elif s_data.get("type") == "status" and s_data.get("status"):
        return s_data["status"].get("name", "-")
    return "-"

@app.tool(
    name="track_job_application",
    description="Logs a new job application or updates an existing one in Notion with company, role, URL, status, location, and rich notes."
)
def track_job_application(
    company: str,
    role: str,
    job_url: str = "",
    status: str = "Applied",
    location: str = "",
    priority: str = "",
    applied_date: str = "",
    summary: str = "",
    match_points: Optional[List[str]] = None,
    notes: str = ""
) -> str:
    """Tracks a job application in the Notion database, distinguishing multiple roles per company."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")
        status_prop = schema.get("status_prop")
        url_prop = schema.get("url_prop")
        date_prop = schema.get("date_prop")
        location_prop = schema.get("location_prop")
        notes_prop = schema.get("notes_prop")
        priority_prop = schema.get("priority_prop")

        # Search all pages matching this company name
        existing_pages = query_database_pages(
            client,
            db_id,
            query_filter={
                "property": title_prop,
                "title": {"contains": company}
            }
        )

        # Check if the specific role at this company already exists
        target_page_id = None
        for page in existing_pages:
            existing_company = get_page_company(page, title_prop)
            if existing_company.lower() == company.lower():
                existing_role = get_page_role(page, role_prop)
                # If roles match (case-insensitive) or neither has a role specified
                if role and existing_role and (role.lower() == existing_role.lower()):
                    target_page_id = page["id"]
                    break
                elif not role and not existing_role:
                    target_page_id = page["id"]
                    break

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

        if notes_prop and notes:
            properties[notes_prop] = {
                "rich_text": [{"type": "text", "text": {"content": notes}}]
            }

        if priority_prop and priority:
            properties[priority_prop] = {
                "select": {"name": priority}
            }

        blocks = build_notion_blocks(
            summary=summary,
            match_points=match_points,
            notes=notes,
            job_url=job_url,
            location=location
        )

        if target_page_id:
            # Update the specific existing position
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
            return f"✅ Updated existing application for **{company}** - **{role or 'General'}** with status **{status}** in Notion."
        else:
            # Create a new, distinct entry for this role
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
    description="Updates the status of an existing job application (e.g. Wishlist, Applied, Screening, Interview, Offer, Rejected) and appends notes. If multiple roles exist for a company, specify 'role' to disambiguate."
)
def update_job_status(
    company: str,
    new_status: str,
    role: str = "",
    update_notes: str = ""
) -> str:
    """Updates status and appends notes to a specific job application, disambiguating multiple roles."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")
        status_prop = schema.get("status_prop")

        if not status_prop:
            return "❌ No status property found in Notion database schema."

        # Find matching pages
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

        # Filter strictly for the company
        company_pages = [p for p in results if company.lower() in get_page_company(p, title_prop).lower()]

        if not company_pages:
            return f"❌ Could not find an application matching '{company}' in Notion."

        target_page = None

        if len(company_pages) == 1:
            target_page = company_pages[0]
        else:
            # Multiple positions exist at this company!
            if role:
                for p in company_pages:
                    p_role = get_page_role(p, role_prop)
                    if role.lower() in p_role.lower():
                        target_page = p
                        break
            
            if not target_page:
                # Disambiguate for the user
                listing = []
                for p in company_pages:
                    p_role = get_page_role(p, role_prop) or "Role unspecified"
                    p_status = get_page_status(p, status_prop)
                    listing.append(f"- **{p_role}** (Current Status: `{p_status}`)")
                
                return (
                    f"⚠️ Found {len(company_pages)} different positions at **{company}** in your tracker:\n"
                    + "\n".join(listing)
                    + f"\n\nPlease specify which role to update to **{new_status}** (e.g. `role='{get_page_role(company_pages[0], role_prop)}'`)."
                )

        page_id = target_page["id"]
        matched_role = get_page_role(target_page, role_prop) or role

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

        role_label = f" ({matched_role})" if matched_role else ""
        return f"✅ Status for **{company}**{role_label} updated to **{new_status}**."
    except Exception as e:
        return f"❌ Failed to update job status: {str(e)}"

@app.tool(
    name="get_job_details",
    description="Retrieves the detailed notes and status of a specific job application from Notion. Specify role if multiple positions exist at that company."
)
def get_job_details(company: str, role: str = "") -> str:
    """Retrieves full details and blocks for a job application, supporting multiple roles."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")
        status_prop = schema.get("status_prop")

        results = query_database_pages(
            client,
            db_id,
            query_filter={
                "property": title_prop,
                "title": {"contains": company}
            }
        )

        company_pages = [p for p in results if company.lower() in get_page_company(p, title_prop).lower()]

        if not company_pages:
            return f"❌ No application found for company '{company}' in Notion."

        target_page = None
        if len(company_pages) == 1:
            target_page = company_pages[0]
        else:
            if role:
                for p in company_pages:
                    if role.lower() in get_page_role(p, role_prop).lower():
                        target_page = p
                        break
            
            if not target_page:
                summary_lines = [f"Found {len(company_pages)} positions at **{company}**:"]
                for p in company_pages:
                    p_role = get_page_role(p, role_prop) or "Role unspecified"
                    p_status = get_page_status(p, status_prop)
                    summary_lines.append(f"- **{p_role}** (`{p_status}`)")
                summary_lines.append(f"\nPlease specify which role you'd like to inspect (e.g. role='{get_page_role(company_pages[0], role_prop)}').")
                return "\n".join(summary_lines)

        page_id = target_page["id"]
        matched_role = get_page_role(target_page, role_prop)

        blocks_res = client.blocks.children.list(block_id=page_id)
        blocks = blocks_res.get("results", [])

        details = [f"## 🏢 Job Details for {company}" + (f" - {matched_role}" if matched_role else "") + "\n"]
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
