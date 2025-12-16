# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tool Template Library
=====================

Pre-configured tool templates for rapid custom tool creation.
Users select a template and customize the configuration fields.

Provides 5 core templates:
1. Notification (Slack/Discord) - PRIORITY
2. API/Webhook
3. Image/Video Generator (OpenAI DALL-E 3, Sora / Gemini Imagen 3, Veo 3/3.1)
4. Database Query (PostgreSQL, MySQL, MongoDB)
5. Data Transform (JSON, CSV, XML, YAML)
"""

from typing import Dict, List, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

from models.custom_tool import ToolType, ToolTemplateType


# =============================================================================
# Tool Template Model
# =============================================================================

class ToolTemplate(BaseModel):
    """
    Template for creating custom tools.

    Provides pre-configured defaults and required fields.
    """
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="What this tool does")
    category: str = Field(..., description="Tool category")
    tool_type: ToolType = Field(..., description="Type of tool")

    # Icon/visual for UI
    icon: str = Field(default="🔧", description="Emoji or icon identifier")
    priority: int = Field(default=0, description="Display priority (higher = featured)")

    # Template configuration structure
    config_template: Dict[str, Any] = Field(
        ...,
        description="Template configuration with placeholders"
    )
    input_schema_template: Dict[str, Any] = Field(
        ...,
        description="JSON Schema template for tool inputs"
    )

    # Required fields that users must fill
    required_user_fields: List[str] = Field(
        default_factory=list,
        description="Fields that users must customize"
    )

    # Helper information for users
    setup_instructions: str = Field(
        default="",
        description="Instructions for setting up this tool"
    )
    example_use_cases: List[str] = Field(
        default_factory=list,
        description="Example scenarios for using this tool"
    )

    # Metadata
    tags: List[str] = Field(default_factory=list)
    is_featured: bool = Field(default=False)

    def to_tool_config(self, user_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert template to tool configuration with user values.

        Args:
            user_values: User-provided values for customization

        Returns:
            Complete tool configuration
        """
        # Deep copy config template
        import copy
        config = copy.deepcopy(self.config_template)

        # Apply user values
        for key, value in user_values.items():
            if key in config.get("implementation_config", {}):
                config["implementation_config"][key] = value
            else:
                config[key] = value

        return config


# =============================================================================
# Tool Template Registry
# =============================================================================

class ToolTemplateRegistry:
    """
    Registry of available tool templates.

    Mirrors AgentTemplateRegistry pattern.
    """
    _templates: Dict[str, ToolTemplate] = {}

    @classmethod
    def register(cls, template: ToolTemplate):
        """Register a tool template"""
        cls._templates[template.template_id] = template

    @classmethod
    def get(cls, template_id: str) -> Optional[ToolTemplate]:
        """Get a template by ID"""
        return cls._templates.get(template_id)

    @classmethod
    def list_all(cls) -> List[ToolTemplate]:
        """List all available templates"""
        return list(cls._templates.values())

    @classmethod
    def list_by_type(cls, tool_type: ToolType) -> List[ToolTemplate]:
        """List templates filtered by tool type"""
        return [t for t in cls._templates.values() if t.tool_type == tool_type]

    @classmethod
    def list_featured(cls) -> List[ToolTemplate]:
        """List featured templates"""
        return [t for t in cls._templates.values() if t.is_featured]


# =============================================================================
# TEMPLATE DEFINITIONS
# =============================================================================

# -----------------------------------------------------------------------------
# 1. NOTIFICATION TOOLS (PRIORITY)
# -----------------------------------------------------------------------------

NOTIFICATION_SLACK_TEMPLATE = ToolTemplate(
    template_id="notification_slack",
    name="Slack Notification",
    description="Send messages to Slack channels via webhook or bot",
    category="notification",
    tool_type=ToolType.NOTIFICATION,
    icon="💬",
    priority=100,  # Highest priority
    is_featured=True,
    config_template={
        "tool_type": "notification",
        "template_type": "notification_slack",
        "implementation_config": {
            "provider": "slack",
            "webhook_url": "",  # USER MUST PROVIDE
            "channel": "#general",
            "message_template": "{message}",
            "username": "LangConfig Bot",
            "icon_emoji": ":robot_face:",
            "timeout": 10
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to send to Slack"
            },
            "channel": {
                "type": "string",
                "description": "Channel to send to (optional, uses default if not specified)",
                "default": "#general"
            },
            "priority": {
                "type": "string",
                "description": "Message priority: normal, high, urgent",
                "default": "normal"
            }
        },
        "required": ["message"]
    },
    required_user_fields=["webhook_url"],
    setup_instructions="""
1. Go to https://api.slack.com/messaging/webhooks
2. Create a new Incoming Webhook for your workspace
3. Select the default channel
4. Copy the webhook URL
5. Paste it into the 'Webhook URL' field below

The webhook URL looks like: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
""",
    example_use_cases=[
        "Send task completion notifications to team channel",
        "Alert when workflow encounters errors",
        "Notify stakeholders of important agent decisions",
        "Daily summary reports to project channel"
    ],
    tags=["notification", "slack", "messaging", "communication"]
)

