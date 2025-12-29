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
    """Build prompt for story generation directly from source content using SCQA framework."""
    # Truncate source if too long
    max_content_length = 10000
    content_preview = source_content[:max_content_length]
    if len(source_content) > max_content_length:
        content_preview += f"\n\n... (truncated {len(source_content) - max_content_length} chars)"
    
    target_slides = slide_count or 10
    
    return f"""**Role**: You are an elite Strategy Consultant specialized in high-stakes venture capital pitches and executive reviews. Your task is to transform the provided uploaded file into an executive storyline for a leadership review.

# UPLOADED FILE CONTENT
```
{content_preview}
```

# USER INSTRUCTION
{user_instruction or "Create a compelling presentation"}

# GUIDANCE
{intent_guidance or "None"}

# TARGET SLIDES
{target_slides} slides

### I. Narrative Blueprint (strict)
1. Use the **SCQA** flow to structure the narrative to move the audience from agreement to anxiety, then to resolution.
   - **S (Situation): *Impact-first status quo*. Establish the shared "Status Quo" everyone agrees on, **starting from business outcomes**. 
   - **C (Complication): ** Identify the "Villain"—the market shift, pain point, or crisis that creates **Tension** and urgency. Explanation: Don't just list problems; frame them as an active loss of value/revenue that creates a **"crisis of inaction."**
   - **Q (Question): ** Frame the strategic question: How do we capture the opportunity while solving the pain?
   - **A (Answer): ** Present the product as the inevitable resolution.
2. **Answer-first SCQA**: Reduce preface and reveal the "core thing we are proposing" (i.e. "Answer") early, then justify it. Compress the SCQ content.
   - No "scene-setting" slides that restate what everyone knows without a decision implication.
   - Avoid multi-slide problem tours before naming the solution.
   - Avoid abstract vision language without a tangible "what we are building/changing" early.

#### Example: 10-slide structure (SCQA, *no over-index on "Q"*; 80% on Solution + Feasibility + Moat)
- Slide 1: Cover page includes title, subtitle (one-sentence conclusion/vision), presenter/team, date/context
- Slide 2-3: S + C (fast, minimal background, impact-first mandate for early slides). **Purpose:** move the room from *agreement → anxiety* fast
- Slides 4–8: A (Answer) = Solution + Moat + Proof. **Purpose:** make the resolution feel inevitable: *what we build, why we win, why it's buildable
- Slides 9–10: Commit (de-risk + decision + next steps, FAQ, closing vision). **Purpose:** convert skepticism into confidence and force a clean decision

[IMPORTANT] This narrative example is a **reference**, not a strict template. You must **adapt slide allocation and sequencing** based on the Input Document.
- You may **merge, split, reorder, or rename** slides where it improves clarity and pacing.
- Keep the **SCQA arc** and the **80/20 rule** intact, but avoid forcing content into a slot that doesn't fit.
- Prioritize **novel, non-redundant** slides; if two slides would say the same thing, merge them.
- If the uploaded file lacks evidence for a component (e.g., moat, scale signals), **de-emphasize** it and shift emphasis to what *is* supported.

### II. Content Rules (Hard Constraints)
1. **Vertical & Horizontal Logic (The Pyramid Upgrade)**:
   - *Horizontal*: If you read only the headlines of the deck in order, they must form a flawless, 30-second elevator pitch. If there is a "logic gap" between slide titles, the deck fails.
   - *Vertical*: Every headline must be a claim; every bullet below it must be the evidence.
2. **Cognitive Rhythm (Density Control)**: Vary the "Cognitive Load" to prevent audience fatigue. Some slides should be "Deep Dives" (dense evidence on technical workflow), while others must be "Impact Slides" (sparse, bold visuals/text to anchor emotional "aha" moments). Never put two Deep Dives back-to-back.
3. **Insight Density**: 
   - *Metric Prioritization*: You must extract and prioritize critical data (metric, datetime, number) in the uploaded file.
   - *The "So What" Conversion*: Replace descriptive facts with strategic inferences to drive decisions. Every bullet must pass the "So What?" test by converting context into quantified impact. Replace "table stakes" (e.g., "market is growing") with active outcomes (e.g., "growth reduces CAC by 15%"). Never present data without a conclusion.
4. **Feasibility over Vision**: Provide concrete artifacts (like design, data, prototype, etc.) to prove the solution is buildable, not just aspirational.
5. **Non-Redundancy**: No duplicated content across slides. Every slide must provide "new information gain."
6. **No Ghost Data**: 
   - Use only facts in the uploaded file. Do not hallucinate.
   - If critical data is missing, highlight it as a "Strategic Unknown" rather than inventing it.
   - If any "Strategic Unknowns" are identified, you must append a "Data Gap Summary" slide at the very end (after the closing page). If no data is missing, omit this slide.
7. **Subject-Matter Section Titles**: Section titles must describe the content (e.g., "Current User Friction"), not the narrative slot (e.g., "Villain").


### III. Headline Compression Rules (Hard Constraints)
1. **Billboard Headlines**: Every title must be a standalone strategic claim. If an executive reads only the titles, they should grasp the entire investment thesis without looking at the body (English: ≤ 9 words | Chinese: ≤ 15 characters).
   - *Bad*: "Market Analysis"
   - *Good*: "Rising acquisition costs are eroding our Q3 profit margins."
2. Quick "do/don't" rules for great headlines:
   - *Do*: (1) High-density claims. (1) One claim, one verb, one outcome. (2) Put details in subtitle/body.
   - *Don't*: Feature lists, architecture nouns, or "we will build…".
3. Executive Tone: Avoid flowery/dramatic language.
   - *Bad*: "Meeting value dies without artifacts." (Too dramatic)
   - *Good*: "Manual document creation delays execution by [X] days." (Professional/Measured)
   - *Good*: "AI converts spoken intent into tool-ready artifacts." (Clear/Actionable)


#### Good executive headline formulas for slide titles (Soft Guidance):
- Outcome → Mechanism (classic, punchy)
- Villain → Cost (creates urgency fast)
- Decision / Ask framing (forces leadership action)
- Before → After transformation (visual and memorable)
- Strategic positioning (why we win)
- Proof / Feasibility (build confidence)
- Value / ROI framing (exec-friendly)
- Principle / thesis statements (clean and authoritative)
- Risk → Mitigation (de-risking slide titles)

### IV. Linguistic & Tone (Hard Constraints)
1. **Strategic Punchline Usage ("Less but Sharper")**: Selectively add **punchlines** on key slides—such as the **conclusion, major turning points, and core data pages**—to **anchor the message, tighten the narrative, and reinforce the "WOW" factor**. 
[IMPORTANT] Follow the **"less but sharper"** principle and **control the frequency**; overusing punchlines can make the content feel hollow and slogan-like. Use **at most 3 total** across the deck.
2. **Semantic Compression & Information Density**: Avoid "fluff" and "wordiness." Transform weak sentences ("We want to make search faster") into high-density claims ("Optimizing discovery to reduce time-to-value").
3. **WIIFM Persona-Matching**: Tailor vocabulary and focus for the specific stakeholder.
4. **Impact over Features**: Focuses on the Impact (Outcomes) rather than the Outputs. 
    - *Bad*: "we built X"
    - *Good*: "X achieves Y". This text feels more "targeted" to leaders.
5. **The Elevator Pitch Test**: Do the headlines connect smoothly (e.g., Slide 1 leads inevitably to Slide 2). Can the headlines be read sequentially to form a coherent 30-second pitch?

### V. Visual Hint (Hard Constraints): 
- Framework over Imagery: Do not describe "pictures." Describe logical frameworks (e.g., 2x2 matrix, Flywheel, Bridge chart).
- Mandatory for Deep Dives: For every "Deep Dive" slide, the visual_design must specify a professional consulting chart type (e.g., Waterfall, Sankey, Gantt, or Harvey Balls).

### VI. The Creative Edge (Soft Guidance): 
1. Use metaphors where appropriate to clarify complex concepts (e.g., comparing a platform to an "operating system for logistics" rather than just a "management tool"). 
2. Aim for a "Visionary yet Grounded" tone—the deck should feel like it was written by a partner who deeply understands the business, not a clerk summarizing a file.

# OUTPUT FORMAT

## Step 1: Analyze and Design
After analyzing the uploaded file, first decide the main focus of the storyline. Then output the design of the storyline following the "Answer-first SCQA" arc:

```json
{{
  "presentation_meta": {{
    "title": "string (presentation title)",
    "subtitle": "string (optional one-sentence vision/conclusion)",
    "audience": "string (target audience, e.g., 'Executive Leadership', 'VCs', 'Product Team')",
    "focus": "string (main focus/thesis of the presentation)",
    "total_slides": integer (total slide pages),
    "scqa_design": "string (Design the storyline by specifying the S/C/Q/A structure and map body slides to corresponding phases."
  }}
}}
```

## Step 2: Generate Slides
Then output the slides (exactly {{presentation_meta.total_slides}} slides) as JSON in the following format:

```json
{{
  "slides": [
    {{
      "slide_id": 1 (cover page),
      "headline": "presentation_meta.title",
      "subtitle": "presentation_meta.subtitle (optional)",
      "category": "cover",
      "presenters": [
          {{"name": "string", "role": "string (optional)", "org": "string (optional)"}}
        ],
      "date": "YYYY-MM-DD (optional; defaults to meta.date)"
      "visual_design": "string (optional)"
    }},
    {{
      "slide_id": 2,
      "headline": "string (active_headline, exec-readable, declarative)",
      "subtitle": "string (optional, adds precision or scope)",
      "density_tag": "impact | medium | deepdive",
      "speaker_intent": "string (optional: what the audience should think/decide/feel)",
      "category": "Situation | Complication | Question | Answer",
      "content": {{
        "sections": [
          {{
            "title": "string",
            "bullets": [
              {{
                "text": "string",
                "citation": {{
                  "source_id": "string",
                  "location": "string (optional: page/section/timestamp)"
                }}
              }}
            ]
          }}
        ]
      }},
      "visual_design": "string (optional)"
    }},
    {{
      "slide_id": N (ending page),
      "headline": "string (ending of the presentation, like 'Thank you'/'Decision needed'/'Next Step'/'Q&A' etc.)",
      "subtitle": "string (optional, adds precision or scope)",
      "category": "ending",
      "visual_design": "string (optional)"
    }},
    {{
      "slide_id": N+1 (Include this slide ONLY if Strategic Unknowns exist. Omit otherwise.),
      "headline": "Data Gap Summary",
      "category": "data",
      "content": {{
        "sections": [
          {{
            "title": "Critical Data Gaps",
            "bullets": [
              {{
                "text": "Identify specific missing data point (e.g., Year 3 CAGR) in slide [slide_id]"
              }}
            ]
          }}
        ]
      }}
    }}
  ]
}}
```

Return ONLY this JSON object with slides. No other text."""


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
    """Generate draft slides directly from source content using SCQA framework.
    
    Creates executive-level storyline following:
    - SCQA narrative structure (Situation, Complication, Question, Answer)
    - Impact-first headlines with strategic claims
    - Cognitive rhythm balancing dense and minimal slides
    - Visual frameworks (not decorative images)
    
    Args:
        source_content: Raw source text to create story from
        user_instruction: User's generation instructions
        slide_count: Target number of slides
        intent_guidance: Optional guidance from constitution
        
    Returns:
        List of draft slide dicts with story, headline, visual_design populated (atoms field empty)
    """
    prompt = _get_story_from_source_prompt(source_content, user_instruction, slide_count, intent_guidance)
    
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    response = call_llm(
        system_prompt="You are an elite Strategy Consultant creating executive storylines. Output only valid JSON array following the SCQA framework.",
        user_prompt=prompt,
        deployment=deployment,
        temperature=0.7,
        max_tokens=8000,  # Need room for 10+ draft slides with detailed visual_design
    )
    
    # Parse JSON from response
    result = _parse_json_response(response)
    
    # Extract slides (parser guarantees dict with "slides" key)
    slides = result["slides"]
    
    # Validate and normalize
    for slide in slides:
        # Normalize slide_id to id (new SCQA format uses slide_id)
        if "slide_id" in slide and "id" not in slide:
            slide["id"] = f"slide_{str(slide['slide_id']).zfill(2)}"
        
        slide["state"] = "draft"
        slide.setdefault("layout", "")
        slide.setdefault("widgets", {})
        slide.setdefault("density", "moderate")
        slide.setdefault("visual_design", "hierarchical")
        slide.setdefault("atoms", [])
        
        # Set rank from slide_id if not present
        if "rank" not in slide and "slide_id" in slide:
            slide["rank"] = slide["slide_id"]
    
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


def _parse_json_response(response: str):
    """Extract JSON object with slides from LLM response.
    
    Handles format: Array with slides element like [{"presentation_meta": ...}, {"slides": [...]}]
    or direct {"slides": [...]}
    """
    # Try direct parse first
    try:
        parsed = json.loads(response)
        
        # If it's an array, find the element with "slides"
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "slides" in item:
                    return item
            # If no element has slides, raise error
            raise ValueError("No element with 'slides' field found in array response")
        
        # If it's a dict with slides, return it
        if isinstance(parsed, dict) and "slides" in parsed:
            return parsed
            
        raise ValueError(f"Unexpected response format: {type(parsed)}")
        
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object with slides using regex
    json_match = re.search(r'\{[\s\S]*"slides"[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Failed to parse story response as JSON")


def _parse_json_array(response: str) -> List[Dict]:
    """Extract JSON array from LLM response (for refinement operations)."""
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
