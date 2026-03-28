"""Guided batch annotation prompt."""

from __future__ import annotations

from cartograph.server.main import mcp


@mcp.prompt()
def annotate_batch(batch_size: int = 10) -> str:
    """Guide an agent through annotating unannotated nodes in batches."""
    return (
        "You are annotating codebase nodes with summaries, tags, and roles "
        "using Cartographing Kittens' annotation tools.\n"
        "\n"
        "Follow these steps:\n"
        "\n"
        "1. Call annotation_status to see how many nodes still need "
        "annotation and the overall progress.\n"
        f"2. Call get_pending_annotations with limit={batch_size} to "
        "retrieve the next batch of unannotated nodes.\n"
        "3. For each node in the batch:\n"
        "   - Read its source code or query its metadata\n"
        "   - Write a concise one-line summary of its purpose\n"
        "   - Assign relevant tags (e.g. 'api', 'util', 'model', 'test')\n"
        "   - Assign a role (e.g. 'entry-point', 'helper', 'data-class')\n"
        "4. Call submit_annotations with all the annotations you produced.\n"
        "5. Check annotation_status again. If nodes remain, repeat from "
        "step 2 until all nodes are annotated."
    )