NOTIFICATION_DISCORD_TEMPLATE = ToolTemplate(
    template_id="notification_discord",
    name="Discord Notification",
    description="Send messages to Discord channels via webhook (supports multiple channels)",
    category="notification",
    tool_type=ToolType.NOTIFICATION,
    icon="🎮",
    priority=95,
    is_featured=True,
    config_template={
        "tool_type": "notification",
        "template_type": "notification_discord",
        "implementation_config": {
            "provider": "discord",
            # Support both single webhook or multiple channels
            "webhook_url": "",  # Default/fallback webhook (USER MUST PROVIDE)
            "webhooks": {
                # Example multi-channel setup (optional):
                # "announcements": "https://discord.com/api/webhooks/111111/aaaaa",
                # "updates": "https://discord.com/api/webhooks/222222/bbbbb",
                # "errors": "https://discord.com/api/webhooks/333333/ccccc"
            },
            "default_channel": "default",  # Which webhook to use if channel not specified
            "username": "LangConfig Bot",
            "avatar_url": "",
            "message_template": "{message}",
            "use_embeds": True,
            "embed_color": "#5865F2",  # Discord blurple
            "timeout": 10
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to send to Discord"
            },
            "channel": {
                "type": "string",
                "description": "Channel name to send to (uses default if not specified or webhook_url if only one configured)",
                "default": "default"
            },
            "title": {
                "type": "string",
                "description": "Embed title (if using embeds)",
                "default": ""
            },
            "color": {
                "type": "string",
                "description": "Embed color in hex (e.g., #FF0000)",
                "default": "#5865F2"
            },
            "username": {
                "type": "string",
                "description": "Override bot username for this message (optional)",
                "default": ""
            }
        },
        "required": ["message"]
    },
    required_user_fields=["webhook_url"],
    setup_instructions="""
SINGLE CHANNEL SETUP:
1. Open your Discord server
2. Go to Server Settings → Integrations → Webhooks
3. Click 'New Webhook'
4. Choose the channel and copy the webhook URL
5. Paste it into the 'Webhook URL' field below

MULTIPLE CHANNELS SETUP:
Each Discord webhook is permanently bound to ONE channel. To send to different channels:

1. Create separate webhooks for each channel:
   - Channel A: Server Settings → Integrations → Webhooks → New Webhook → Copy URL
   - Channel B: Server Settings → Integrations → Webhooks → New Webhook → Copy URL
   - Channel C: Server Settings → Integrations → Webhooks → New Webhook → Copy URL

2. In the 'Webhooks' configuration field (JSON), add your webhooks like this:
   {
     "announcements": "https://discord.com/api/webhooks/111111/aaaaa",
     "updates": "https://discord.com/api/webhooks/222222/bbbbb",
     "errors": "https://discord.com/api/webhooks/333333/ccccc"
   }

3. When calling the tool, specify which channel: {"message": "Hello!", "channel": "announcements"}

IMPORTANT: Each webhook URL is bound to the channel where you created it. You cannot change
which channel a webhook posts to - you must create a new webhook in the target channel.

Webhook URLs look like: https://discord.com/api/webhooks/[ID]/[TOKEN]
""",
    example_use_cases=[
        "Send workflow status to #updates, errors to #alerts",
        "Route different message types to different channels",
        "Alert moderators in #moderation, announce in #general",
        "Log to #logs, notify stakeholders in #notifications"
    ],
    tags=["notification", "discord", "messaging", "communication", "multi-channel"]
)

# -----------------------------------------------------------------------------
# 1B. CMS/PUBLISHING TOOLS
# -----------------------------------------------------------------------------

