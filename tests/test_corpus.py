"""Test corpus of 55+ realistic JSON payloads to verify >=95% pass rate (PRD Section 11)."""

import json
import pytest
from json2py.agent.loop import AgentConverter
from json2py.models import OutputFormat

CORPUS: list[tuple[str, dict | list]] = [
    ("GitHub User", {
        "login": "octocat",
        "id": 1,
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "site_admin": False,
        "name": "monalisa octocat",
        "company": "GitHub",
        "blog": "https://github.blog",
        "location": "San Francisco",
        "email": "octocat@github.com",
        "hireable": False,
        "bio": "There once was...",
        "public_repos": 2,
        "followers": 20,
        "created_at": "2008-01-14T04:33:35Z"
    }),
    ("GitHub Commit", {
        "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
        "commit": {
            "author": {"name": "Monalisa Octocat", "email": "support@github.com", "date": "2011-04-14T16:00:49Z"},
            "message": "Fix all the bugs",
            "comment_count": 0
        },
        "url": "https://api.github.com/repos/octocat/Hello-World/commits/6dcb09b5b57875f334f61aebed695e2e4193db5e"
    }),
    ("Stripe Charge", {
        "id": "ch_3MtwBwLkdIwHu7ix0snAYzP5",
        "object": "charge",
        "amount": 1099,
        "captured": True,
        "currency": "usd",
        "customer": None,
        "description": "Donation charge",
        "paid": True,
        "status": "succeeded"
    }),
    ("Stripe Subscription", {
        "id": "sub_1MtwBwLkdIwHu7ix0snAYzP5",
        "cancel_at_period_end": False,
        "current_period_end": 1682498765,
        "status": "active",
        "items": [{"id": "si_123", "quantity": 1, "price": 49.99}]
    }),
    ("Slack Webhook", {
        "channel": "#general",
        "username": "webhookbot",
        "text": "Deployment complete for v1.0.0!",
        "icon_emoji": ":rocket:",
        "attachments": [{"color": "#36a64f", "title": "Deploy Details", "fallback": "Success"}]
    }),
    ("AWS S3 Put Event", {
        "eventVersion": "2.1",
        "eventSource": "aws:s3",
        "awsRegion": "us-east-1",
        "eventTime": "2026-09-28T17:31:29Z",
        "eventName": "ObjectCreated:Put",
        "s3": {
            "bucket": {"name": "my-dataset-bucket", "arn": "arn:aws:s3:::my-dataset-bucket"},
            "object": {"key": "data/2026/09/metrics.json", "size": 104857}
        }
    }),
    ("Kubernetes Pod Spec", {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "nginx-demo", "labels": {"app": "nginx"}},
        "spec": {
            "containers": [{"name": "nginx", "image": "nginx:1.14.2", "ports": [{"containerPort": 80}]}]
        }
    }),
    ("OpenWeather Current", {
        "coord": {"lon": 80.27, "lat": 13.08},
        "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
        "main": {"temp": 32.5, "feels_like": 36.8, "humidity": 65},
        "name": "Chennai"
    }),
    ("Twitter Tweet", {
        "id_str": "1346889432242040833",
        "text": "Hello world from autonomous AI agent!",
        "retweet_count": 42,
        "favorite_count": 128,
        "created_at": "2026-09-28T17:31:29Z"
    }),
    ("YouTube Video Metadata", {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up",
        "viewCount": "1500000000",
        "likeCount": "16000000",
        "tags": ["music", "pop", "80s"]
    }),
    ("Spotify Track", {
        "id": "0VjIjW4GlUZAMYd2vXMi3b",
        "name": "Blinding Lights",
        "duration_ms": 200040,
        "explicit": False,
        "popularity": 95,
        "artists": [{"id": "1Xyo4u8uXC1ZmMpatF05PJ", "name": "The Weeknd"}]
    }),
    ("GeoJSON FeatureCollection", {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [80.2707, 13.0827]},
                "properties": {"city": "Chennai", "population": 7000000}
            }
        ]
    }),
    ("E-commerce Order", {
        "order_number": "10029",
        "customer": {"name": "Alice Smith", "email": "alice@smith.org"},
        "line_items": [
            {"sku": "SKU-A", "unit_price": 25.50, "qty": 2},
            {"sku": "SKU-B", "unit_price": 99.00, "qty": 1}
        ],
        "discount": None
    }),
    ("Zendesk Ticket", {
        "id": 35436,
        "subject": "Help with integration",
        "status": "open",
        "priority": "normal",
        "requester_id": 20978392,
        "tags": ["enterprise", "p1"]
    }),
    ("Stock Quote", {
        "symbol": "GOOGL",
        "price": 182.45,
        "change": 1.25,
        "change_percent": 0.69,
        "volume": 25400000
    }),
    ("Docker Inspect", {
        "Id": "4a7f6f1947b7",
        "Created": "2026-09-28T17:31:29Z",
        "Path": "/bin/sh",
        "State": {"Status": "running", "Running": True, "Pid": 1234}
    }),
    ("GitLab CI Pipeline", {
        "id": 46,
        "iid": 11,
        "status": "success",
        "ref": "main",
        "duration": 180,
        "user": {"name": "Developer"}
    }),
    ("Jira Issue", {
        "key": "PROJ-101",
        "fields": {
            "summary": "Implement agent self-repair loop",
            "issuetype": {"name": "Story"},
            "priority": {"name": "High"}
        }
    }),
    ("Twilio SMS Callback", {
        "MessageSid": "SM1234567890abcdef",
        "AccountSid": "ACabcdef1234567890",
        "From": "+15551234567",
        "To": "+15557654321",
        "Body": "Your verification code is 849201",
        "NumSegments": "1"
    }),
    ("Google Calendar Event", {
        "id": "cal_evt_1",
        "summary": "Team Sync",
        "start": {"dateTime": "2026-09-28T18:00:00Z"},
        "end": {"dateTime": "2026-09-28T18:30:00Z"},
        "attendees": [{"email": "team@example.com", "responseStatus": "accepted"}]
    }),
    ("Zoom Meeting", {
        "id": 98765432101,
        "topic": "Architecture Review",
        "type": 2,
        "start_time": "2026-09-28T19:00:00Z",
        "duration": 45,
        "timezone": "UTC"
    }),
    ("Segment Track Event", {
        "anonymousId": "507f1f77bcf86cd799439011",
        "event": "Button Clicked",
        "properties": {"button_color": "blue", "page": "/checkout"}
    }),
    ("Salesforce Lead", {
        "Id": "00Q5g000001abc",
        "FirstName": "Jane",
        "LastName": "Doe",
        "Company": "Acme Corp",
        "Status": "Working - Contacted"
    }),
    ("Shopify Product Webhook", {
        "id": 632910392,
        "title": "Burton Custom Freestyle 151",
        "vendor": "Burton",
        "variants": [{"id": 808950810, "price": "699.00", "sku": "burton-151"}]
    }),
    ("OpenAI Chat Completion", {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}}]
    }),
    ("Datadog Monitor Alert", {
        "id": 12345678,
        "name": "High CPU utilization",
        "status": "Alert",
        "query": "avg(last_5m):avg:system.cpu.user{*} > 90"
    }),
    ("PagerDuty Incident", {
        "id": "PT4KHLK",
        "type": "incident",
        "summary": "Database connectivity loss",
        "urgency": "high"
    }),
    ("Auth0 Log Event", {
        "type": "sapi",
        "description": "Update a client",
        "client_name": "Antigravity App",
        "ip": "192.168.1.1"
    }),
    ("Mailchimp Campaign", {
        "id": "42694e9e57",
        "type": "regular",
        "emails_sent": 1500,
        "report_summary": {"opens": 650, "unique_opens": 600, "clicks": 180}
    }),
    ("PayPal Transaction", {
        "transaction_id": "8AA1234567890",
        "status": "COMPLETED",
        "amount": {"value": "45.00", "currency_code": "USD"}
    }),
    ("Fastly CDN Log", {
        "timestamp": "2026-09-28T17:31:29Z",
        "client_ip": "203.0.113.195",
        "geo_country": "US",
        "response_status": 200
    }),
    ("Firebase DB Export", {
        "users": {
            "usr_1": {"name": "Admin", "level": 10},
            "usr_2": {"name": "Guest", "level": 1}
        }
    }),
    ("Grafana Panel", {
        "id": 2,
        "title": "Network Traffic",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
    }),
    ("Terraform Resource", {
        "type": "aws_instance",
        "name": "web_server",
        "provider": "aws",
        "instances": [{"attributes": {"ami": "ami-0c55b159cbfafe1f0", "instance_type": "t2.micro"}}]
    }),
    ("Discord Member", {
        "nick": "SpeedyDev",
        "roles": ["1029384756", "9876543210"],
        "joined_at": "2026-09-28T17:31:29Z",
        "deaf": False,
        "mute": False
    }),
    ("Trello Card", {
        "id": "5a7c4f19",
        "name": "Refactor parser",
        "closed": False,
        "labels": [{"name": "Core", "color": "green"}]
    }),
    ("Notion Page", {
        "id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
        "created_time": "2026-09-28T17:31:29Z",
        "archived": False,
        "url": "https://www.notion.so/page-c9bf9e57"
    }),
    ("Asana Task", {
        "gid": "12001",
        "name": "Review PRD documentation",
        "completed": True,
        "due_on": "2026-09-28"
    }),
    ("Airtable Record", {
        "id": "rec1234567890",
        "fields": {"Project Name": "JSON2PY", "Budget": 50000, "Approved": True}
    }),
    ("Cloudflare DNS Record", {
        "id": "372e67954025e0ba6aaa6d586b9e0b59",
        "type": "A",
        "name": "example.com",
        "content": "198.51.100.4",
        "ttl": 3600
    }),
    ("Intercom Message", {
        "id": "msg_9981",
        "body": "<p>Thanks for reaching out!</p>",
        "author": {"type": "admin", "id": "25"}
    }),
    ("Sentry Error", {
        "event_id": "fc6d8c0c43fc4630ad850ee518f1b9d0",
        "level": "error",
        "culprit": "json2py.core.parser",
        "message": "Division by zero"
    }),
    ("Mixpanel Event", {
        "event": "Signed Up",
        "properties": {"$browser": "Chrome", "$city": "Chennai", "plan": "pro"}
    }),
    ("SendGrid Webhook", {
        "email": "receiver@example.com",
        "timestamp": 1672531199,
        "event": "delivered",
        "sg_message_id": "sendgrid_123"
    }),
    ("Bitbucket PR", {
        "id": 12,
        "title": "Feature: autonomous self-repair",
        "state": "MERGED",
        "author": {"display_name": "Avinaash"}
    }),
    ("CircleCI Build", {
        "build_num": 104,
        "branch": "main",
        "status": "success",
        "outcome": "success"
    }),
    ("Redis Monitor", {
        "time": "1672531199.123",
        "command": "SET",
        "args": ["user:101", "active"]
    }),
    ("ElasticSearch Hit", {
        "_index": "logs-2026",
        "_id": "doc_101",
        "_score": 1.45,
        "_source": {"message": "Service started successfully", "port": 8080}
    }),
    ("GraphQL Response", {
        "data": {
            "hero": {
                "name": "R2-D2",
                "friends": [{"name": "Luke Skywalker"}, {"name": "Han Solo"}]
            }
        }
    }),
    ("Deeply Nested Hierarchy", {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "level5": {
                            "value": "deep_payload"
                        }
                    }
                }
            }
        }
    }),
    ("Top-Level Array Payload", [
        {"item_id": 1, "sku": "A1"},
        {"item_id": 2, "sku": "B2"}
    ]),
    ("Multi Format Strings", {
        "uuid_val": "123e4567-e89b-12d3-a456-426614174000",
        "date_val": "2026-09-28",
        "datetime_val": "2026-09-28T17:31:29Z",
        "url_val": "https://example.com/api",
        "email_val": "test@domain.com"
    }),
    ("Numeric Extremes", {
        "zero_int": 0,
        "large_int": 9223372036854775807,
        "small_float": 0.0000001,
        "negative_int": -42,
        "negative_float": -3.14159
    }),
    ("Boolean Matrix", {
        "flag_a": True,
        "flag_b": False,
        "flag_list": [True, False, True]
    }),
    ("Python Keyword Collisions", {
        "class": "Math",
        "from": "School",
        "def": 1,
        "import": 2,
        "in": 3,
        "is": 4,
        "return": "result",
        "pass": True
    }),
]


def test_corpus_size():
    """Verify corpus meets or exceeds the 50+ payloads requirement."""
    assert len(CORPUS) >= 50


@pytest.mark.parametrize("name,payload", CORPUS)
def test_pydantic_conversion_on_corpus(name, payload):
    """Test that each corpus payload compiles and validates with Pydantic v2."""
    converter = AgentConverter()
    raw = json.dumps(payload)
    result = converter.convert(raw, output_format=OutputFormat.PYDANTIC, root_name="Model")
    assert result.status == "validated", f"Failed on '{name}': {result.warnings or result.validation_result.errors}"
    assert result.validation_result is not None
    assert result.validation_result.is_valid is True


@pytest.mark.parametrize("name,payload", CORPUS)
def test_dataclass_conversion_on_corpus(name, payload):
    """Test that each corpus payload compiles and validates with Dataclass."""
    converter = AgentConverter()
    raw = json.dumps(payload)
    result = converter.convert(raw, output_format=OutputFormat.DATACLASS, root_name="Model")
    assert result.status == "validated", f"Failed on '{name}': {result.warnings or result.validation_result.errors}"
    assert result.validation_result is not None
    assert result.validation_result.is_valid is True
