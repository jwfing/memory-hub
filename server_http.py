"""Memory Hub MCP Server - HTTP/SSE Mode for Remote Access."""

import json
from typing import Any, Optional
from datetime import datetime
from contextvars import ContextVar

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    Prompt,
    PromptMessage,
    GetPromptResult
)
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response, JSONResponse
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from sqlalchemy import text
from memhub.database import SessionLocal, Conversation, Entity, Relationship, init_db
from memhub.embeddings import get_embedding_service
from memhub.rag_service import get_rag_service
from memhub.graph_service import get_graph_service
from memhub.auth_service import get_auth_service
from memhub.entity_extraction_service import get_entity_extraction_service
from memhub.api_key_service import get_api_key_service

import logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Context variable to store authenticated user_id for the current request
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)

# Initialize services
embedding_service = get_embedding_service()
rag_service = get_rag_service()
graph_service = get_graph_service()
auth_service = get_auth_service()
entity_extraction_service = get_entity_extraction_service()
api_key_service = get_api_key_service()

# Create MCP server
mcp_server = Server("memory-hub")


def extract_and_verify_token(headers: dict) -> Optional[dict]:
    """
    Extract Bearer token from headers and verify it.
    Supports both JWT tokens and API keys.

    Returns:
        Token payload if valid, None otherwise
    """
    auth_header = headers.get('authorization') or headers.get('Authorization')
    if not auth_header:
        return None

    # Extract token from "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None

    token = parts[1]

    # Check if it's an API Key (starts with "mhub_")
    if token.startswith('mhub_'):
        # Verify API Key
        db = SessionLocal()
        try:
            payload = api_key_service.verify_api_key(db, token)
            if payload:
                logger.debug(f"API Key verified for user: {payload.get('user_id')}")
            return payload
        finally:
            db.close()
    else:
        # Verify JWT Token
        payload = auth_service.verify_token(token)
        logger.debug(f"JWT token verified: {payload}")
        return payload


def get_current_user_id() -> str:
    """Get the current authenticated user_id from context."""
    user_id = current_user_id.get()
    if not user_id:
        raise ValueError("Unauthorized: No valid authentication token")
    return user_id


# Tool input models (user_id is Optional - auto-filled by auth middleware)
class SaveConversationInput(BaseModel):
    """Input for saving a conversation."""
    session_id: str = Field(description="Session ID")
    role: str = Field(description="Role: 'user' or 'assistant'")
    content: str = Field(description="Message content")
    platform: Optional[str] = Field(default=None, description="Platform: 'claude', 'chatgpt', etc.")
    metadata: Optional[str] = Field(default=None, description="Additional metadata as JSON string")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class SearchConversationsInput(BaseModel):
    """Input for searching conversations."""
    query: str = Field(description="Search query")
    limit: int = Field(default=10, description="Maximum number of results")
    session_id: Optional[str] = Field(default=None, description="Filter by session ID")
    platform: Optional[str] = Field(default=None, description="Filter by platform")
    days_back: Optional[int] = Field(default=None, description="Search last N days")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class GetRecentContextInput(BaseModel):
    """Input for getting recent context."""
    session_id: Optional[str] = Field(default=None, description="Filter by session ID")
    limit: int = Field(default=20, description="Maximum number of messages")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class SearchByTopicInput(BaseModel):
    """Input for searching by topic."""
    topic: str = Field(description="Topic to search for")
    limit: int = Field(default=10, description="Maximum number of results")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class GetRelatedEntitiesInput(BaseModel):
    """Input for getting related entities."""
    entity_name: str = Field(description="Entity name")
    max_depth: int = Field(default=2, description="Maximum relationship depth")
    limit: int = Field(default=20, description="Maximum number of results")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class GetEntityImportanceInput(BaseModel):
    """Input for getting entity importance."""
    limit: int = Field(default=20, description="Maximum number of results")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class GetTopicClustersInput(BaseModel):
    """Input for getting topic clusters."""
    min_cluster_size: int = Field(default=3, description="Minimum cluster size")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class GetTimelineInput(BaseModel):
    """Input for getting conversation timeline."""
    entity_name: Optional[str] = Field(default=None, description="Filter by entity name")
    limit: int = Field(default=50, description="Maximum number of results")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-filled from auth token)")