CMS_WORDPRESS_TEMPLATE = ToolTemplate(
    template_id="cms_wordpress",
    name="WordPress Publisher",
    description="Create, update, and manage WordPress posts, pages, and media",
    category="cms",
    tool_type=ToolType.API,
    icon="📝",
    priority=92,
    is_featured=True,
    config_template={
        "tool_type": "api",
        "template_type": "cms_wordpress",
        "implementation_config": {
            "provider": "wordpress",
            "site_url": "",  # USER MUST PROVIDE: https://yoursite.com
            "username": "",  # USER MUST PROVIDE: WordPress username
            "app_password": "",  # USER MUST PROVIDE: Application password (NOT regular password)
            "default_author_id": 1,
            "default_status": "draft",  # draft, publish, pending, private
            "default_category": "Uncategorized",
            "timeout": 30
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: create_post, update_post, publish_post, delete_post, upload_media",
                "enum": ["create_post", "update_post", "publish_post", "delete_post", "upload_media", "get_post"],
                "default": "create_post"
            },
            "title": {
                "type": "string",
                "description": "Post/page title"
            },
            "content": {
                "type": "string",
                "description": "Post/page content (HTML or plain text)"
            },
            "excerpt": {
                "type": "string",
                "description": "Post excerpt/summary (optional)",
                "default": ""
            },
            "status": {
                "type": "string",
                "description": "Post status: draft, publish, pending, private",
                "enum": ["draft", "publish", "pending", "private"],
                "default": "draft"
            },
            "post_id": {
                "type": "integer",
                "description": "Post ID (required for update/publish/delete actions)"
            },
            "categories": {
                "type": "array",
                "description": "Category names or IDs",
                "items": {"type": "string"},
                "default": []
            },
            "tags": {
                "type": "array",
                "description": "Tag names",
                "items": {"type": "string"},
                "default": []
            },
            "featured_image_url": {
                "type": "string",
                "description": "URL of image to set as featured image",
                "default": ""
            },
            "author_id": {
                "type": "integer",
                "description": "Author ID (optional, uses default if not specified)"
            }
        },
        "required": ["action"]
    },
    required_user_fields=["site_url", "username", "app_password"],
    setup_instructions="""
WORDPRESS REST API AUTHENTICATION:

1. **Create an Application Password** (WordPress 5.6+):
   - Log in to your WordPress admin dashboard
   - Go to Users → Profile
   - Scroll down to "Application Passwords"
   - Enter a name (e.g., "LangConfig Bot")
   - Click "Add New Application Password"
   - COPY THE PASSWORD IMMEDIATELY (shown only once!)
   - Paste it into the 'App Password' field below

2. **Site URL**:
   - Enter your WordPress site URL (e.g., https://yoursite.com)
   - Do NOT include /wp-admin or /wp-json

3. **Username**:
   - Your WordPress username (the one you log in with)

IMPORTANT NOTES:
- Application Passwords are MORE SECURE than your regular password
- They can be revoked anytime from your WordPress profile
- Requires WordPress 5.6+ with REST API enabled
- HTTPS is recommended for security

TESTING YOUR SETUP:
After configuration, test with:
{
  "action": "create_post",
  "title": "Test Post",
  "content": "This is a test post from LangConfig",
  "status": "draft"
}

COMMON ACTIONS:

Create Draft:
{
  "action": "create_post",
  "title": "My Article",
  "content": "<p>Article content here</p>",
  "status": "draft",
  "categories": ["News"],
  "tags": ["AI", "Automation"]
}

Publish Draft:
{
  "action": "publish_post",
  "post_id": 123
}

Update Post:
{
  "action": "update_post",
  "post_id": 123,
  "title": "Updated Title",
  "content": "<p>Updated content</p>"
}

Delete Post:
{
  "action": "delete_post",
  "post_id": 123
}
""",
    example_use_cases=[
        "Generate blog posts with AI and save as WordPress drafts",
        "Auto-publish scheduled content from workflows",
        "Update existing posts with new information",
        "Create documentation pages automatically",
        "Bulk import content from external sources",
        "Generate and publish social media round-ups"
    ],
    tags=["wordpress", "cms", "publishing", "blog", "content-management"]
)

