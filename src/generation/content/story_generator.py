"""Story generator - Plans narrative arc and creates draft slides.

Architecture:
- GENERATION: Always from source content (no atoms dependency)
- REFINEMENT: Prefers atoms if available, falls back to source content

Generates draft slides with:
- story: Narrative description
- atoms: Empty for source-based, IDs for atom-based refinement
- density: Information density
- visual_design: Visual approach

Layout and widgets are empty (filled by ContentTool).
"""
from __future__ import annotations

import json
import os
import re
from typing import List, Dict, Any, Optional

from src.generation.atom.collection import AtomCollection
from src.utils.llm_client import call_llm


def _get_atom_content(atom) -> str:
    """Extract displayable content from any atom type."""
    # Try different field names based on atom type
    if hasattr(atom, 'text') and atom.text:
        return atom.text
    if hasattr(atom, 'quote') and atom.quote:
        return atom.quote
    if hasattr(atom, 'description') and atom.description:
        return atom.description
    if hasattr(atom, 'name') and atom.name:
        # BioAtom
        parts = [atom.name]
        if hasattr(atom, 'role') and atom.role:
            parts.append(atom.role)
        if hasattr(atom, 'affiliation') and atom.affiliation:
            parts.append(atom.affiliation)
        return " - ".join(parts)
    if hasattr(atom, 'value') and hasattr(atom, 'label'):
        # StatAtom
        return f"{atom.value} ({atom.label})"
    # Fallback to abstract
    if hasattr(atom, 'abstract') and atom.abstract:
        return atom.abstract
    return str(atom.id)


def _get_atom_type(atom) -> str:
    """Get the type name of an atom."""
    return type(atom).__name__


def _build_story_prompt(
    content_section: str,
    atoms_description: str,
    example_atoms_value: str,
    user_instruction: str,
    intent_guidance: str,
    slide_count: Optional[int],
) -> str:
    """Shared prompt builder for story generation.
    
    Args:
        content_section: The input content section (source or atoms)
        atoms_description: Description of atoms field in output
        example_atoms_value: Example value for atoms field in JSON
        user_instruction: User's instruction
        intent_guidance: Guidance from constitution
        slide_count: Target number of slides
    """
    target_slides = slide_count or 10
    
    return f"""You are a STORYTELLER who designs presentation narratives.

# INPUT

{content_section}

## User Instruction
{user_instruction or "Create a compelling presentation"}

## Guidance
{intent_guidance or "None"}

## Target Slides
{target_slides} slides

# OUTPUT

Create draft slides with story arc. Each slide needs:
- id: Unique ID (e.g., "slide_01_hook")
- rank: Order (1-based)
- state: "draft"
- story: Narrative purpose (what this slide accomplishes in the story)
- atoms: {atoms_description}
- density: "minimal" (1-2 points) | "moderate" (3-4) | "dense" (5+)
- visual_design: FREE TEXT describing how to visualize. Include:
  - Desired elements (big number, quote, bullet list, chart, image placeholder, etc.)
  - Orientation/layout concept (left-heavy hero, centered, side-by-side comparison, grid of items, etc.)
  - Visual emphasis (what should stand out, what's supporting)
  - Rough spatial arrangement

Examples of visual_design:
- "Large stat on left (the key number), supporting context text on right"
- "Centered bold quote with author attribution below"
- "Side-by-side comparison: before state left, after state right"
- "Grid of 4 feature cards, each with icon placeholder and short label"
- "Timeline flowing left to right with 5 milestone markers"
- "Full-bleed dramatic single statement, minimal text"
- "Dashboard style: 3 metric cards on top, chart area below"

Leave layout and widgets EMPTY (filled later):
- layout: ""
- widgets: {{}}

# STORY ARC STRUCTURE

1. **HOOK** (1-2 slides): Grab attention with surprising fact or question
2. **CONTEXT** (2-3 slides): Set the scene, establish stakes
3. **JOURNEY** (3-5 slides): Main content, building tension/interest
4. **INSIGHT** (2-3 slides): Key revelations, "aha" moments
5. **CLOSE** (1-2 slides): Resolution, call to action, memorable end

# OUTPUT FORMAT

```json
[
  {{
    "id": "slide_01_hook",
    "rank": 1,
    "state": "draft",
    "story": "HOOK: Surprise with unexpected statistic to grab attention",
    "atoms": {example_atoms_value},
    "density": "minimal",
    "visual_design": "Large dramatic number on left, brief context line on right",
    "layout": "",
    "widgets": {{}}
  }},
  ...
]
```

Return ONLY the JSON array, no other text."""