class AddEntityInput(BaseModel):
    """Input for adding an entity."""
    conversation_id: int = Field(description="Conversation ID")
    entity_type: str = Field(description="Entity type")
    entity_name: str = Field(description="Entity name")
    description: Optional[str] = Field(default=None, description="Entity description")


class AddRelationshipInput(BaseModel):
    """Input for adding a relationship."""
    source_entity_id: int = Field(description="Source entity ID")
    target_entity_id: int = Field(description="Target entity ID")
    relationship_type: str = Field(description="Relationship type")
    weight: float = Field(default=1.0, description="Relationship weight")


# Authentication tool input models
class RegisterUserInput(BaseModel):
    """Input for user registration."""
    username: str = Field(description="Username (3-50 characters)")
    email: str = Field(description="Email address")
    password: str = Field(description="Password (minimum 8 characters)")
    full_name: Optional[str] = Field(default=None, description="Full name")


class LoginUserInput(BaseModel):
    """Input for user login."""
    username: str = Field(description="Username or email")
    password: str = Field(description="Password")


class VerifyTokenInput(BaseModel):
    """Input for token verification."""
    token: str = Field(description="JWT token")


class UpdatePasswordInput(BaseModel):
    """Input for password update."""
    token: str = Field(description="JWT token")
    old_password: str = Field(description="Current password")
    new_password: str = Field(description="New password")


class GetUserInfoInput(BaseModel):
    """Input for getting user info."""
    token: str = Field(description="JWT token")


# API Key management input models
class GenerateAPIKeyInput(BaseModel):
    """Input for generating API key."""
    token: str = Field(description="JWT token for authentication")
    name: str = Field(description="Name/description for the API key")
    expires_days: Optional[int] = Field(default=None, description="Days until expiration (null = never expires)")


class ListAPIKeysInput(BaseModel):
    """Input for listing API keys."""
    token: str = Field(description="JWT token for authentication")


class RevokeAPIKeyInput(BaseModel):
    """Input for revoking API key."""
    token: str = Field(description="JWT token for authentication")
    key_id: Optional[int] = Field(default=None, description="API key ID to revoke")
    key_prefix: Optional[str] = Field(default=None, description="API key prefix to revoke")