# Twitter/X Publishing Tool
SOCIAL_TWITTER_TEMPLATE = ToolTemplate(
    template_id="social_twitter",
    name="Twitter/X Integration",
    description="Read and post tweets using Twitter API v2 (supports free tier)",
    category="cms",
    tool_type=ToolType.API,
    icon="social_twitter",
    priority=91,
    is_featured=True,
    config_template={
        "tool_type": "api",
        "template_type": "social_twitter",
        "implementation_config": {
            "provider": "twitter",
            "api_key": "",  # USER MUST PROVIDE: Twitter API Key
            "api_secret": "",  # USER MUST PROVIDE: Twitter API Secret
            "access_token": "",  # USER MUST PROVIDE: Access Token
            "access_token_secret": "",  # USER MUST PROVIDE: Access Token Secret
            "bearer_token": "",  # USER MUST PROVIDE (Alternative): Bearer Token (for read-only)
            "api_version": "v2",
            "timeout": 30
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: post_tweet, read_timeline, search_tweets, get_user, delete_tweet",
                "enum": ["post_tweet", "read_timeline", "search_tweets", "get_user", "delete_tweet"],
                "default": "post_tweet"
            },
            "text": {
                "type": "string",
                "description": "Tweet text content (max 280 characters for post_tweet)"
            },
            "tweet_id": {
                "type": "string",
                "description": "Tweet ID (required for delete_tweet)"
            },
            "username": {
                "type": "string",
                "description": "Twitter username (for get_user, read_timeline actions)"
            },
            "query": {
                "type": "string",
                "description": "Search query (for search_tweets action)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 100 for free tier)",
                "default": 10
            },
            "reply_to_tweet_id": {
                "type": "string",
                "description": "Tweet ID to reply to (optional, for post_tweet)"
            },
            "media_url": {
                "type": "string",
                "description": "URL of media to attach (optional, for post_tweet)"
            }
        },
        "required": ["action"]
    },
    required_user_fields=["api_key", "api_secret", "access_token", "access_token_secret"],
    setup_instructions="""
TWITTER API V2 SETUP (FREE TIER):

1. **Create a Twitter Developer Account**:
   - Go to https://developer.twitter.com/
   - Click "Sign up" and complete the application
   - Select "Free" tier (includes 1,500 tweets/month post limit)

2. **Create a New App**:
   - Go to the Developer Portal
   - Navigate to "Projects & Apps"
   - Click "Create App"
   - Give your app a name

3. **Get API Credentials**:
   - In your app settings, go to "Keys and tokens"
   - Generate/copy the following:
     * API Key (Consumer Key)
     * API Secret (Consumer Secret)
     * Access Token
     * Access Token Secret
   - Alternatively, for read-only: Use Bearer Token

4. **Set App Permissions**:
   - In app settings → "User authentication settings"
   - Set permissions: "Read and Write" (for posting)
   - Save changes

5. **Rate Limits (Free Tier)**:
   - Post tweets: 1,500 tweets/month
   - Read tweets: 500,000 tweets/month
   - User lookups: 500,000 requests/month

IMPORTANT NOTES:
- Free tier has monthly limits, not per-minute
- Tweets must be ≤280 characters
- Media uploads require additional setup
- For read-only operations, Bearer Token alone is sufficient
""",
    example_use_cases=[
        "Post automated updates and announcements to Twitter",
        "Monitor mentions and replies from your timeline",
        "Search for tweets about specific topics or hashtags",
        "Get user profile information and follower counts",
        "Reply to tweets programmatically",
        "Schedule and post content to Twitter automatically"
    ],
    tags=["social", "twitter", "x", "posting", "social-media", "publishing"]
)

# -----------------------------------------------------------------------------
# 2. API/WEBHOOK TOOLS
# -----------------------------------------------------------------------------

API_WEBHOOK_TEMPLATE = ToolTemplate(
    template_id="api_webhook",
    name="API / Webhook Call",
    description="Make HTTP requests to any REST API or webhook",
    category="api",
    tool_type=ToolType.API,
    icon="🌐",
    priority=90,
    is_featured=True,
    config_template={
        "tool_type": "api",
        "template_type": "api_webhook",
        "implementation_config": {
            "method": "GET",
            "url": "",  # USER MUST PROVIDE
            "headers": {},
            "auth": {
                "type": "none"
            },
            "body_template": None,
            "response_parser": {
                "type": "full_response"
            },
            "timeout": 30
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "API endpoint path or full URL"
            }
        },
        "required": ["endpoint"]
    },
    required_user_fields=["url", "method"],
    setup_instructions="""
1. Enter the API base URL or full endpoint URL
2. Select HTTP method (GET, POST, PUT, DELETE, PATCH)
3. Add any required headers (e.g., Content-Type, API keys)
4. Configure authentication if needed
5. For POST/PUT/PATCH, define the request body template
6. Configure how to parse the response

Variables in URL/body are substituted from agent inputs using {variable_name} syntax.
""",
    example_use_cases=[
        "Trigger deployments via CI/CD webhooks",
        "Create tickets in project management systems",
        "Query external data APIs",
        "Send data to analytics platforms",
        "Integrate with third-party services"
    ],
    tags=["api", "webhook", "http", "rest", "integration"]
)

# -----------------------------------------------------------------------------
# 3. IMAGE/VIDEO GENERATION TOOLS
# -----------------------------------------------------------------------------

