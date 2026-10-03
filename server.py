"""
Notion Job Tracker MCP Server
A Model Context Protocol server that tracks job applications in Notion.
Supports both classic Notion databases and Notion's Data Sources architecture.
"""

import os
import sys
import mimetypes
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
            "cv_prop": None,
            "contact_prop": None,
            "followup_prop": None,
            "domain_prop": None,
            "status_options": []
        }

        for name, data in props.items():
            prop_type = data.get("type")
            lower_name = name.lower()

            if prop_type == "title" and not schema["title_prop"]:
                schema["title_prop"] = name
            elif prop_type == "url" and not schema["url_prop"]:
                schema["url_prop"] = name
            elif prop_type == "date" and not schema["followup_prop"] and any(k in lower_name for k in ["follow", "next"]):
                schema["followup_prop"] = name
            elif prop_type == "date" and not schema["date_prop"]:
                if any(k in lower_name for k in ["applied", "date", "created"]):
                    schema["date_prop"] = name
            elif prop_type in ("select", "status") and not schema["status_prop"] and any(k in lower_name for k in ["status", "stage", "state"]):
                schema["status_prop"] = name
                opts = data.get(prop_type, {}).get("options", [])
                schema["status_options"] = [opt.get("name") for opt in opts]
            elif prop_type == "select" and "priority" in lower_name and not schema["priority_prop"]:
                schema["priority_prop"] = name
            elif prop_type in ("rich_text", "select") and not schema["domain_prop"] and any(k in lower_name for k in ["domain", "field", "category", "track"]):
                schema["domain_prop"] = name
            elif prop_type == "files" and not schema["cv_prop"]:
                schema["cv_prop"] = name
            elif any(k in lower_name for k in ["cv", "resume"]) and not schema["cv_prop"]:
                schema["cv_prop"] = name
            elif prop_type in ("rich_text", "select") and not schema["contact_prop"] and any(k in lower_name for k in ["contact", "recruiter", "person"]):
                schema["contact_prop"] = name
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

def infer_domain(role: str) -> str:
    """Infers the technology or career domain based on the role title."""
    lower = role.lower()
    if any(k in lower for k in ["ai", "machine learning", "ml", "llm", "nlp", "computer vision", "deep learning", "genai", "artificial intelligence"]):
        return "AI / Machine Learning"
    elif any(k in lower for k in ["data engineer", "data pipeline", "etl", "spark", "analytics engineer", "big data"]):
        return "Data Engineering"
    elif any(k in lower for k in ["devops", "sre", "platform", "infrastructure", "cloud", "kubernetes", "systems", "site reliability"]):
        return "Platform & DevOps"
    elif any(k in lower for k in ["frontend", "front-end", "ui", "react", "vue", "angular", "web developer"]):
        return "Frontend"
    elif any(k in lower for k in ["fullstack", "full-stack", "full stack"]):
        return "Fullstack"
    elif any(k in lower for k in ["backend", "back-end", "api", "server", "python", "golang", "java", "distributed"]):
        return "Backend"
    return "Software Engineering"

def upload_cv_file(client: Client, file_path_or_url: str) -> Dict[str, Any]:
    """Uploads a local CV file or formats an external URL for Notion."""
    if not file_path_or_url:
        return {}

    # External URL handling
    if file_path_or_url.startswith(("http://", "https://")):
        filename = os.path.basename(file_path_or_url.split("?")[0]) or "CV.pdf"
        return {
            "type": "external",
            "filename": filename,
            "property_payload": {
                "type": "external",
                "name": filename,
                "external": {"url": file_path_or_url}
            },
            "block_payload": {
                "object": "block",
                "type": "file",
                "file": {
                    "type": "external",
                    "external": {"url": file_path_or_url}
                }
            }
        }

    # Local file handling
    expanded_path = os.path.abspath(os.path.expanduser(file_path_or_url))
    if not os.path.isfile(expanded_path):
        raise FileNotFoundError(f"CV file not found at path: {file_path_or_url}")

    filename = os.path.basename(expanded_path)
    content_type, _ = mimetypes.guess_type(expanded_path)
    if not content_type:
        content_type = "application/pdf"

    # Step 1: Create file upload in Notion
    upload_res = client.file_uploads.create(
        filename=filename,
        content_type=content_type
    )
    upload_id = upload_res["id"]

    # Step 2: Send binary data
    with open(expanded_path, "rb") as f:
        client.file_uploads.send(file_upload_id=upload_id, file=f)

    return {
        "type": "file_upload",
        "upload_id": upload_id,
        "filename": filename,
        "property_payload": {
            "type": "file_upload",
            "name": filename,
            "file_upload": {"id": upload_id}
        },
        "block_payload": {
            "object": "block",
            "type": "file",
            "file": {
                "type": "file_upload",
                "file_upload": {"id": upload_id}
            }
        }
    }