# Register tools
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="save_conversation",
            description="Save a conversation message with automatic embedding generation",
            inputSchema=SaveConversationInput.model_json_schema()
        ),
        Tool(
            name="search_conversations",
            description="Search conversations using semantic search (RAG)",
            inputSchema=SearchConversationsInput.model_json_schema()
        ),
        Tool(
            name="get_recent_context",
            description="Get recent conversation context for a user/session",
            inputSchema=GetRecentContextInput.model_json_schema()
        ),
        Tool(
            name="search_by_topic",
            description="Search conversations by topic using entity extraction",
            inputSchema=SearchByTopicInput.model_json_schema()
        ),
        Tool(
            name="get_related_entities",
            description="Get entities related to a given entity from knowledge graph",
            inputSchema=GetRelatedEntitiesInput.model_json_schema()
        ),
        Tool(
            name="get_entity_importance",
            description="Get most important entities based on graph centrality",
            inputSchema=GetEntityImportanceInput.model_json_schema()
        ),
        Tool(
            name="get_topic_clusters",
            description="Identify topic clusters in the knowledge graph",
            inputSchema=GetTopicClustersInput.model_json_schema()
        ),
        Tool(
            name="get_timeline",
            description="Get timeline of conversations, optionally filtered by entity",
            inputSchema=GetTimelineInput.model_json_schema()
        ),
        Tool(
            name="add_entity",
            description="Manually add an entity to a conversation for knowledge graph",
            inputSchema=AddEntityInput.model_json_schema()
        ),
        Tool(
            name="add_relationship",
            description="Manually add a relationship between entities in knowledge graph",
            inputSchema=AddRelationshipInput.model_json_schema()
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls with automatic user_id injection from auth token."""
    # Auto-fill user_id from authenticated context if not provided
    try:
        authenticated_user_id = get_current_user_id()
        # Inject user_id into arguments if not already present
        if isinstance(arguments, dict) and 'user_id' not in arguments:
            arguments['user_id'] = authenticated_user_id
        elif isinstance(arguments, dict) and not arguments.get('user_id'):
            arguments['user_id'] = authenticated_user_id
    except ValueError as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e), "message": "Authentication required"})
        )]

    db = SessionLocal()
    try:
        if name == "save_conversation":
            args = SaveConversationInput(**arguments)

            # Generate embedding
            embedding = embedding_service.get_embedding(args.content)

            # Create conversation
            conversation = Conversation(
                user_id=args.user_id,
                session_id=args.session_id,
                role=args.role,
                content=args.content,
                platform=args.platform,
                embedding=embedding,
                extra_metadata=args.metadata,
                created_at=datetime.utcnow()
            )

            db.add(conversation)
            db.commit()
            db.refresh(conversation)

            # Extract entities and relationships from conversation
            try:
                entities_data, relationships_data = entity_extraction_service.extract_entities(
                    text=args.content,
                    role=args.role,
                    extract_relationships=True
                )

                # Save extracted entities
                entity_id_map = {}  # Map entity name to database ID
                for entity_data in entities_data:
                    # Generate embedding for entity
                    entity_embedding = embedding_service.get_embedding(
                        entity_data["description"]
                    )

                    entity = Entity(
                        user_id=args.user_id,
                        conversation_id=conversation.id,
                        entity_type=entity_data["entity_type"],
                        entity_name=entity_data["entity_name"],
                        description=entity_data["description"],
                        embedding=entity_embedding,
                        created_at=datetime.utcnow()
                    )

                    db.add(entity)
                    db.flush()  # Flush to get the entity.id without committing
                    entity_id_map[entity_data["entity_name"]] = entity.id

                # Save extracted relationships
                saved_relationships = []
                for rel_data in relationships_data:
                    source_name = rel_data["source_entity_name"]
                    target_name = rel_data["target_entity_name"]

                    # Only create relationship if both entities were saved
                    if source_name in entity_id_map and target_name in entity_id_map:
                        relationship = Relationship(
                            source_entity_id=entity_id_map[source_name],
                            target_entity_id=entity_id_map[target_name],
                            relationship_type=rel_data["relationship_type"],
                            weight=rel_data.get("weight", 1.0),
                            created_at=datetime.utcnow()
                        )
                        db.add(relationship)
                        saved_relationships.append({
                            "source": source_name,
                            "target": target_name,
                            "type": rel_data["relationship_type"]
                        })

                db.commit()

                result = {
                    "success": True,
                    "conversation_id": conversation.id,
                    "message": "Conversation saved successfully",
                    "entities_extracted": len(entities_data),
                    "relationships_extracted": len(saved_relationships)
                }

            except Exception as e:
                # If entity extraction fails, still save the conversation
                logger.warning(f"Entity extraction failed: {e}")
                result = {
                    "success": True,
                    "conversation_id": conversation.id,
                    "message": "Conversation saved successfully (entity extraction failed)",
                    "entities_extracted": 0,
                    "relationships_extracted": 0,
                    "extraction_error": str(e)
                }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "search_conversations":
            args = SearchConversationsInput(**arguments)

            results = rag_service.search_conversations(
                db=db,
                query=args.query,
                user_id=args.user_id,
                limit=args.limit,
                session_id=args.session_id,
                platform=args.platform,
                days_back=args.days_back
            )

            return [TextContent(
                type="text",
                text=json.dumps({"results": results, "count": len(results)}, indent=2)
            )]

        elif name == "get_recent_context":
            args = GetRecentContextInput(**arguments)

            results = rag_service.get_recent_context(
                db=db,
                user_id=args.user_id,
                session_id=args.session_id,
                limit=args.limit
            )

            return [TextContent(
                type="text",
                text=json.dumps({"context": results, "count": len(results)}, indent=2)
            )]

        elif name == "search_by_topic":
            args = SearchByTopicInput(**arguments)

            results = rag_service.search_by_topic(
                db=db,
                topic=args.topic,
                user_id=args.user_id,
                limit=args.limit
            )

            return [TextContent(
                type="text",
                text=json.dumps({"results": results, "count": len(results)}, indent=2)
            )]

        elif name == "get_related_entities":
            args = GetRelatedEntitiesInput(**arguments)

            results = graph_service.get_related_entities(
                db=db,
                entity_name=args.entity_name,
                user_id=args.user_id,
                max_depth=args.max_depth,
                limit=args.limit
            )

            return [TextContent(
                type="text",
                text=json.dumps({"related_entities": results, "count": len(results)}, indent=2)
            )]

        elif name == "get_entity_importance":
            args = GetEntityImportanceInput(**arguments)

            results = graph_service.get_entity_importance(
                db=db,
                user_id=args.user_id,
                limit=args.limit
            )

            return [TextContent(
                type="text",
                text=json.dumps({"entities": results, "count": len(results)}, indent=2)
            )]

        elif name == "get_topic_clusters":
            args = GetTopicClustersInput(**arguments)

            results = graph_service.get_topic_clusters(
                db=db,
                user_id=args.user_id,
                min_cluster_size=args.min_cluster_size
            )

            return [TextContent(
                type="text",
                text=json.dumps({"clusters": results, "count": len(results)}, indent=2)
            )]

        elif name == "get_timeline":
            args = GetTimelineInput(**arguments)

            results = graph_service.get_conversation_timeline(
                db=db,
                user_id=args.user_id,
                entity_name=args.entity_name,
                limit=args.limit
            )

            return [TextContent(
                type="text",
                text=json.dumps({"timeline": results, "count": len(results)}, indent=2)
            )]

        elif name == "add_entity":
            args = AddEntityInput(**arguments)

            # Generate embedding for entity
            description_text = args.description or args.entity_name
            embedding = embedding_service.get_embedding(description_text)

            entity = Entity(
                conversation_id=args.conversation_id,
                entity_type=args.entity_type,
                entity_name=args.entity_name,
                description=args.description,
                embedding=embedding,
                created_at=datetime.utcnow()
            )

            db.add(entity)
            db.commit()
            db.refresh(entity)

            result = {
                "success": True,
                "entity_id": entity.id,
                "message": "Entity added successfully"
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "add_relationship":
            args = AddRelationshipInput(**arguments)

            relationship = Relationship(
                source_entity_id=args.source_entity_id,
                target_entity_id=args.target_entity_id,
                relationship_type=args.relationship_type,
                weight=args.weight,
                created_at=datetime.utcnow()
            )

            db.add(relationship)
            db.commit()
            db.refresh(relationship)

            result = {
                "success": True,
                "relationship_id": relationship.id,
                "message": "Relationship added successfully"
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)})
        )]

    finally:
        db.close()


@mcp_server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompts."""
    return [
        Prompt(
            name="auto-save-reminder",
            description="Reminder to automatically save important conversations to memory-hub",
            arguments=[]
        )
    ]


@mcp_server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Get a prompt by name."""
    if name == "auto-save-reminder":
        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="""You are Claude Code with access to memory-hub MCP server.

IMPORTANT: When you have important or meaningful conversations with the user (especially about technical implementations, problem-solving, or learning), you should proactively save the conversation to memory-hub using the save_conversation tool.

Guidelines for auto-saving:
1. Save conversations that contain:
   - Technical implementations or solutions
   - Important decisions or discussions
   - Learning moments or explanations
   - Problem-solving sessions
   - Feature requests or bug reports

2. Don't save:
   - Simple confirmations or acknowledgments
   - Trivial questions
   - Test messages

3. When saving:
   - Use descriptive session_ids (e.g., "feature_name_YYYYMMDD")
   - Add relevant metadata (topic, language, tags)
   - Save both user messages and your responses

Remember: The goal is to build a knowledge graph of the user's projects and learning journey."""
                    )
                )
            ]
        )

    raise ValueError(f"Unknown prompt: {name}")


