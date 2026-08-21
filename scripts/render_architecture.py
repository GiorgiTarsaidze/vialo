#!/usr/bin/env python3
"""Render the Vialo AWS architecture as a PNG with official service icons.

The README carries a mermaid version of this, which is right for GitHub because
it stays readable in a diff. This one exists for the demo video, where a flat
image with the real AWS marks reads faster on screen than a text diagram.

Requires graphviz on PATH. The `diagrams` package is not a project dependency and
is deliberately not in backend/pyproject.toml: nothing at runtime needs it.

    uv venv /tmp/diagvenv
    uv pip install --python /tmp/diagvenv/bin/python diagrams
    /tmp/diagvenv/bin/python scripts/render_architecture.py [output-dir]

Colours follow .kiro/steering/design-system.md so the frame matches the product.
"""

from __future__ import annotations

import sys
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.ml import Bedrock
from diagrams.aws.general import GenericSDK
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import Cognito
from diagrams.aws.storage import SimpleStorageServiceS3
from diagrams.onprem.client import Users

CANVAS = "#fff8ea"
INK = "#2b2326"
PLUM = "#6f3e59"
MUTED = "#6d6064"

GRAPH_ATTR = {
    "bgcolor": CANVAS,
    "fontname": "Inter, Helvetica, Arial, sans-serif",
    "fontcolor": INK,
    "fontsize": "20",
    "pad": "0.6",
    "nodesep": "0.45",
    "ranksep": "0.9",
    "splines": "spline",
}

NODE_ATTR = {
    "fontname": "Inter, Helvetica, Arial, sans-serif",
    "fontcolor": INK,
    "fontsize": "12",
}

EDGE_ATTR = {
    "color": PLUM,
    "fontname": "Inter, Helvetica, Arial, sans-serif",
    "fontcolor": MUTED,
    "fontsize": "11",
    "penwidth": "1.6",
}

CLUSTER_ATTR = {
    "bgcolor": "#fffcf5",
    "pencolor": "#e7d8d1",
    "fontname": "Inter, Helvetica, Arial, sans-serif",
    "fontcolor": PLUM,
    "fontsize": "15",
    "penwidth": "1.6",
    "margin": "18",
}


def render(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / "vialo-aws-architecture"

    with Diagram(
        "Vialo runs entirely on AWS",
        filename=str(stem),
        outformat="png",
        show=False,
        direction="TB",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        browser = Users("Browser\nReact 18 + TypeScript SPA")

        with Cluster("AWS  ·  us-east-1", graph_attr=CLUSTER_ATTR):
            cdn = CloudFront("CloudFront\nTLS · CSP · SPA rewrite")
            s3_site = SimpleStorageServiceS3("S3 frontend\nprivate, OAC only")
            s3_media = SimpleStorageServiceS3("S3 Journal media\nprivate, OAC only")
            gateway = APIGateway("API Gateway\n2 req/s, burst 5")
            fn = Lambda("Lambda · Python 3.12\nARM64 · 1769 MB · 30 s")
            cognito = Cognito("Cognito user pool\nhosted UI · PKCE · sign in")
            bedrock = Bedrock("Bedrock\nClaude Sonnet 4.6")
            cache = Dynamodb("DynamoDB\nplace cache")
            limits = Dynamodb("DynamoDB\nlimits + spend")
            shares = Dynamodb("DynamoDB\nshares, 30-day TTL")
            journal = Dynamodb("DynamoDB\nJournal, 3 GSIs")

        with Cluster("Google Maps Platform", graph_attr=CLUSTER_ATTR):
            places = GenericSDK("Places API\ngrounding + hours")
            routes = GenericSDK("Routes API\nmatrix + geometry")

        browser >> Edge(label="https") >> cdn

        cdn >> Edge(style="dashed") >> s3_site
        cdn >> Edge(style="dashed", label="/media/*") >> s3_media
        cdn >> Edge(label="/api/*") >> gateway
        gateway >> fn

        fn >> Edge(label="verify JWT", style="dashed", color=MUTED) >> cognito

        fn >> Edge(label="candidates") >> bedrock
        fn >> Edge(color=MUTED) >> cache
        fn >> Edge(color=MUTED) >> limits
        fn >> Edge(color=MUTED) >> shares
        fn >> Edge(color=MUTED) >> journal

        fn >> Edge(label="place_id, hours") >> places
        fn >> Edge(label="travel time") >> routes

    return stem.with_suffix(".png")


if __name__ == "__main__":
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.cwd()
    written = render(target)
    print(f"wrote {written}")
