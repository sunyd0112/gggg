"""Test SCQA-based story generation and compare with expected output."""
import json
from src.generation.content.story_generator import generate_story_from_source

# Load test content from file
input_file = "data/context/output_driven_meeting.txt"
with open(input_file, 'r', encoding='utf-8') as f:
    test_content = f.read()

print(f"📂 Loaded input from: {input_file}")
print(f"📊 Content length: {len(test_content)} characters\n")

def test_story_generation():
    """Test story generation with SCQA framework."""
    print("=" * 80)
    print("TESTING SCQA STORY GENERATION")
    print("=" * 80)
    
    # Generate story from source
    print("\n📝 Generating story from source content...")
    
    slides = generate_story_from_source(
        source_content=test_content,
        user_instruction="Create a 10-slide executive pitch deck",
        slide_count=10,
        intent_guidance="Focus on business impact and feasibility"
    )
    
    print(f"✅ Generated {len(slides)} slides\n")
    
    # Export to JSON for comparison
    output_file = "test_story_scqa_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(slides, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved output to: {output_file}\n")
    
    # Print summary
    print("=" * 80)
    print("SLIDE SUMMARY")
    print("=" * 80)
    for slide in slides:
        rank = slide.get('rank', '?')
        slide_id = slide.get('id', 'unknown')
        headline = slide.get('headline', slide.get('story', ''))[:60]
        category = slide.get('category', 'N/A')
        density = slide.get('density', 'N/A')
        
        print(f"\n[{rank}] {slide_id}")
        print(f"    Category: {category}")
        print(f"    Density:  {density}")
        print(f"    Headline: {headline}...")
    
    # Print detailed view of first 2 slides
    print("\n" + "=" * 80)
    print("DETAILED VIEW - FIRST 2 SLIDES")
    print("=" * 80)
    for slide in slides[:2]:
        print(f"\n{json.dumps(slide, indent=2, ensure_ascii=False)}")
    
    print("\n" + "=" * 80)
    print(f"NEXT STEPS:")
    print("=" * 80)
    print(f"1. Review {output_file} for full output")
    print(f"2. Compare with your GPT-5.2 sample output")
    print(f"3. Check for:")
    print(f"   - SCQA structure (Situation → Complication → Answer)")
    print(f"   - Billboard headlines (≤9 words, strategic claims)")
    print(f"   - Cognitive rhythm (varied density)")
    print(f"   - Visual frameworks (not decorative images)")
    print(f"   - Empty atoms: [] for all slides")
    print("=" * 80)
    
    return slides

if __name__ == "__main__":
    # For debugging with breakpoints, set one here:
    # import pdb; pdb.set_trace()
    
    slides = test_story_generation()
    
    # OPTIONAL: Save your GPT-5.2 sample output here for automated comparison
    # expected_file = "expected_story_output.json"
    # if os.path.exists(expected_file):
    #     with open(expected_file, 'r', encoding='utf-8') as f:
    #         expected = json.load(f)
    #     
    #     print("\n🔍 COMPARISON WITH EXPECTED OUTPUT:")
    #     print(f"Expected slides: {len(expected)}")
    #     print(f"Generated slides: {len(slides)}")
    #     # Add more comparison logic here