@mcp_server.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="memory://stats",
            name="Memory Statistics",
            mimeType="application/json",
            description="Statistics about stored conversations and entities"
        )
    ]


@mcp_server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource."""
    if uri == "memory://stats":
        db = SessionLocal()
        try:
            conv_count = db.query(Conversation).count()
            entity_count = db.query(Entity).count()
            rel_count = db.query(Relationship).count()

            stats = {
                "conversations": conv_count,
                "entities": entity_count,
                "relationships": rel_count,
                "timestamp": datetime.utcnow().isoformat()
            }

            return json.dumps(stats, indent=2)
        finally:
            db.close()

    return json.dumps({"error": "Resource not found"})


# HTTP REST API handlers for authentication
async def handle_register(request):
    """Handle user registration via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = RegisterUserInput(**data)

        db = SessionLocal()
        try:
            result = auth_service.create_user(
                db=db,
                username=args.username,
                email=args.email,
                password=args.password,
                full_name=args.full_name
            )
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def handle_login(request):
    """Handle user login via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = LoginUserInput(**data)

        db = SessionLocal()
        try:
            result = auth_service.authenticate_user(
                db=db,
                username=args.username,
                password=args.password
            )
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def handle_verify_token(request):
    """Handle token verification via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = VerifyTokenInput(**data)

        payload = auth_service.verify_token(args.token)

        if payload:
            db = SessionLocal()
            try:
                user_info = auth_service.get_user_info(db, payload["user_id"])
                result = {
                    "success": True,
                    "valid": True,
                    "user": user_info
                }
            finally:
                db.close()
        else:
            result = {
                "success": False,
                "valid": False,
                "error": "Invalid or expired token"
            }

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def handle_update_password(request):
    """Handle password update via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = UpdatePasswordInput(**data)

        # Verify token first
        payload = auth_service.verify_token(args.token)
        if not payload:
            return JSONResponse({
                "success": False,
                "error": "Invalid or expired token"
            }, status_code=401)

        db = SessionLocal()
        try:
            result = auth_service.update_password(
                db=db,
                user_id=payload["user_id"],
                old_password=args.old_password,
                new_password=args.new_password
            )
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def handle_get_user_info(request):
    """Handle getting user info via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = GetUserInfoInput(**data)

        # Verify token
        payload = auth_service.verify_token(args.token)
        if not payload:
            return JSONResponse({
                "success": False,
                "error": "Invalid or expired token"
            }, status_code=401)

        db = SessionLocal()
        try:
            user_info = auth_service.get_user_info(db, payload["user_id"])
            if user_info:
                result = {
                    "success": True,
                    "user": user_info
                }
            else:
                result = {
                    "success": False,
                    "error": "User not found"
                }
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


