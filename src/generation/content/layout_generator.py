"""Layout generator - Generates layouts and widgets for draft slides.

Takes draft slides with story, atoms, visual_design and generates:
- layout: Appropriate layout name based on visual_design
- widgets: Widget content populated from atoms
- state: "active"
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
    if hasattr(atom, 'text') and atom.text:
        return atom.text
    if hasattr(atom, 'quote') and atom.quote:
        return atom.quote
    if hasattr(atom, 'description') and atom.description:
        return atom.description
    if hasattr(atom, 'name') and atom.name:
        parts = [atom.name]
        if hasattr(atom, 'role') and atom.role:
            parts.append(atom.role)
        if hasattr(atom, 'affiliation') and atom.affiliation:
            parts.append(atom.affiliation)
        return " - ".join(parts)
    if hasattr(atom, 'value') and hasattr(atom, 'label'):
        return f"{atom.value} ({atom.label})"
    if hasattr(atom, 'abstract') and atom.abstract:
        return atom.abstract
    return str(atom.id)


def _get_atom_type(atom) -> str:
    """Get the type name of an atom."""
    return type(atom).__name__


def _get_layout_prompt(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    atoms: AtomCollection,
    theme_id: Optional[str],
    intent_guidance: str,
) -> str:
    """Build prompt for layout generation."""
    drafts_json = json.dumps(draft_slides, indent=2)
    
    # Only include atoms that are referenced by the draft slides
    referenced_atom_ids = set()
    for slide in draft_slides:
        for atom_id in slide.get("atoms", []):
            referenced_atom_ids.add(atom_id)
    
    # Filter atoms to only those referenced
    referenced_atoms = []
    for atom in atoms.list_contexts():
        if atom.id in referenced_atom_ids:
            content = _get_atom_content(atom)
            referenced_atoms.append({
                "id": atom.id,
                "type": _get_atom_type(atom),
                "content": content[:500] if len(content) > 500 else content,
                "rank": atom.rank,
            })
    
    atoms_json = json.dumps(referenced_atoms, indent=2)
    
    # Build context section - only include layout/widgets from context slides, not full content
    context_section = ""
    if context_before:
        context_slim = [{"id": s.get("id"), "layout": s.get("layout"), "story": s.get("story", "")[:100]} for s in context_before]
        context_section += f"## Slides Before (for flow reference)\n```json\n{json.dumps(context_slim, indent=2)}\n```\n\n"
    if context_after:
        context_slim = [{"id": s.get("id"), "layout": s.get("layout"), "story": s.get("story", "")[:100]} for s in context_after]
        context_section += f"## Slides After (for flow reference)\n```json\n{json.dumps(context_slim, indent=2)}\n```\n\n"
    
    return f"""# SLIDE LAYOUT GENERATION

## Draft Slides
```json
{drafts_json}
```

## Referenced Atoms
```json
{atoms_json}
```
{context_section}
# TASK
For each draft slide: select layout based on visual_design, populate widgets from atoms, set state="active".

# LAYOUTS (name: slots)
- hero-split: left, right
- smart-grid: header, col1-col4
- timeline: title, step1-step5
- comparison: title, beforeLabel, before, afterLabel, after
- dashboard: title, metric1-4, chart
- center: default
- spotlight: default, subtitle
- quote-hero: quote, author, context
- stats-showcase: title, stat-1 to stat-4

# WIDGET TYPES
- Type.Display (headline), Type.Heading, Type.Body, Type.List (items array), Type.Quote
- Data.BigNum (value, label, sublabel), Data.Metric (value, label, trend), Data.Chart

# OUTPUT
JSON array. Each slide must have: id, rank, state="active", story (keep), atoms (keep), density (keep), visual_design (keep), layout (new), widgets (new).

```json
[{{"id":"...", "rank":1, "state":"active", "story":"...", "atoms":[...], "density":"...", "visual_design":"...", "layout":"hero-split", "widgets":{{"left":{{"type":"Data.BigNum","parameters":{{"value":"14","label":"Years"}}}},"right":{{"type":"Type.Body","parameters":{{"text":"..."}}}}}}}}]
```