def build_notion_blocks(
    summary: str = "",
    match_points: Optional[List[str]] = None,
    notes: str = "",
    job_url: str = "",
    location: str = "",
    cv_filename: str = "",
    cv_block: Optional[Dict[str, Any]] = None
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

    if cv_block:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"📄 Submitted CV: {cv_filename or 'CV'}"}}]
            }
        })
        blocks.append(cv_block)

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
            f"- CV Property: {schema.get('cv_prop') or 'Not found'}\n"
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

def get_page_date(page: Dict[str, Any], date_prop: Optional[str]) -> Optional[str]:
    """Helper to extract date string (YYYY-MM-DD) from a Notion page."""
    if not date_prop:
        return None
    props = page.get("properties", {})
    d_data = props.get(date_prop, {})
    if d_data.get("type") == "date" and d_data.get("date"):
        return d_data["date"].get("start")
    return None

def get_page_text(page: Dict[str, Any], prop_name: Optional[str]) -> str:
    """Helper to extract plain text from any rich_text or select property."""
    if not prop_name:
        return ""
    props = page.get("properties", {})
    p_data = props.get(prop_name, {})
    p_type = p_data.get("type")
    if p_type == "rich_text":
        texts = p_data.get("rich_text", [])
        return texts[0].get("plain_text", "").strip() if texts else ""
    elif p_type == "select" and p_data.get("select"):
        return p_data["select"].get("name", "").strip()
    return ""