IMAGE_OPENAI_DALLE3_TEMPLATE = ToolTemplate(
    template_id="image_openai_dalle3",
    name="DALL-E 3 Image Generator",
    description="Generate images using OpenAI's DALL-E 3 model",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="🎨",
    priority=85,
    is_featured=True,
    config_template={
        "tool_type": "image_video",
        "template_type": "image_openai_dalle3",
        "implementation_config": {
            "provider": "openai",
            "model": "dall-e-3",
            "api_key": "",  # USER MUST PROVIDE
            "size": "1024x1024",
            "quality": "standard",
            "style": "vivid",
            "timeout": 60
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image generation prompt"
            },
            "size": {
                "type": "string",
                "description": "Image size: 1024x1024, 1792x1024, or 1024x1792",
                "default": "1024x1024"
            },
            "quality": {
                "type": "string",
                "description": "Image quality: standard or hd",
                "default": "standard"
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=["api_key"],
    setup_instructions="""
1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Ensure you have DALL-E 3 access enabled
3. Paste your API key below (it will be encrypted)

Note: DALL-E 3 generates one image per request. Costs vary by size and quality.
""",
    example_use_cases=[
        "Generate marketing visuals from product descriptions",
        "Create illustrations for blog posts",
        "Visualize concepts and ideas",
        "Generate placeholder images",
        "Create custom artwork based on text"
    ],
    tags=["image", "generation", "openai", "dalle", "art"]
)

VIDEO_OPENAI_SORA_TEMPLATE = ToolTemplate(
    template_id="video_openai_sora",
    name="Sora Video Generator",
    description="Generate videos using OpenAI's Sora model",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="🎬",
    priority=80,
    is_featured=False,
    config_template={
        "tool_type": "image_video",
        "template_type": "image_openai_sora",
        "implementation_config": {
            "provider": "openai",
            "model": "sora",
            "api_key": "",  # USER MUST PROVIDE
            "duration": 5,
            "resolution": "1080p",
            "timeout": 120
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Video generation prompt"
            },
            "duration": {
                "type": "integer",
                "description": "Video duration in seconds (3-60)",
                "default": 5
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=["api_key"],
    setup_instructions="""
1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Ensure you have Sora access (may require waitlist approval)
3. Paste your API key below

Note: Sora is OpenAI's video generation model. Check availability and pricing.
""",
    example_use_cases=[
        "Generate video content from text descriptions",
        "Create animated product demonstrations",
        "Produce short video clips for social media",
        "Visualize concepts in motion"
    ],
    tags=["video", "generation", "openai", "sora", "animation"]
)

IMAGE_OPENAI_GPT_IMAGE_1_5_TEMPLATE = ToolTemplate(
    template_id="image_openai_gpt_image_1_5",
    name="GPT-Image-1.5 Generator",
    description="Generate and edit images using OpenAI's latest GPT-Image-1.5 model (December 2025) - 4x faster, enhanced instruction following, precise editing, and legible text rendering",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="🖼️",
    priority=88,
    is_featured=True,
    config_template={
        "tool_type": "image_video",
        "template_type": "image_openai_gpt_image_1_5",
        "implementation_config": {
            "provider": "openai",
            "model": "gpt-image-1.5",
            "api_key": "",  # USER MUST PROVIDE
            "size": "1024x1024",
            "quality": "high",
            "background": "auto",
            "moderation": "auto",
            "output_format": "png",
            "timeout": 90
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed image generation prompt. GPT-Image-1.5 excels at instruction following, precise editing, and rendering legible text in images."
            },
            "size": {
                "type": "string",
                "description": "Image size: 1024x1024 (square), 1536x1024 (landscape), 1024x1536 (portrait), or auto",
                "default": "1024x1024"
            },
            "quality": {
                "type": "string",
                "description": "Image quality: low (faster, less detail), medium (balanced), high (maximum detail)",
                "enum": ["low", "medium", "high"],
                "default": "high"
            },
            "background": {
                "type": "string",
                "description": "Background type: transparent, opaque, or auto (model decides)",
                "enum": ["transparent", "opaque", "auto"],
                "default": "auto"
            },
            "n": {
                "type": "integer",
                "description": "Number of images to generate (1-4)",
                "default": 1,
                "minimum": 1,
                "maximum": 4
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=["api_key"],
    setup_instructions="""
🖼️ **GPT-Image-1.5**

OpenAI's latest image generation model, released December 16, 2025. 4x faster than previous versions.

**Setup:**
1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Ensure your account has access to gpt-image-1.5
3. Paste your API key below

**Key Features:**
- ⚡ **4x Faster**: Significantly faster generation than previous models
- 🎯 **Enhanced Instruction Following**: Better understanding of prompts
- ✏️ **Precise Editing**: Add, change, or remove objects, styles, and clothing
- 🔤 **Legible Text**: Improved text rendering in generated images
- 🎨 **Style Control**: More accurate style and clothing modification

**Quality Levels:**
- `low`: Faster generation, lower detail
- `medium`: Balanced speed and quality
- `high`: Maximum detail, best for final outputs

**Pricing:**
~$0.04 per image (1024x1024, high quality)

**Best For:**
- Marketing materials with accurate text/logos
- Product mockups and designs
- Illustrations requiring precise details
- Social media graphics with embedded text
""",
    example_use_cases=[
        "Generate marketing materials with accurate text and logos",
        "Create product mockups with realistic branding",
        "Design social media graphics with embedded text",
        "Illustrate concepts with precise contextual accuracy",
        "Generate images with transparent backgrounds for compositing",
        "Create detailed illustrations for documentation"
    ],
    tags=["image", "generation", "openai", "gpt-image-1.5", "fast", "text-rendering", "editing", "featured"]
)

IMAGE_GEMINI_IMAGEN3_TEMPLATE = ToolTemplate(
    template_id="image_gemini_imagen3",
    name="Imagen 3 Image Generator",
    description="Generate images using Google's Imagen 3 model",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="🖼️",
    priority=75,
    is_featured=False,
    config_template={
        "tool_type": "image_video",
        "template_type": "image_gemini_imagen3",
        "implementation_config": {
            "provider": "google",
            "model": "imagen-3",
            "aspect_ratio": "1:1",
            "num_images": 1,
            "safety_filter_level": "block_most",
            "timeout": 60
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image generation prompt"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4",
                "default": "1:1"
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=[],
    setup_instructions="""
🖼️ **Imagen 3**

API Key: Configured in Settings page

Note: Imagen 3 offers high-quality photorealistic and artistic image generation.
""",
    example_use_cases=[
        "Generate photorealistic product images",
        "Create artistic interpretations",
        "Produce marketing visuals",
        "Generate concept art"
    ],
    tags=["image", "generation", "google", "gemini", "imagen"]
)

IMAGE_GEMINI_NANO_BANANA_TEMPLATE = ToolTemplate(
    template_id="image_gemini_nano_banana",
    name="Nano Banana Pro (Gemini 3 Pro Image)",
    description="High-quality AI image generation using Gemini 3 Pro Image - Google's best model with 2K/4K output, text rendering, and character consistency",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="🍌",
    priority=90,
    is_featured=True,
    config_template={
        "tool_type": "image_video",
        "template_type": "image_gemini_nano_banana",
        "implementation_config": {
            "provider": "google",
            "model": "gemini-3-pro-image-preview",
            "aspect_ratio": "1:1",
            "number_of_images": 1,
            "safety_filter_level": "block_some",
            "timeout": 45
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed image generation prompt"
            },
            "negative_prompt": {
                "type": "string",
                "description": "Elements to avoid in the image (optional)",
                "default": ""
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Image aspect ratio: 1:1, 16:9, 9:16, 4:3, or 3:4",
                "default": "1:1"
            },
            "style": {
                "type": "string",
                "description": "Image style: photorealistic, artistic, anime, illustration, or default",
                "default": "default"
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=[],
    setup_instructions="""
🍌 **Nano Banana (Gemini 2.5 Flash Image)**

API Key: Configured in Settings page

**Features:**
- Ultra-fast image generation (2-5 seconds)
- Multimodal inputs (text + reference images)
- Character consistency across generations
- Image editing (inpainting, outpainting, blending)
- High-resolution output with upscaling
- Natural scene reconstruction

💰 **Pricing:**
~$0.01-0.03 per image (significantly cheaper than DALL-E 3)

✨ **Best For:**
- Rapid prototyping and iteration
- Batch image generation
- Character-consistent artwork
- Marketing visuals & social media graphics
- Illustrated blog posts and articles
- Image blending and composition
""",
    example_use_cases=[
        "Generate marketing visuals from research reports",
        "Create consistent character artwork for stories",
        "Produce illustrations for blog posts and articles",
        "Generate social media graphics in bulk",
        "Create mockups and prototypes with visual elements",
        "Blend multiple images into cohesive compositions",
        "Add visual elements to automated content"
    ],
    tags=["image", "generation", "google", "gemini", "nano-banana", "fast", "featured", "workflow"]
)

VIDEO_GEMINI_VEO3_TEMPLATE = ToolTemplate(
    template_id="video_gemini_veo3",
    name="Veo 3 Video Generator",
    description="Generate videos using Google's Veo 3 model",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="📹",
    priority=70,
    is_featured=False,
    config_template={
        "tool_type": "image_video",
        "template_type": "video_gemini_veo3",
        "implementation_config": {
            "provider": "google",
            "model": "veo-3",
            "api_key": "",  # USER MUST PROVIDE
            "duration": 5,
            "resolution": "1080p",
            "fps": 24,
            "aspect_ratio": "16:9",
            "timeout": 120
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Video generation prompt"
            },
            "duration": {
                "type": "integer",
                "description": "Video duration in seconds",
                "default": 5
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Video aspect ratio: 16:9, 9:16, 1:1, 4:3",
                "default": "16:9"
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=["api_key"],
    setup_instructions="""
1. Get your Google Cloud API key with Vertex AI access
2. Enable the Veo API in your Google Cloud Console
3. Paste your API key below

Note: Veo 3 is Google's advanced video generation model.
""",
    example_use_cases=[
        "Generate video content from descriptions",
        "Create animated explainer videos",
        "Produce marketing video clips",
        "Generate motion graphics"
    ],
    tags=["video", "generation", "google", "gemini", "veo"]
)

VIDEO_GEMINI_VEO31_TEMPLATE = ToolTemplate(
    template_id="video_gemini_veo31",
    name="Veo 3.1 Fast Video Generator",
    description="Generate videos using Google's Veo 3.1 Fast model. Supports text-to-video, image-to-video animation, and video continuation/extension.",
    category="image_video",
    tool_type=ToolType.IMAGE_VIDEO,
    icon="🎬",
    priority=85,
    is_featured=True,
    config_template={
        "tool_type": "image_video",
        "template_type": "video_gemini_veo31",
        "implementation_config": {
            "provider": "google",
            "model": "veo-3.1-fast-generate-preview",
            "duration": 8,
            "resolution": "720p",
            "fps": 24,
            "aspect_ratio": "16:9",
            "generate_audio": True,
            "timeout": 180
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the video to generate, including desired actions, scenes, and style"
            },
            "image_url": {
                "type": "string",
                "description": "Optional: URL or base64 data URI of an image to animate (image-to-video mode)",
                "default": ""
            },
            "video_url": {
                "type": "string",
                "description": "Optional: URL of a previously generated Veo video to extend/continue",
                "default": ""
            },
            "duration": {
                "type": "integer",
                "description": "Video duration in seconds: 4, 6, or 8",
                "default": 8
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Video aspect ratio: 16:9 (landscape) or 9:16 (portrait)",
                "default": "16:9"
            },
            "negative_prompt": {
                "type": "string",
                "description": "Optional: Elements or styles to avoid in the video",
                "default": ""
            }
        },
        "required": ["prompt"]
    },
    required_user_fields=[],
    setup_instructions="""
🎬 **Veo 3.1 Fast Video Generator**

API Key: Configured in Settings page (uses GOOGLE_API_KEY)

**Three Generation Modes:**

1. **Text-to-Video**: Just provide a prompt
   ```json
   {"prompt": "A cat playing with yarn in a sunlit room"}
   ```

2. **Image-to-Video**: Animate an existing image
   ```json
   {
     "prompt": "The cat starts walking towards the camera",
     "image_url": "https://example.com/cat.jpg"
   }
   ```

3. **Video Extension**: Continue an existing Veo video
   ```json
   {
     "prompt": "The cat jumps onto the couch",
     "video_url": "https://storage.googleapis.com/your-bucket/previous-video.mp4"
   }
   ```

**Features:**
- Fast generation (Veo 3.1 Fast variant)
- Audio generation included
- Up to 8 seconds per clip
- Chain videos for up to 141 seconds total
- 720p resolution, 16:9 or 9:16 aspect ratio

**Best For:**
- Marketing videos and social media content
- Product animations
- Animated storytelling
- Extending video narratives
""",
    example_use_cases=[
        "Generate marketing video clips from product descriptions",
        "Animate product photos into dynamic video content",
        "Create video continuations for storytelling",
        "Produce social media video content",
        "Generate explainer video segments",
        "Chain multiple clips into longer narratives"
    ],
    tags=["video", "generation", "google", "veo", "fast", "image-to-video", "video-extension", "featured", "workflow"]
)

# -----------------------------------------------------------------------------
# 4. DATABASE TOOLS
# -----------------------------------------------------------------------------

DATABASE_POSTGRES_TEMPLATE = ToolTemplate(
    template_id="database_postgres",
    name="PostgreSQL Query",
    description="Execute SQL queries on PostgreSQL databases",
    category="database",
    tool_type=ToolType.DATABASE,
    icon="💾",
    priority=65,
    is_featured=False,
    config_template={
        "tool_type": "database",
        "template_type": "database_postgres",
        "implementation_config": {
            "db_type": "postgres",
            "connection_string": "",  # USER MUST PROVIDE (encrypted)
            "query_template": "SELECT * FROM {table} WHERE id = {id}",
            "read_only": True,
            "max_rows": 100,
            "timeout": 30
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "table": {
                "type": "string",
                "description": "Table name to query"
            },
            "id": {
                "type": "string",
                "description": "ID to lookup"
            }
        },
        "required": ["table", "id"]
    },
    required_user_fields=["connection_string"],
    setup_instructions="""
1. Prepare your PostgreSQL connection string:
   postgresql://username:password@host:port/database

2. For security, enable read-only mode to prevent data modification

3. Use parameterized queries with {variable} placeholders to prevent SQL injection

Warning: Connection strings are encrypted but should use read-only database users when possible.
""",
    example_use_cases=[
        "Query database for user information",
        "Retrieve product data for recommendations",
        "Lookup order status and details",
        "Fetch analytics data",
        "Verify data before processing"
    ],
    tags=["database", "sql", "postgresql", "query", "data"]
)

# -----------------------------------------------------------------------------
# 5. DATA TRANSFORM TOOLS
# -----------------------------------------------------------------------------

DATA_TRANSFORM_JSON_TEMPLATE = ToolTemplate(
    template_id="data_transform_json",
    name="Data Format Converter",
    description="Convert between JSON, CSV, XML, and YAML formats",
    category="data_transform",
    tool_type=ToolType.DATA_TRANSFORM,
    icon="🔄",
    priority=60,
    is_featured=False,
    config_template={
        "tool_type": "data_transform",
        "template_type": "data_transform_json",
        "implementation_config": {
            "input_format": "json",
            "output_format": "csv",
            "transformation_rules": [],
            "validate_output": True
        }
    },
    input_schema_template={
        "type": "object",
        "properties": {
            "data": {
                "type": "string",
                "description": "Data to transform"
            },
            "output_format": {
                "type": "string",
                "description": "Desired output format: json, csv, xml, yaml",
                "default": "json"
            }
        },
        "required": ["data"]
    },
    required_user_fields=[],
    setup_instructions="""
1. Select the input data format
2. Choose the desired output format
3. Optionally define transformation rules (JSONPath, mappings, etc.)
4. Enable output validation to ensure format correctness

Supports: JSON ↔ CSV ↔ XML ↔ YAML conversions
""",
    example_use_cases=[
        "Convert API responses from JSON to CSV for reporting",
        "Transform XML data to JSON for processing",
        "Generate YAML configs from JSON",
        "Extract specific fields using JSONPath",
        "Reshape data structures"
    ],
    tags=["data", "transform", "convert", "json", "csv", "xml", "yaml"]
)


# =============================================================================
# REGISTRY INITIALIZATION
# =============================================================================

def initialize_tool_templates():
    """Register all built-in tool templates"""
    # Notification tools (PRIORITY)
    ToolTemplateRegistry.register(NOTIFICATION_SLACK_TEMPLATE)
    ToolTemplateRegistry.register(NOTIFICATION_DISCORD_TEMPLATE)

    # CMS/Publishing tools
    ToolTemplateRegistry.register(CMS_WORDPRESS_TEMPLATE)
    ToolTemplateRegistry.register(SOCIAL_TWITTER_TEMPLATE)

    # API tools
    ToolTemplateRegistry.register(API_WEBHOOK_TEMPLATE)

    # Image/Video tools
    ToolTemplateRegistry.register(IMAGE_OPENAI_DALLE3_TEMPLATE)
    ToolTemplateRegistry.register(VIDEO_OPENAI_SORA_TEMPLATE)
    ToolTemplateRegistry.register(IMAGE_OPENAI_GPT_IMAGE_1_5_TEMPLATE)  # Featured: GPT-Image-1.5 - 4x faster with enhanced editing
    ToolTemplateRegistry.register(IMAGE_GEMINI_IMAGEN3_TEMPLATE)
    ToolTemplateRegistry.register(IMAGE_GEMINI_NANO_BANANA_TEMPLATE)  # Featured: Ultra-fast & cost-effective
    ToolTemplateRegistry.register(VIDEO_GEMINI_VEO3_TEMPLATE)
    ToolTemplateRegistry.register(VIDEO_GEMINI_VEO31_TEMPLATE)  # Featured: Text-to-video, image-to-video, video extension

    # Database tools
    ToolTemplateRegistry.register(DATABASE_POSTGRES_TEMPLATE)

    # Data transform tools
    ToolTemplateRegistry.register(DATA_TRANSFORM_JSON_TEMPLATE)


# Initialize templates on module import
initialize_tool_templates()
