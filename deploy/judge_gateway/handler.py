"""Three public project tools behind AgentCore Gateway's Lambda target."""

import os

TOOLS = [
    {
        "name": "search_project_docs",
        "description": "Search the owned public Treehouse project document and return a grounded answer with source citations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question about Treehouse public facts"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_task_cards",
        "description": "List the three Treehouse judge demonstration tasks.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "explain_rule",
        "description": "Explain a public Treehouse evidence rule.",
        "inputSchema": {
            "type": "object",
            "properties": {"rule_id": {"type": "string", "description": "One of evidence, privacy, budget"}},
            "required": ["rule_id"],
        },
    },
]
RULES = {
    "evidence": "Simulation is not field measurement. Only actual AWS transport receipts and source citations demonstrate the live challenge path.",
    "privacy": "Ingest only the owned public project note. Do not ingest private imagery, locations, answer keys or recordings of other people.",
    "budget": "Challenge budget is $15 with a stop at $25. Billing lags; stop calls before the bound, and retain existing account guards.",
}


def dispatch(event, context, *, client=None):
    name = context.client_context.custom["bedrockAgentCoreToolName"].split("___")[-1]
    if name == "list_task_cards":
        return {
            "tasks": [
                "Know Your Stuff: cited owned-document answer",
                "Gateway Builder: three MCP tools and an actual agent tool call",
                "Ship It: a real Runtime endpoint answer",
            ],
            "request_id": context.aws_request_id,
        }
    if name == "explain_rule":
        rule = event.get("rule_id")
        if rule not in RULES:
            raise ValueError("Unknown public rule")
        return {"rule_id": rule, "explanation": RULES[rule], "request_id": context.aws_request_id}
    if name != "search_project_docs":
        raise ValueError("Unknown Gateway tool")
    query = event.get("query")
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 4000:
        raise ValueError("Query must contain 1–4000 characters")
    if client is None:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "bedrock-agent-runtime",
            region_name="us-east-1",
            config=Config(connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 1}),
        )
    response = client.retrieve_and_generate(
        input={"text": query.strip()},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": os.environ["KNOWLEDGE_BASE_ID"],
                "modelArn": f"arn:aws:bedrock:us-east-1::foundation-model/{os.environ['MODEL_ID']}",
                "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": 3}},
                "generationConfiguration": {
                    "inferenceConfig": {"textInferenceConfig": {"maxTokens": 600, "temperature": 0.0}}
                },
            },
        },
    )
    citations = []
    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri")
            if uri:
                item = {"uri": uri, "quote": ref.get("content", {}).get("text", "")}
                if item not in citations:
                    citations.append(item)
    return {
        "answer": response["output"]["text"],
        "citations": citations,
        "knowledge_base_id": os.environ["KNOWLEDGE_BASE_ID"],
        "request_id": response.get("ResponseMetadata", {}).get("RequestId"),
        "lambda_request_id": context.aws_request_id,
    }


def lambda_handler(event, context):
    return dispatch(event, context)