@app.tool(
    name="track_job_application",
    description="Logs a new job application or updates an existing one in Notion with company, role, URL, status, location, CV file path, and rich notes."
)
def track_job_application(
    company: str,
    role: str,
    job_url: str = "",
    status: str = "Applied",
    location: str = "",
    priority: str = "",
    applied_date: str = "",
    cv_file_path: str = "",
    contact: str = "",
    next_followup: str = "",
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
        cv_prop = schema.get("cv_prop")
        contact_prop = schema.get("contact_prop")
        followup_prop = schema.get("followup_prop")
        domain_prop = schema.get("domain_prop")

        # Process CV file if provided
        upload_data = {}
        if cv_file_path:
            try:
                upload_data = upload_cv_file(client, cv_file_path)
            except Exception as e:
                return f"❌ Failed to read/upload CV file '{cv_file_path}': {str(e)}"

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

        if contact_prop and contact:
            properties[contact_prop] = {
                "rich_text": [{"type": "text", "text": {"content": contact}}]
            }

        if followup_prop and next_followup:
            properties[followup_prop] = {
                "date": {"start": next_followup}
            }

        if domain_prop and role:
            properties[domain_prop] = {
                "select": {"name": infer_domain(role)}
            }

        if cv_prop and "property_payload" in upload_data:
            properties[cv_prop] = {
                "files": [upload_data["property_payload"]]
            }

        blocks = build_notion_blocks(
            summary=summary,
            match_points=match_points,
            notes=notes,
            job_url=job_url,
            location=location,
            cv_filename=upload_data.get("filename", ""),
            cv_block=upload_data.get("block_payload")
        )

        if target_page_id:
            # Update the specific existing position
            client.pages.update(page_id=target_page_id, properties=properties)

            update_block: List[Dict[str, Any]] = [
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
            if "block_payload" in upload_data:
                update_block.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": f"📄 Attached CV: {upload_data.get('filename')}"}}]
                    }
                })
                update_block.append(upload_data["block_payload"])

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
    name="attach_cv",
    description="Uploads and attaches a tailored CV file (PDF/DOCX) or URL to an existing job application in Notion. Specify role if multiple positions exist at that company."
)
def attach_cv(company: str, cv_file_path: str, role: str = "") -> str:
    """Uploads and attaches a CV file to a job application in Notion."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")
        cv_prop = schema.get("cv_prop")
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
            return f"❌ Could not find an existing application for company '{company}' in Notion."

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
                summary_lines = [f"⚠️ Found {len(company_pages)} positions at **{company}**:"]
                for p in company_pages:
                    p_role = get_page_role(p, role_prop) or "Role unspecified"
                    p_status = get_page_status(p, status_prop)
                    summary_lines.append(f"- **{p_role}** (`{p_status}`)")
                summary_lines.append(f"\nPlease specify which role to attach this CV to.")
                return "\n".join(summary_lines)

        page_id = target_page["id"]
        matched_role = get_page_role(target_page, role_prop)

        # Upload file
        upload_data = upload_cv_file(client, cv_file_path)

        # 1. Update page property if CV column exists
        if cv_prop and "property_payload" in upload_data:
            client.pages.update(
                page_id=page_id,
                properties={
                    cv_prop: {
                        "files": [upload_data["property_payload"]]
                    }
                }
            )

        # 2. Append embedded file block inside page body
        cv_blocks: List[Dict[str, Any]] = [
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": f"📄 Attached CV: {upload_data.get('filename', 'CV')}"}}]
                }
            }
        ]
        if "block_payload" in upload_data:
            cv_blocks.append(upload_data["block_payload"])

        client.blocks.children.append(block_id=page_id, children=cv_blocks)

        role_str = f" ({matched_role})" if matched_role else ""
        return f"✅ Successfully attached **{upload_data.get('filename')}** to **{company}**{role_str} in Notion!"

    except Exception as e:
        return f"❌ Failed to attach CV: {str(e)}"

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
    name="list_job_applications",
    description="Lists tracked job applications from Notion, optionally filtering by status (e.g. 'Interview', 'Applied')."
)
def list_job_applications(status_filter: str = "") -> str:
    """Lists tracked job applications with their status, role, and URL."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
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
            company = get_page_company(page, title_prop) or "Unnamed"
            role = get_page_role(page, role_prop) or "-"
            status = get_page_status(page, status_prop)

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