def _get_story_from_source_prompt(
    source_content: str,
    user_instruction: str,
    slide_count: Optional[int],
    intent_guidance: str,
) -> str:
    """Build prompt for story generation directly from source content."""
    # Truncate source if too long
    max_content_length = 10000
    content_preview = source_content[:max_content_length]
    if len(source_content) > max_content_length:
        content_preview += f"\n\n... (truncated {len(source_content) - max_content_length} chars)"
    
    content_section = f"""## Source Content
```
{content_preview}
```"""
    
    return _build_story_prompt(
        content_section=content_section,
        atoms_description="[] (empty - content will be extracted later)",
        example_atoms_value="[]",
        user_instruction=user_instruction,
        intent_guidance=intent_guidance,
        slide_count=slide_count,
    )


def _get_story_prompt(
    atoms: AtomCollection,
    user_instruction: str,
    slide_count: Optional[int],
    intent_guidance: str,
) -> str:
    """Build prompt for story generation from atoms."""
    # Create a compact atom summary for the prompt
    atom_summaries = []
    for atom in atoms.list_contexts():
        # Get content using helper function
        content = _get_atom_content(atom)
        content_preview = content[:200] if len(content) > 200 else content
        atom_summaries.append({
            "id": atom.id,
            "type": _get_atom_type(atom),
            "content": content_preview,
            "rank": atom.rank,
        })
    atoms_json = json.dumps(atom_summaries, indent=2)
    
    content_section = f"""## Atoms (content units to use)
```json
{atoms_json}
```"""
    
    return _build_story_prompt(
        content_section=content_section,
        atoms_description="List of atom IDs to use (from input atoms)",
        example_atoms_value='["stat_001", "fact_002"]',
        user_instruction=user_instruction,
        intent_guidance=intent_guidance,
        slide_count=slide_count,
    )


def _get_refine_prompt(
    existing_slides: List[Dict],
    atoms: AtomCollection,
    user_instruction: str,
    intent_guidance: str,
) -> str:
    """Build prompt for story refinement."""
    atoms_json = atoms.to_json(indent=2)
    slides_json = json.dumps(existing_slides, indent=2)
    
    return f"""You are refining an existing presentation story.

# CURRENT SLIDES
```json
{slides_json}
```

# AVAILABLE ATOMS
```json
{atoms_json}
```

# USER REQUEST
{user_instruction}

# GUIDANCE
{intent_guidance or "None"}

# TASK

Modify the story based on the user's request. Common operations:
- Merge slides: Combine story/atoms from multiple slides into one
- Split slide: Divide one slide's content into multiple
- Add slide: Insert new slide with atoms and story
- Remove slide: Delete slide (don't reassign its atoms elsewhere)
- Reorder: Change ranks to restructure flow

# OUTPUT RULES

1. For slides you DON'T change: Keep exactly as-is
2. For slides you CHANGE: Set state="draft" (they need new layout/widgets)
3. Return the COMPLETE slide list (not just changed ones)
4. Keep layout="" and widgets={{}} for all draft slides

# OUTPUT FORMAT

Return ONLY the JSON array of all slides:
```json
[
  {{"id": "slide_01_hook", "rank": 1, "state": "active", ...}},  // unchanged
  {{"id": "slide_02_merged", "rank": 2, "state": "draft", ...}},  // changed
  ...
]
```"""