# API Key management handlers
async def handle_generate_api_key(request):
    """Handle API key generation via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = GenerateAPIKeyInput(**data)

        # Verify JWT token first
        payload = auth_service.verify_token(args.token)
        if not payload:
            return JSONResponse({
                "success": False,
                "error": "Invalid or expired token"
            }, status_code=401)

        user_id = payload["user_id"]

        db = SessionLocal()
        try:
            result = api_key_service.generate_api_key(
                db=db,
                user_id=user_id,
                name=args.name,
                expires_days=args.expires_days
            )
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def handle_list_api_keys(request):
    """Handle listing API keys via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = ListAPIKeysInput(**data)

        # Verify JWT token
        payload = auth_service.verify_token(args.token)
        if not payload:
            return JSONResponse({
                "success": False,
                "error": "Invalid or expired token"
            }, status_code=401)

        user_id = payload["user_id"]

        db = SessionLocal()
        try:
            api_keys = api_key_service.list_api_keys(db=db, user_id=user_id)
            return JSONResponse({
                "success": True,
                "api_keys": api_keys,
                "count": len(api_keys)
            })
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def handle_revoke_api_key(request):
    """Handle revoking API key via HTTP API."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
        args = RevokeAPIKeyInput(**data)

        # Verify JWT token
        payload = auth_service.verify_token(args.token)
        if not payload:
            return JSONResponse({
                "success": False,
                "error": "Invalid or expired token"
            }, status_code=401)

        user_id = payload["user_id"]

        db = SessionLocal()
        try:
            result = api_key_service.revoke_api_key(
                db=db,
                user_id=user_id,
                key_id=args.key_id,
                key_prefix=args.key_prefix
            )
            return JSONResponse(result)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


# Create SSE transport for MCP
sse_transport = SseServerTransport("/messages")


# MCP SSE endpoint handler with authentication
async def handle_sse(request):
    """Handle SSE connection for MCP protocol with token authentication."""
    # Extract and verify token from request headers
    headers = dict(request.headers)
    payload = extract_and_verify_token(headers)

    if not payload:
        return JSONResponse(
            {"error": "Unauthorized", "message": "Valid Bearer token required"},
            status_code=401
        )

    # Set user_id in context for the duration of this SSE connection
    user_id = str(payload["user_id"])
    current_user_id.set(user_id)

    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options()
        )
    return Response()


# Custom messages handler with authentication (raw ASGI app)
async def handle_messages_asgi(scope, receive, send):
    """Handle MCP messages with token authentication (ASGI version)."""
    # Extract headers from ASGI scope
    headers = dict(scope.get("headers", []))
    # Convert header keys from bytes to strings
    headers = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
               for k, v in headers.items()}

    payload = extract_and_verify_token(headers)

    if not payload:
        # Send unauthorized response
        response = JSONResponse(
            {"error": "Unauthorized", "message": "Valid Bearer token required"},
            status_code=401
        )
        await response(scope, receive, send)
        return

    # Set user_id in context for this request
    user_id = str(payload["user_id"])
    current_user_id.set(user_id)

    # Forward to SSE transport's message handler
    await sse_transport.handle_post_message(scope, receive, send)


# ASGI application wrapper class for /messages endpoint
class MessagesEndpoint:
    """ASGI application wrapper for messages endpoint."""

    async def __call__(self, scope, receive, send):
        """Handle ASGI request."""
        await handle_messages_asgi(scope, receive, send)


async def handle_health(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    # Check database connectivity
    db_healthy = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    return JSONResponse({
        "status": "healthy" if db_healthy else "degraded",
        "server": "memory-hub",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": "ok"
    })


async def handle_save_conversation_http(request):
    """Simple HTTP endpoint for saving conversations (for Claude Code hooks).
    Implements the same logic as the save_conversation MCP tool including
    entity extraction and relationship extraction.
    """
    from starlette.responses import JSONResponse

    # Verify authentication
    headers_dict = dict(request.scope.get("headers", []))
    auth_header = headers_dict.get(b"authorization") or headers_dict.get(b"Authorization")
    if not auth_header:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    token = auth_header.decode().split()[-1]

    # Verify token
    db = SessionLocal()
    try:
        if token.startswith("mhub_"):
            payload = api_key_service.verify_api_key(db, token)
        else:
            payload = auth_service.verify_token(token)

        if not payload:
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        user_id = str(payload["user_id"])

        # Parse request body
        data = await request.json()
        session_id = data.get("session_id")
        role = data.get("role", "user")
        content = data.get("content")
        platform = data.get("platform", "claude_code")
        metadata = data.get("metadata")

        if not session_id or not content:
            return JSONResponse({"error": "session_id and content are required"}, status_code=400)

        # Generate embedding for content
        embedding = embedding_service.get_embedding(content)

        # Create conversation
        conversation = Conversation(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            platform=platform,
            embedding=embedding,
            extra_metadata=metadata,
            created_at=datetime.utcnow()
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # Extract entities and relationships from conversation (same logic as MCP tool)
        try:
            entities_data, relationships_data = entity_extraction_service.extract_entities(
                text=content,
                role=role,
                extract_relationships=True
            )

            # Save extracted entities
            entity_id_map = {}  # Map entity name to database ID
            for entity_data in entities_data:
                # Generate embedding for entity
                entity_embedding = embedding_service.get_embedding(
                    entity_data["description"]
                )

                entity = Entity(
                    user_id=user_id,
                    conversation_id=conversation.id,
                    entity_type=entity_data["entity_type"],
                    entity_name=entity_data["entity_name"],
                    description=entity_data["description"],
                    embedding=entity_embedding,
                    created_at=datetime.utcnow()
                )

                db.add(entity)
                db.flush()  # Flush to get the entity.id without committing
                entity_id_map[entity_data["entity_name"]] = entity.id

            # Save extracted relationships
            saved_relationships = []
            for rel_data in relationships_data:
                source_name = rel_data["source_entity_name"]
                target_name = rel_data["target_entity_name"]

                # Only create relationship if both entities were saved
                if source_name in entity_id_map and target_name in entity_id_map:
                    relationship = Relationship(
                        source_entity_id=entity_id_map[source_name],
                        target_entity_id=entity_id_map[target_name],
                        relationship_type=rel_data["relationship_type"],
                        weight=rel_data.get("weight", 1.0),
                        created_at=datetime.utcnow()
                    )
                    db.add(relationship)
                    saved_relationships.append({
                        "source": source_name,
                        "target": target_name,
                        "type": rel_data["relationship_type"]
                    })

            db.commit()

            result = {
                "success": True,
                "conversation_id": conversation.id,
                "message": "Conversation saved successfully",
                "entities_extracted": len(entities_data),
                "relationships_extracted": len(saved_relationships)
            }

        except Exception as e:
            # If entity extraction fails, still save the conversation
            logger.warning(f"Entity extraction failed: {e}")
            result = {
                "success": True,
                "conversation_id": conversation.id,
                "message": "Conversation saved successfully (entity extraction failed)",
                "entities_extracted": 0,
                "relationships_extracted": 0,
                "extraction_error": str(e)
            }

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Error saving conversation via HTTP: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


# Create Starlette application
app = Starlette(
    routes=[
        Route('/sse', handle_sse, methods=['GET']),
        Route('/health', handle_health),
        Route('/api/save', handle_save_conversation_http, methods=['POST']),  # Hook endpoint
        # Authentication endpoints
        Route('/auth/register', handle_register, methods=['POST']),
        Route('/auth/login', handle_login, methods=['POST']),
        Route('/auth/verify', handle_verify_token, methods=['POST']),
        Route('/auth/update-password', handle_update_password, methods=['POST']),
        Route('/auth/user-info', handle_get_user_info, methods=['POST']),
        # API Key management endpoints
        Route('/auth/api-keys/generate', handle_generate_api_key, methods=['POST']),
        Route('/auth/api-keys/list', handle_list_api_keys, methods=['POST']),
        Route('/auth/api-keys/revoke', handle_revoke_api_key, methods=['POST']),
    ]
)

# Add /messages route as raw ASGI app
app.add_route('/messages', MessagesEndpoint(), methods=['POST'])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    print("Initializing database...")
    init_db()
    print("Database initialized!")
    print("MCP Server (HTTP/SSE mode) started successfully!")


def main():
    """Run the HTTP/SSE server."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
        timeout_graceful_shutdown=10  # Wait max 10 seconds for connections to close
    )


if __name__ == "__main__":
    main()