@app.tool(
    name="get_application_insights",
    description="Calculates comprehensive job hunt analytics: application counters, response/conversion rates, monthly trends, field/domain breakdown, and stale application alerts."
)
def get_application_insights() -> str:
    """Calculates comprehensive job hunt analytics from the Notion database."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")
        status_prop = schema.get("status_prop")
        date_prop = schema.get("date_prop")

        pages = query_database_pages(client, db_id)
        if not pages:
            return "📊 No applications found in your Notion database yet."

        total_tracked = len(pages)
        status_counts: Dict[str, int] = {}
        monthly_counts: Dict[str, int] = {}
        domain_counts: Dict[str, int] = {}
        stale_apps: List[Dict[str, Any]] = []

        now = datetime.now()

        for page in pages:
            company = get_page_company(page, title_prop)
            role = get_page_role(page, role_prop)
            status = get_page_status(page, status_prop)
            date_str = get_page_date(page, date_prop)

            st_key = status if status != "-" else "Unspecified"
            status_counts[st_key] = status_counts.get(st_key, 0) + 1

            domain = infer_domain(role) if role else "General"
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            if date_str:
                try:
                    d_obj = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    m_key = d_obj.strftime("%B %Y")
                    monthly_counts[m_key] = monthly_counts.get(m_key, 0) + 1

                    if status.lower() == "applied":
                        days_ago = (now - d_obj).days
                        if days_ago >= 14:
                            stale_apps.append({
                                "company": company,
                                "role": role or "Role unspecified",
                                "date": date_str,
                                "days_ago": days_ago
                            })
                except Exception:
                    pass

        applied_count = status_counts.get("Applied", 0)
        screening_count = status_counts.get("Screening", 0)
        interview_count = status_counts.get("Interview", 0)
        offer_count = status_counts.get("Offer", 0)
        rejected_count = status_counts.get("Rejected", 0)
        wishlist_count = status_counts.get("Wishlist", 0)

        active_interviews = screening_count + interview_count
        positive_responses = screening_count + interview_count + offer_count
        submitted_applications = total_tracked - wishlist_count

        response_rate = 0.0
        if submitted_applications > 0:
            response_rate = (positive_responses / submitted_applications) * 100

        lines = [
            "## 📊 Job Search Analytics & Insights Dashboard\n",
            "### 🎯 Pipeline Funnel Overview",
            f"- **Total Tracked:** {total_tracked}",
            f"- **Total Submitted:** {submitted_applications} (Wishlist: {wishlist_count})",
            f"- **Active Pipeline (Interviews/Screenings):** {active_interviews}",
            f"- **Offers:** {offer_count} 🎉",
            f"- **Rejections:** {rejected_count}",
            f"- **Awaiting Initial Response:** {applied_count}",
            f"- **Positive Response Rate:** `{response_rate:.1f}%` *(Screening/Interview vs Submitted)*\n",
            "### 📅 Applications Submitted per Month"
        ]

        if monthly_counts:
            for month, count in sorted(monthly_counts.items(), key=lambda x: x[0], reverse=True):
                lines.append(f"- **{month}:** {count} applications")
        else:
            lines.append("- *No application dates recorded yet.*")

        lines.append("\n### 🛠️ Breakdown by Career Domain")
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_tracked) * 100
            lines.append(f"- **{domain}:** {count} ({pct:.0f}%)")

        if stale_apps:
            lines.append("\n### ⏳ Stale Applications (> 14 Days with No Status Update)")
            for s in sorted(stale_apps, key=lambda x: x["days_ago"], reverse=True):
                lines.append(f"- **{s['company']}** ({s['role']}): Applied `{s['date']}` (**{s['days_ago']} days ago**) ➡️ *Recommended: Send polite follow-up or check status.*")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to compute insights: {str(e)}"

@app.tool(
    name="draft_followup_message",
    description="Drafts a tailored, polite recruiter follow-up message (for LinkedIn or Email) for a job application in Notion."
)
def draft_followup_message(
    company: str,
    role: str = "",
    channel: str = "LinkedIn",
    contact_name: str = ""
) -> str:
    """Drafts a follow-up message referencing application date, role, and key highlights."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")
        date_prop = schema.get("date_prop")
        contact_prop = schema.get("contact_prop")

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
            return f"❌ Could not find an application for '{company}' in Notion."

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
                return f"⚠️ Multiple roles found for {company}. Please specify role."

        matched_role = get_page_role(target_page, role_prop) or "the open position"
        applied_date = get_page_date(target_page, date_prop)
        contact = contact_name or get_page_text(target_page, contact_prop) or "Hiring Team"

        greeting = f"Hi {contact}" if contact != "Hiring Team" else "Hi Team"
        timing_str = f"on {applied_date}" if applied_date else "recently"

        if channel.lower() == "linkedin":
            msg = (
                f"### 💬 Tailored LinkedIn Follow-Up ({company} - {matched_role})\n\n"
                f"{greeting},\n\n"
                f"I hope you're having a great week! I recently applied {timing_str} for the **{matched_role}** role at **{company}**.\n\n"
                f"Given my background building distributed systems, backend architectures, and AI integrations, I'm very excited about what {company} is building.\n\n"
                f"I'd love to connect and see if my background aligns with what the team is looking for. Thank you for your time!\n\n"
                f"Best regards,\nAhmed Khalifa"
            )
        else:
            msg = (
                f"### ✉️ Tailored Email Follow-Up ({company} - {matched_role})\n\n"
                f"**Subject:** Following up: Application for {matched_role} - Ahmed Khalifa\n\n"
                f"{greeting},\n\n"
                f"I hope this email finds you well.\n\n"
                f"I wanted to briefly follow up on the application I submitted {timing_str} for the **{matched_role}** position at **{company}**.\n\n"
                f"I remain very enthusiastic about the opportunity to contribute to {company}, particularly with my experience developing robust backend services and AI agent systems.\n\n"
                f"Please let me know if there are any additional materials or details I can provide to support my application. I look forward to hearing from you.\n\n"
                f"Best regards,\n\nAhmed Khalifa\n[LinkedIn Profile] | [Portfolio/GitHub]"
            )

        return msg
    except Exception as e:
        return f"❌ Failed to draft follow-up message: {str(e)}"