def generate_story_from_source(
    source_content: str,
    user_instruction: str,
    slide_count: Optional[int] = None,
    intent_guidance: str = "",
) -> List[Dict[str, Any]]:
    """Generate draft slides directly from source content without atoms.
    
    Args:
        source_content: Raw source text to create story from
        user_instruction: User's generation instructions
        slide_count: Target number of slides
        intent_guidance: Optional guidance from constitution
        
    Returns:
        List of draft slide dicts with story, visual_design populated (atoms field empty)
    """
    prompt = _get_story_from_source_prompt(source_content, user_instruction, slide_count, intent_guidance)
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a presentation storyteller. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=8000,  # Need room for 10+ draft slides
    )
    
    # Parse JSON from response
    slides = _parse_json_array(response)
    
    # Validate and normalize
    for slide in slides:
        slide["state"] = "draft"
        slide.setdefault("layout", "")
        slide.setdefault("widgets", {})
        slide.setdefault("density", "moderate")
        slide.setdefault("visual_design", "hierarchical")
        slide.setdefault("atoms", [])  # Empty atoms list for source-based generation
    
    return slides


def refine_story(
    existing_slides: List[Dict],
    atoms: AtomCollection,
    user_instruction: str,
    intent_guidance: str = "",
) -> List[Dict[str, Any]]:
    """Refine existing story using atoms for structured content understanding.
    
    This is the PREFERRED refinement method when atoms are available.
    Atoms provide structured content types (BIO, FACT, STAT, QUOTE, etc.)
    enabling precise content reassignment between slides.
    
    Args:
        existing_slides: Current slides to modify
        atoms: AtomCollection for structured content reference
        user_instruction: What to change
        intent_guidance: Optional guidance
        
    Returns:
        Updated list of slides (mix of active and draft)
    """
    prompt = _get_refine_prompt(existing_slides, atoms, user_instruction, intent_guidance)
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a presentation storyteller. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=8000,
    )
    
    # Parse JSON from response
    slides = _parse_json_array(response)
    
    # Normalize
    for slide in slides:
        if slide.get("state") == "draft":
            slide.setdefault("layout", "")
            slide.setdefault("widgets", {})
    
    return slides


def refine_story_from_source(
    existing_slides: List[Dict],
    source_content: str,
    user_instruction: str,
    intent_guidance: str = "",
) -> List[Dict[str, Any]]:
    """Refine existing story using source content as reference (fallback method).
    
    Used when atoms are not yet available. Good for structural changes
    (merge, split, reorder) but less precise for content-level edits.
    
    Args:
        existing_slides: Current slides to modify
        source_content: Raw source text for reference
        user_instruction: What to change
        intent_guidance: Optional guidance
        
    Returns:
        Updated list of slides (mix of active and draft)
    """
    # Truncate source if too long
    max_content_length = 10000
    content_preview = source_content[:max_content_length]
    if len(source_content) > max_content_length:
        content_preview += f"\n\n... (truncated {len(source_content) - max_content_length} chars)"
    
    slides_json = json.dumps(existing_slides, indent=2)
    
    prompt = f"""You are refining an existing presentation story.

# CURRENT SLIDES
```json
{slides_json}
```

# SOURCE CONTENT (for reference)
```
{content_preview}
```

# USER REQUEST
{user_instruction}

# GUIDANCE
{intent_guidance or "None"}

# TASK

Modify the story based on the user's request. Common operations:
- Merge slides: Combine story from multiple slides into one
- Split slide: Divide one slide's content into multiple
- Add slide: Insert new slide with story
- Remove slide: Delete slide
- Reorder: Change ranks to restructure flow

# OUTPUT RULES

1. For slides you DON'T change: Keep exactly as-is
2. For slides you CHANGE: Set state="draft" (they need new layout/widgets)
3. Return the COMPLETE slide list (not just changed ones)
4. Keep layout="" and widgets={{}} and atoms=[] for all draft slides

# OUTPUT FORMAT

Return ONLY the JSON array of all slides:
```json
[
  {{"id": "slide_01_hook", "rank": 1, "state": "active", ...}},  // unchanged
  {{"id": "slide_02_merged", "rank": 2, "state": "draft", ...}},  // changed
  ...
]
```"""
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a presentation storyteller. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=8000,
    )
    
    # Parse JSON from response
    slides = _parse_json_array(response)
    
    # Normalize
    for slide in slides:
        if slide.get("state") == "draft":
            slide.setdefault("layout", "")
            slide.setdefault("widgets", {})
            slide.setdefault("atoms", [])
    
    return slides


def _parse_json_array(response: str) -> List[Dict]:
    """Extract JSON array from LLM response."""
    # Try to find JSON array in response
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try direct parse
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse story response as JSON: {e}")