Return ONLY the JSON array, no explanation."""


def generate_layouts(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    atoms: Optional[AtomCollection],
    theme_id: Optional[str] = None,
    intent_guidance: str = "",
) -> List[Dict[str, Any]]:
    """Generate layouts and widgets for draft slides.
    
    Supports two modes:
    1. New SCQA format: Slides already have 'content' field with sections/bullets
       -> Use _generate_layouts_from_content (skip LLM)
    2. Old atom-based format: Slides have 'atoms' IDs only
       -> Generate content and widgets from atoms via LLM
    
    Args:
        draft_slides: Slides with story/atoms/visual_design but no layout/widgets
        context_before: Up to 2 active slides before for context
        context_after: Up to 2 active slides after for context
        atoms: AtomCollection for widget content
        theme_id: Active theme ID
        intent_guidance: Additional guidance
        
    Returns:
        List of active slides with layout and widgets populated
    """
    if not draft_slides:
        return []
    
    # Detect which format: check if slides have 'content' field already
    has_content = any(slide.get("content") for slide in draft_slides)
    
    if has_content:
        # New SCQA format: content already generated by story tool
        return _generate_layouts_from_content(draft_slides, theme_id)
    
    # Old atom-based format
    if not atoms:
        # No atoms - can't populate widgets meaningfully
        # Return drafts with minimal layouts
        return _fallback_layouts(draft_slides)
    
    prompt = _get_layout_prompt(
        draft_slides, context_before, context_after,
        atoms, theme_id, intent_guidance
    )
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a slide designer. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=16000,  # Need room for 10 slides with widgets
    )
    
    # Parse JSON from response
    active_slides = _parse_json_array(response)
    
    # Validate and normalize
    for slide in active_slides:
        slide["state"] = "active"
        if not slide.get("layout"):
            # Default fallback layout
            slide["layout"] = "center"
        if not slide.get("widgets"):
            slide["widgets"] = {}
    
    return active_slides


def _fallback_layouts(draft_slides: List[Dict]) -> List[Dict]:
    """Generate minimal layouts when no atoms available."""
    result = []
    for slide in draft_slides:
        active = dict(slide)
        active["state"] = "active"
        active["layout"] = "center"  # Simple default
        active["widgets"] = {
            "default": {
                "type": "Type.Body",
                "parameters": {"text": slide.get("story", "Slide content")}
            }
        }
        result.append(active)
    return result


def _generate_layouts_from_content(
    draft_slides: List[Dict],
    theme_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Generate layouts for slides that already have content populated.
    
    New SCQA format: content structure is already present, just need to:
    1. Map visual_design to layout name
    2. Convert content sections/bullets to widgets
    3. Normalize field names (slide_id -> id, etc.)
    """
    active_slides = []
    
    for slide in draft_slides:
        # Normalize field names
        slide_id = slide.get("id") or slide.get("slide_id")
        rank = slide.get("rank", 0)
        
        # Determine layout from visual_design or category
        visual_design = slide.get("visual_design", "").lower()
        category = slide.get("category", "")
        
        # Simple layout mapping based on category and visual_design
        if category == "cover":
            layout = "title"
        elif category == "ending":
            layout = "ending"
        elif "chart" in visual_design or "matrix" in visual_design:
            layout = "visual-emphasis"
        elif "hero" in visual_design or "split" in visual_design:
            layout = "hero-left"
        else:
            layout = "standard"
        
        # Extract widgets from content if present
        widgets = {}
        content = slide.get("content", {})
        if content and isinstance(content, dict):
            sections = content.get("sections", [])
            if sections:
                # Convert sections/bullets to widget format
                bullets = []
                for section in sections:
                    if section.get("title"):
                        bullets.append({"text": section["title"], "level": "h3"})
                    for bullet in section.get("bullets", []):
                        bullets.append({"text": bullet.get("text", ""), "level": "body"})
                
                widgets["content"] = {"type": "text", "bullets": bullets}
        
        # Build active slide
        active_slide = {
            "id": slide_id,
            "rank": rank,
            "state": "active",
            "layout": layout,
            "widgets": widgets,
            # Preserve all original fields
            "headline": slide.get("headline", ""),
            "subtitle": slide.get("subtitle"),
            "category": slide.get("category"),
            "content": content,
            "visual_design": slide.get("visual_design", ""),
            "density": slide.get("density", "moderate"),
            "atoms": slide.get("atoms", []),
        }
        
        # Add cover-specific fields
        if category == "cover":
            active_slide["presenters"] = slide.get("presenters", [])
            active_slide["date"] = slide.get("date")
        
        # Add speaker_intent if present
        if slide.get("speaker_intent"):
            active_slide["speaker_intent"] = slide["speaker_intent"]
        
        # Add density_tag if present
        if slide.get("density_tag"):
            active_slide["density_tag"] = slide["density_tag"]
        
        active_slides.append(active_slide)
    
    return active_slides


def _generate_layouts_from_atoms(
    draft_slides: List[Dict],
    context_before: List[Dict],
    context_after: List[Dict],
    atoms: AtomCollection,
    theme_id: Optional[str],
    intent_guidance: str,
) -> List[Dict[str, Any]]:
    """Generate layouts for slides using atom-based content (legacy mode)."""
    prompt = _get_layout_prompt(
        draft_slides, context_before, context_after, atoms, theme_id, intent_guidance
    )
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are a presentation layout designer. Output only valid JSON array.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=8000,
    )
    
    slides = _parse_json_array(response)
    
    # Ensure state is active
    for slide in slides:
        slide["state"] = "active"
        slide.setdefault("layout", "standard")
        slide.setdefault("widgets", {})
    
    return slides


def _parse_json_array(response: str) -> List[Dict]:
    """Extract JSON array from LLM response."""
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse layout response as JSON: {e}")