@app.tool(
    name="generate_interview_prep",
    description="Generates an interview preparation cheat sheet based on the job requirements, CV match points, and notes saved in Notion."
)
def generate_interview_prep(company: str, role: str = "") -> str:
    """Generates a structured interview prep plan tailored to the saved job in Notion."""
    try:
        client = get_notion_client()
        db_id = get_db_id()
        schema = inspect_database_schema(client, db_id)

        title_prop = schema.get("title_prop", "Company 1") or "Company 1"
        role_prop = schema.get("role_prop")

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
            return f"❌ No application found for '{company}' in Notion."

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
                return f"⚠️ Multiple roles found for {company}. Please specify role."

        page_id = target_page["id"]
        matched_role = get_page_role(target_page, role_prop) or "Role"

        blocks_res = client.blocks.children.list(block_id=page_id)
        blocks = blocks_res.get("results", [])

        extracted_text = []
        for b in blocks:
            b_type = b.get("type", "")
            data = b.get(b_type, {})
            texts = data.get("rich_text", [])
            t_str = "".join([t.get("plain_text", "") for t in texts])
            if t_str:
                extracted_text.append(t_str)

        notes_summary = "\n".join(extracted_text) if extracted_text else "No additional notes logged."
        domain = infer_domain(matched_role)

        prep = [
            f"# 🎯 Interview Prep Cheat Sheet: {company} ({matched_role})\n",
            f"**Domain Track:** `{domain}`\n",
            "## 1. 🌟 Your 30-Second Elevator Pitch",
            f"\"I'm a software engineer specializing in {domain.lower()}, with a focus on building high-performance, reliable systems and AI-powered automation. I was drawn to {company} because of your focus on scalable engineering, and I'm excited to bring my experience to the {matched_role} team.\"\n",
            "## 2. 🔑 Core Strengths & CV Highlights on File",
            f"Review your tailored points for {company}:",
            notes_summary + "\n",
            "## 3. 💡 High-Probability Technical & Domain Questions to Expect",
            f"- **System Architecture:** How would you design a scalable service to handle sudden spikes in traffic at {company}?",
            "- **Reliability & Debugging:** Describe a time you diagnosed and resolved a challenging production failure or race condition.",
            "- **Domain Depth:** How do you approach API versioning, data consistency, and testing in your services?",
            "- **AI / Agentic Integration:** When integrating LLMs or agent workflows, how do you manage latency, determinism, and fallback strategies?\n",
            "## 4. ❓ Smart Reverse-Interview Questions (To Ask Them)",
            f"- *\"What is the biggest engineering or infrastructure bottleneck the {matched_role} team is tackling this quarter?\"*",
            f"- *\"How does the team balance shipping fast features versus maintaining code quality and technical debt?\"*",
            "- *\"What does success look like in this role 90 days after joining?\"*"
        ]

        return "\n".join(prep)
    except Exception as e:
        return f"❌ Failed to generate interview prep: {str(e)}"

if __name__ == "__main__":
    app.run(transport="stdio")
